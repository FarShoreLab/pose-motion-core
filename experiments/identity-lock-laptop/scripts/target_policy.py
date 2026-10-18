"""Identity guard above a mature tracker. Numeric IDs never bypass appearance checks."""
import numpy as np


def unit(value):
    a = np.asarray(value, dtype=np.float32)
    return a / max(float(np.linalg.norm(a)), 1e-12)


def iou(a, b):
    a, b = np.asarray(a), np.asarray(b)
    wh = np.maximum(0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2]))
    inter = float(wh.prod())
    area = float(np.maximum(0, a[2:] - a[:2]).prod() + np.maximum(0, b[2:] - b[:2]).prod())
    return inter / max(area - inter, 1e-9)


def overlap_fraction(a, b):
    wh = np.maximum(0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2]))
    return float(wh.prod() / max(np.maximum(0, a[2:] - a[:2]).prod(), 1e-9))


class TargetPolicy:
    def __init__(self, config):
        self.c = config
        self.anchor = None
        self.negatives = []
        self.gallery = []
        self.last_box = None
        self.last_frame = None
        self.last_id = None
        self.velocity = np.zeros(4)
        self.pending_id = None
        self.pending_count = 0
        self.last_template_frame = 0
        self.template_updates = 0
        self.recoveries = 0

    def step(self, frame, detections, features, track_ids):
        dets = np.asarray(detections, dtype=float).reshape(-1, 6)
        feats = [unit(f) if f is not None else None for f in features]
        if self.anchor is None:
            seed = self.c['initialization']['seed_bbox_xyxy']
            candidates = [(iou(d[:4], seed), i) for i, d in enumerate(dets) if feats[i] is not None and i in track_ids]
            if not candidates or max(candidates)[0] < self.c['initialization']['seed_bbox_iou_min']:
                raise RuntimeError('Explicit first-frame target cannot be initialized; no automatic replacement permitted')
            _, selected = max(candidates)
            self.anchor = feats[selected].copy()
            self.anchor.setflags(write=False)
            self.gallery = [self.anchor.copy()]
            self.negatives = [f.copy() for i, f in enumerate(feats) if f is not None and i != selected and iou(dets[i, :4], dets[selected, :4]) < .2]
            return self._accept(frame, dets, feats, track_ids, selected, [], 'initialized', False)

        gap = frame - self.last_frame
        evaluated = []
        for i, (det, feat) in enumerate(zip(dets, feats)):
            reasons = []
            if feat is None:
                evaluated.append({'detection_index': i, 'reasons': ['missing_embedding']})
                continue
            anchor = float(feat @ self.anchor)
            gallery = max(float(feat @ g) for g in self.gallery)
            neg = max((float(feat @ n) for n in self.negatives), default=-1.)
            score = .8 * anchor + .2 * gallery
            tid = track_ids.get(i)
            if tid is None: reasons.append('unconfirmed_tracker_detection')
            if det[4] < self.c['minimum_detection_confidence']: reasons.append('low_detection_confidence')
            if anchor < self.c['anchor_similarity_min']: reasons.append('immutable_anchor_mismatch')
            if anchor - neg < self.c['negative_margin_min']: reasons.append('initial_distractor_similarity')
            expected = self.last_box + self.velocity * min(gap, self.c['motion_grace_frames'])
            distance = float(np.linalg.norm((det[:2] + det[2:4] - expected[:2] - expected[2:]) / 2))
            diag = max(float(np.linalg.norm(self.last_box[2:] - self.last_box[:2])), 1.)
            size = np.maximum(det[2:4] - det[:2], 1.) / np.maximum(self.last_box[2:] - self.last_box[:2], 1.)
            size_ratio = float(max(size.max(), (1 / size).max()))
            if gap <= self.c['motion_grace_frames']:
                if distance / diag > self.c['max_center_motion_diagonals']: reasons.append('motion_inconsistent')
                if size_ratio > self.c['max_size_ratio']: reasons.append('size_inconsistent')
            reacquiring = gap > 1 or tid != self.last_id
            if reacquiring and anchor < self.c['reacquire_similarity_min']: reasons.append('reacquire_appearance_insufficient')
            overlap = max((overlap_fraction(det[:4], other[:4]) for j, other in enumerate(dets) if j != i), default=0.)
            evaluated.append({'detection_index': i, 'track_id': tid, 'anchor_similarity': anchor,
                'gallery_similarity': gallery, 'negative_similarity': neg, 'negative_margin': anchor - neg,
                'score': score, 'motion_distance_diagonals': distance / diag, 'size_ratio': size_ratio,
                'other_person_overlap': overlap, 'reacquiring': reacquiring, 'reasons': reasons})
        eligible = sorted((e for e in evaluated if not e['reasons']), key=lambda e: e['score'], reverse=True)
        reason, state = 'no_identity_consistent_track', 'occluded' if gap <= self.c['max_prediction_frames'] else 'lost'
        if eligible:
            best = eligible[0]
            rivals = [e['score'] for e in evaluated if e['detection_index'] != best['detection_index'] and 'score' in e]
            margin = best['score'] - max(rivals, default=-1.)
            best['candidate_margin'] = margin
            if margin < self.c['candidate_margin_min']:
                reason, state = 'ambiguous_candidate_margin', 'ambiguous'
                self.pending_count, self.pending_id = 0, None
            else:
                if best['reacquiring']:
                    tid = best['track_id']
                    self.pending_count = self.pending_count + 1 if self.pending_id == tid else 1
                    self.pending_id = tid
                    if self.pending_count < self.c['reacquire_confirmation_frames']:
                        reason, state = 'reacquisition_confirmation_pending', 'ambiguous'
                    else:
                        self.recoveries += 1
                        return self._accept(frame, dets, feats, track_ids, best['detection_index'], evaluated, 'reacquired', False)
                else:
                    return self._accept(frame, dets, feats, track_ids, best['detection_index'], evaluated, 'tracked', True)
        else:
            self.pending_count, self.pending_id = 0, None
        predicted = (self.last_box + self.velocity * gap).tolist() if gap <= self.c['max_prediction_frames'] else None
        return {'input_frame': frame, 'target_identity': 'explicit-seed-target', 'state': state,
            'valid': False, 'observed': False, 'bbox_xyxy': None, 'display_bbox_xyxy': predicted,
            'display_box_kind': 'bounded_prediction' if predicted is not None else 'none',
            'track_id': None, 'last_observed_track_id': self.last_id, 'frames_since_observation': gap,
            'reason': reason, 'candidates': evaluated, 'template_updated': False,
            'template_updates_total': self.template_updates, 'manual_recovery_hints': 0}

    def _accept(self, frame, dets, feats, ids, index, evaluated, state, can_update):
        box = dets[index, :4].copy()
        if self.last_box is not None:
            instant = (box - self.last_box) / max(frame - self.last_frame, 1)
            self.velocity = .5 * self.velocity + .5 * instant
        self.last_box, self.last_frame, self.last_id = box, frame, ids[index]
        self.pending_count, self.pending_id = 0, None
        updated = False
        e = next((x for x in evaluated if x['detection_index'] == index), None)
        if can_update and e and frame - self.last_template_frame >= self.c['template_update_interval_frames']:
            safe = (e['anchor_similarity'] >= self.c['template_anchor_similarity_min'] and
                dets[index, 4] >= self.c['template_detection_confidence_min'] and
                e['negative_margin'] >= self.c['template_negative_margin_min'] and
                e['other_person_overlap'] <= self.c['template_max_other_overlap'])
            if safe:
                self.gallery.append(feats[index].copy())
                self.gallery = [self.gallery[0]] + self.gallery[1:][-(self.c['template_gallery_max'] - 1):]
                self.last_template_frame = frame
                self.template_updates += 1
                updated = True
        return {'input_frame': frame, 'target_identity': 'explicit-seed-target', 'state': state,
            'valid': True, 'observed': True, 'bbox_xyxy': box.tolist(), 'display_bbox_xyxy': box.tolist(),
            'display_box_kind': 'observed', 'track_id': ids[index], 'detection_index': index,
            'detection_confidence': float(dets[index, 4]), 'frames_since_observation': 0,
            'reason': state, 'candidates': evaluated, 'template_updated': updated,
            'template_updates_total': self.template_updates, 'manual_recovery_hints': 0}
