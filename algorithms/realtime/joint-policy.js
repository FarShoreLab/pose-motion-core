import {BONES, KEY_JOINTS} from './skeleton.js';

export const GROUPS = {
  torso: {joints: [11, 12, 23, 24], enter: .60, exit: .50},
  hinge: {joints: [13, 14, 25, 26], enter: .65, exit: .50},
  distal: {joints: [15, 16, 27, 28], enter: .70, exit: .55},
  detail: {joints: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18, 19, 20, 21, 22, 29, 30, 31, 32], enter: .70, exit: .55}
};

export const DEFAULTS = {
  uncertainFloor: .35,
  predictionMs: 150,
  maxSpeed: 6,
  maxNormalizedSpeed: 3,
  groups: GROUPS
};

const finite = point => point && [point.x, point.y, point.z].every(Number.isFinite);
const copy = point => ({x: point.x, y: point.y, z: point.z});
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

// Stateful causal quality policy. Input records retain their original coordinates.
export class JointTracker {
  constructor(options = {}) {
    this.options = {...DEFAULTS, ...options};
    this.reset();
  }

  reset() {
    this.context = null;
    this.lastPTS = null;
    this.previous = Array(33).fill('lost');
    this.history = Array.from({length: 33}, () => []);
    this.boneLengths = new Map();
  }

  observe(record, {missing = []} = {}) {
    const context = `${record.clip}:${record.epoch}`;
    const contextReset = context !== this.context || record.source_pts_ms <= this.lastPTS;
    if (contextReset) {
      this.reset();
      this.context = context;
    }
    const world = [], landmarks = [], states = [], reasons = [], confidence = [];
    const transitions = [], groups = [], pts = record.source_pts_ms;
    for (let joint = 0; joint < 33; joint++) {
      const point = record.world_landmarks?.[joint];
      const landmark = record.landmarks?.[joint];
      const score = Math.min(landmark?.visibility ?? 0, landmark?.presence ?? 0);
      confidence.push(score);
      const [groupName, group] = Object.entries(this.options.groups).find(([, value]) => value.joints.includes(joint));
      groups.push(groupName);
      const threshold = this.previous[joint] === 'measured' ? group.exit : group.enter;
      let state = 'uncertain', reason = 'low_confidence_raw_observation';
      const safe = finite(point) && finite(landmark)
        && Math.max(Math.abs(point.x), Math.abs(point.y), Math.abs(point.z)) < 5
        && landmark.x > -.5 && landmark.x < 1.5 && landmark.y > -.5 && landmark.y < 1.5;
      if (missing.includes(joint)) {
        state = 'lost'; reason = 'synthetic_missing_mask';
      } else if (!safe) {
        state = 'lost'; reason = 'no_finite_or_bounded_observation';
      } else if (score < this.options.uncertainFloor) {
        state = 'lost'; reason = 'below_uncertain_display_floor';
      } else if (score >= threshold) {
        state = 'measured'; reason = null;
      }
      const history = this.history[joint], last = history.at(-1);
      const elapsedSeconds = last ? (pts - last.pts) / 1000 : 0;
      if (state === 'measured' && last && elapsedSeconds > 0 && elapsedSeconds < .5
          && distance(point, last.world) > this.options.maxSpeed * elapsedSeconds + .10) {
        state = 'uncertain'; reason = 'implausible_joint_jump';
      }
      if (state === 'measured' && this.implausibleBone(joint, point, record)) {
        state = 'uncertain'; reason = 'implausible_bone_length';
      }
      // A reused model can carry ROI history across a loop or source cut.
      if (contextReset && record.model_reused_across_context && state === 'measured') {
        state = 'uncertain'; reason = 'context_reacquisition';
      }
      world.push(state === 'lost' ? null : copy(point));
      landmarks.push(state === 'lost' ? null : copy(landmark));
      states.push(state); reasons.push(reason);
      if (state !== this.previous[joint]) {
        transitions.push({joint, from: this.previous[joint], to: state, reason, confidence: score});
      }
      if (state === 'measured') {
        history.push({pts, world: copy(point), landmark: copy(landmark), frame_id: record.frame_id});
        if (history.length > 2) history.shift();
      }
    }
    for (const [a, b] of BONES) {
      if (states[a] !== 'measured' || states[b] !== 'measured') continue;
      const key = `${a}:${b}`, length = distance(world[a], world[b]);
      this.boneLengths.set(key, this.boneLengths.has(key) ? this.boneLengths.get(key) * .9 + length * .1 : length);
    }
    this.previous = states;
    this.lastPTS = pts;
    return {
      frame_id: record.frame_id, epoch: record.epoch, clip: record.clip, source_pts_ms: pts,
      world, landmarks, states, reasons, confidence, groups, transitions,
      measured_count: states.filter(state => state === 'measured').length,
      uncertain_count: states.filter(state => state === 'uncertain').length,
      lost_count: states.filter(state => state === 'lost').length,
      // Retained output field means all twelve key joints are measured.
      valid: KEY_JOINTS.every(joint => states[joint] === 'measured')
    };
  }

  implausibleBone(joint, point, record) {
    for (const [a, b] of BONES) {
      if (a !== joint && b !== joint) continue;
      const other = a === joint ? b : a;
      const neighbor = record.world_landmarks?.[other], landmark = record.landmarks?.[other];
      if (!finite(neighbor) || Math.min(landmark?.visibility ?? 0, landmark?.presence ?? 0) < .5) continue;
      const baseline = this.boneLengths.get(`${a}:${b}`), length = distance(point, neighbor);
      if ((baseline > .04 && (length > baseline * 2.2 + .05 || length < baseline * .35)) || length > 1.3) return true;
    }
    return false;
  }

  predict(targetPTS) {
    const world = [], landmarks = [], states = [], basis = [];
    for (let joint = 0; joint < 33; joint++) {
      const history = this.history[joint], last = history.at(-1), prior = history.at(-2);
      const age = last ? targetPTS - last.pts : Infinity;
      if (!last || !prior || age < 0 || age > this.options.predictionMs || last.pts <= prior.pts
          || last.pts - prior.pts > 500 || this.previous[joint] !== 'measured') {
        world.push(null); landmarks.push(null); states.push('lost'); basis.push(null);
        continue;
      }
      const elapsedSeconds = (last.pts - prior.pts) / 1000, horizonSeconds = age / 1000;
      const project = (field, cap) => {
        const velocity = {
          x: (last[field].x - prior[field].x) / elapsedSeconds,
          y: (last[field].y - prior[field].y) / elapsedSeconds,
          z: (last[field].z - prior[field].z) / elapsedSeconds
        };
        const scale = Math.min(1, cap / (Math.hypot(velocity.x, velocity.y, velocity.z) || 1));
        return {
          x: last[field].x + velocity.x * horizonSeconds * scale,
          y: last[field].y + velocity.y * horizonSeconds * scale,
          z: last[field].z + velocity.z * horizonSeconds * scale
        };
      };
      world.push(project('world', this.options.maxSpeed));
      landmarks.push(project('landmark', this.options.maxNormalizedSpeed));
      states.push('predicted');
      basis.push({last_source_pts_ms: last.pts, previous_source_pts_ms: prior.pts, horizon_ms: age, last_frame_id: last.frame_id});
    }
    return {source_pts_ms: targetPTS, world, landmarks, states, basis};
  }
}
