import assert from 'node:assert/strict';
import {test} from 'node:test';
import {JointTracker, LatestFrameQueue, repairReplay} from '../index.js';

function record(pts, confidence = .95, epoch = 1) {
  return {
    frame_id: pts, clip: 'synthetic', epoch, source_pts_ms: pts,
    world_landmarks: Array.from({length: 33}, (_, joint) => ({x: joint * .008, y: joint * .009, z: 0})),
    landmarks: Array.from({length: 33}, (_, joint) => ({x: .3 + joint * .008, y: .2 + joint * .009, z: 0, visibility: confidence, presence: .99}))
  };
}

test('uncertain coordinates remain visible and causal prediction expires', () => {
  const tracker = new JointTracker(), input = record(0, .4), original = structuredClone(input);
  assert(tracker.observe(input).states.every(state => state === 'uncertain'));
  assert.deepEqual(input, original);
  tracker.observe(record(40)); tracker.observe(record(80));
  assert(tracker.predict(200).states.every(state => state === 'predicted'));
  assert(tracker.predict(231).world.every(point => point === null));
  const nextEpoch = record(0, .95, 2);
  nextEpoch.model_reused_across_context = true;
  assert(tracker.observe(nextEpoch).states.every(state => state === 'uncertain'));
  assert(tracker.predict(20).states.every(state => state === 'lost'));
});

test('replay repairs bounded gaps with future measured evidence and preserves epochs', () => {
  const tracker = new JointTracker();
  const frames = [tracker.observe(record(0)), tracker.observe(record(40, .4)), tracker.observe(record(80))];
  assert(repairReplay(frames)[1].states.every(state => state === 'repaired'));
  assert(frames[1].states.every(state => state === 'uncertain'));
  frames[2].epoch = 2;
  assert(repairReplay(frames)[1].states.every(state => state === 'uncertain'));
});

test('queue never releases early and closes every discarded frame once', () => {
  const queue = new LatestFrameQueue({maxPending: 2}), closed = [];
  const frame = id => ({row: {scheduled_release_ms: id * 20}, bitmap: {close() { closed.push(id); }}});
  queue.offer(frame(1), 0); queue.offer(frame(2), 0); queue.offer(frame(3), 0);
  assert.deepEqual(closed, [3]);
  assert.equal(queue.takeDue(19), null);
  const accepted = queue.takeDue(20);
  assert.equal(accepted.row.scheduled_release_ms, 20);
  queue.discard('reset');
  assert.deepEqual(closed, [3, 2]);
  accepted.bitmap.close();
  assert.deepEqual(closed, [3, 2, 1]);
});
