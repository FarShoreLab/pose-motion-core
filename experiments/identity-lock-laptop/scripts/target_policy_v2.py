"""Conservative gallery-based target identity layer, evaluated independently of numeric IDs.

V1 confused a fixed first-view cosine with person identity and made every rejection
enter an even stricter first-view recovery gate. V2 uses a protected nearest-neighbor
gallery, as in appearance-based MOT, and applies the same evidence to continuation
and short-gap recovery. All rejected observations remain invalid.
"""
import numpy as np
from target_policy import TargetPolicy, unit, iou, overlap_fraction


class GalleryTargetPolicy(TargetPolicy):
    def step(self, frame, detections, features, track_ids):
        dets = np.asarray(detections, dtype=float).reshape(-1, 6)
        feats = [unit(f) if f is not None else None for f in features]
        if self.anchor is None:
            return super().step(frame, detections, features, track_ids)
        gap = frame - self.last_frame
        evaluated = []
        for i, (det, feat) in enumerate(zip(dets, feats)):
            if feat is None:
                evaluated.append({'detection_index': i, 'reasons': ['missing_embedding']})
                continue
            anchor = float(feat @ self.anchor)
            gallery = max(float(feat @ g) for g in self.gallery)
            negative = max((float(feat @ g) for g in self.negatives), default=-1.)
            tid = track_ids.get(i)
            expected = self.last_box + self.velocity * min(gap, self.c['motion_grace_frames'])
            diagonal = max(float(np.linalg.norm(self.last_box[2:] - self.last_box[:2])), 1.)
            distance = float(np.linalg.norm((det[:2] + det[2:4] - expected[:2] - expected[2:]) / 2)) / diagonal
            size = np.maximum(det[2:4] - det[:2], 1.) / np.maximum(self.last_box[2:] - self.last_box[:2], 1.)
            size_ratio = float(max(size.max(), (1 / size).max()))
            # Low-confidence duplicate proposals must not cause template contamination
            # decisions; high-confidence, physically distinct people do.
            overlap = max((overlap_fraction(det[:4], other[:4]) for j, other in enumerate(dets)
                if j != i and other[4] >= self.c['overlap_detection_confidence'] and
                not (iou(det[:4], other[:4]) >= .7 and float(feat @ feats[j]) >= .8)), default=0.)
            reacquiring = gap > 1 or tid != self.last_id
            reasons = []
            if tid is None: reasons.append('unconfirmed_tracker_detection')
            if det[4] < self.c['minimum_detection_confidence']: reasons.append('low_detection_confidence')
            if anchor < self.c['anchor_similarity_floor']: reasons.append('immutable_anchor_floor')
            required = self.c['long_gap_similarity_min'] if gap > self.c['long_gap_frames'] else self.c['gallery_similarity_min']
            if gallery < required: reasons.append('trusted_gallery_mismatch')
            if gallery - negative < self.c['negative_margin_min']: reasons.append('distractor_similarity')
            # Apply center-motion gating through the short gap; after long_gap_frames
            # it is disabled, while size and appearance checks remain active.
            if gap <= self.c['long_gap_frames'] and distance > self.c['max_center_motion_diagonals']:
                reasons.append('motion_inconsistent')
            if size_ratio > self.c['max_size_ratio']: reasons.append('size_inconsistent')
            if overlap > self.c['maximum_observation_overlap']: reasons.append('overlapping_people_ambiguous')
            evaluated.append({'detection_index': i, 'track_id': tid, 'anchor_similarity': anchor,
                'gallery_similarity': gallery, 'negative_similarity': negative,
                'negative_margin': gallery-negative, 'score': .9*gallery + .1*anchor,
                'motion_distance_diagonals': distance, 'size_ratio': size_ratio,
                'other_person_overlap': overlap, 'reacquiring': reacquiring, 'reasons': reasons})
        eligible = sorted((e for e in evaluated if not e['reasons']), key=lambda e:e['score'], reverse=True)
        state = 'occluded' if gap <= self.c['max_prediction_frames'] else 'lost'
        reason = 'no_identity_consistent_track'
        if eligible:
            best = eligible[0]
            index = best['detection_index']
            rivals = [e['score'] for e in evaluated if 'score' in e and e['detection_index'] != index
                and dets[e['detection_index'],4] >= self.c['minimum_detection_confidence']
                and not (iou(dets[index,:4],dets[e['detection_index'],:4]) >= .7 and
                         float(feats[index] @ feats[e['detection_index']]) >= .8)]
            best['candidate_margin'] = best['score'] - max(rivals, default=-1.)
            if best['candidate_margin'] < self.c['candidate_margin_min']:
                state, reason = 'ambiguous', 'ambiguous_candidate_margin'
                self.pending_id, self.pending_count = None, 0
            elif best['reacquiring']:
                tid = best['track_id']
                self.pending_count = self.pending_count + 1 if self.pending_id == tid else 1
                self.pending_id = tid
                if self.pending_count >= self.c['reacquire_confirmation_frames']:
                    self.recoveries += 1
                    return self._accept(frame, dets, feats, track_ids, index, evaluated, 'reacquired', False)
                state, reason = 'ambiguous', 'reacquisition_confirmation_pending'
            else:
                return self._accept(frame, dets, feats, track_ids, index, evaluated, 'tracked', True)
        else:
            self.pending_id, self.pending_count = None, 0
            if any('overlapping_people_ambiguous' in e['reasons'] and e.get('gallery_similarity',0) >= self.c['gallery_similarity_min'] for e in evaluated):
                state, reason = 'ambiguous', 'overlapping_people_ambiguous'
        prediction = (self.last_box + self.velocity * gap).tolist() if gap <= self.c['max_prediction_frames'] else None
        return {'input_frame':frame,'target_identity':'explicit-seed-target','state':state,
            'valid':False,'observed':False,'bbox_xyxy':None,'display_bbox_xyxy':prediction,
            'display_box_kind':'bounded_prediction' if prediction else 'none','track_id':None,
            'last_observed_track_id':self.last_id,'frames_since_observation':gap,'reason':reason,
            'candidates':evaluated,'template_updated':False,'template_updates_total':self.template_updates,
            'manual_recovery_hints':0}

    def _accept(self, frame, dets, feats, ids, index, evaluated, state, can_update):
        # Parent performs motion update and emits the common valid/invalid schema.
        result = super()._accept(frame,dets,feats,ids,index,evaluated,state,False)
        e = next((e for e in evaluated if e['detection_index']==index),None)
        if can_update and e:
            safe = (e['anchor_similarity'] >= self.c['template_anchor_similarity_min'] and
                    e['gallery_similarity'] >= self.c['template_gallery_similarity_min'] and
                    e['negative_margin'] >= self.c['template_negative_margin_min'] and
                    e.get('candidate_margin',0) >= self.c['template_candidate_margin_min'] and
                    e['other_person_overlap'] <= self.c['template_max_other_overlap'] and
                    dets[index,4] >= self.c['template_detection_confidence_min'])
            if safe and max(float(feats[index]@g) for g in self.gallery) < .995:
                self.gallery.append(feats[index].copy())
                self.gallery = [self.gallery[0]] + self.gallery[1:][-(self.c['template_gallery_max']-1):]
                self.template_updates += 1
                result['template_updated'] = True
                result['template_updates_total'] = self.template_updates
        return result
