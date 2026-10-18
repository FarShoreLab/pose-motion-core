"""Live-only OpenSim stage. The client supplies states, never replacement positions."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from opensim_ik import HumanIK, calibrate, fit_record

IK_SOURCE_SHA256 = hashlib.sha256((ROOT / 'src/opensim_ik.py').read_bytes()).hexdigest()

class LiveIK:
    def __init__(self, audit_dir):
        self.stream_key = None
        self.records = []
        self.model = None
        self.calibration = None
        self.last_epoch = None
        self.count = 0
        audit_dir.mkdir(exist_ok=True)
        self.audit_path = audit_dir / ('immutable-live-' + time.strftime('%Y%m%dT%H%M%S') + '-' + str(time.monotonic_ns()) + '.jsonl')
        self.audit = self.audit_path.open('x', buffering=1)
        self.last_raw = None
        self.last_fit_identity = None

    def remember_raw(self, raw):
        # Serialize before any derived filter or fit is attached. No coordinates overwritten.
        self.last_raw = copy.deepcopy(raw)
        self.audit.write(json.dumps({'kind':'raw_mediapipe_output','data':raw}, allow_nan=False, separators=(',', ':')) + '\n')

    def fit(self, body):
        started = time.perf_counter()
        raw = self.last_raw
        if raw is None or any(body.get(k) != raw.get(k) for k in ('frame_id', 'epoch', 'source_pts_ms')):
            raise ValueError('IK requires the exact latest live inference identity')
        identity = (raw['epoch'], raw['frame_id'])
        if identity == self.last_fit_identity:
            raise ValueError('A live inference can be fitted only once')
        states = body.get('observation_states')
        if not isinstance(states, list) or len(states) != 33 or any(s not in ('measured','uncertain','lost') for s in states):
            raise ValueError('Expected 33 unchanged v5.2 observation states')
        if not isinstance(body.get('clip'),str) or len(body['clip'])>128:
            raise ValueError('Invalid clip')
        stream_key = (raw['epoch'].rsplit(':',1)[0], body['clip'])
        if stream_key != self.stream_key:
            self.stream_key = stream_key
            self.records = []
            self.model = None
            self.calibration = None
            self.last_epoch = None
            self.count = 0
        if raw['epoch'] != self.last_epoch and self.model is not None:
            # Loops retain calibrated lengths, but no temporal coordinate prior crosses a cut.
            self.model.last_q = None
            self.model.fk(self.model.initial_q)
        self.last_epoch = raw['epoch']
        self.last_fit_identity = identity
        self.count += 1
        record = {'frame_id':raw['frame_id'], 'epoch':raw['epoch'], 'clip':body['clip'],
                  'source_pts_ms':raw['source_pts_ms'],
                  'source_unwrapped_pts_ms':body.get('source_unwrapped_pts_ms', raw['source_pts_ms']),
                  'landmarks':copy.deepcopy(raw['landmarks'][0] if raw['landmarks'] else []),
                  'world_landmarks':copy.deepcopy(raw['world_landmarks'][0] if raw['world_landmarks'] else []),
                  'filtered_observation':{'states':list(states)},
                  'synthetic_missing_joints':list(body.get('synthetic_missing_joints', []))}
        init_ms = 0.0
        if len(self.records) < 30:
            self.records.append(record)
            output = {'status':'calibrating','world':[None]*33,'states':['unmodelled']*33,
                      'observation_states':list(states),'solver_ms':0.0}
            if len(self.records) == 30:
                init_start = time.perf_counter()
                lengths, quality = calibrate(self.records, max_frames=30)
                self.model = HumanIK(lengths, temporal_weight=0.0)
                self.calibration = {'lengths_m':lengths,'quality':quality,'locked':True,
                    'frames':[{'frame_id':r['frame_id'],'epoch':r['epoch'],'source_pts_ms':r['source_pts_ms']} for r in self.records],
                    'policy':'median of eligible samples from first 30 LIVE outputs, fixed for this source; fallback lengths disclosed',
                    'model_source_sha256':IK_SOURCE_SHA256,'dof':len(self.model.coords),
                    'coordinates':self.model.coord_specs,'temporal_weight':0.0}
                init_ms = (time.perf_counter()-init_start)*1000
        else:
            output = fit_record(self.model, record)
        output.update(frame_id=raw['frame_id'],epoch=raw['epoch'],source_pts_ms=raw['source_pts_ms'],
            source_unwrapped_pts_ms=record['source_unwrapped_pts_ms'],
            input_sha256=raw['input_sha256'],live_output_index=self.count,
            calibration_count=len(self.records),calibration_target=30,
            calibration=self.calibration if self.count==30 else None,
            calibration_locked=self.calibration is not None,
            calibration_fallback_count=sum(v['fallback'] for v in self.calibration['quality'].values()) if self.calibration else None,
            model_initialization_ms=init_ms,model_source_sha256=IK_SOURCE_SHA256,
            new_measurement=False,ground_truth_validated=False,
            model_notice='Simplified 25-DoF OpenSim constrained fit; fitted/inferred coordinates are not new observations or verified 3D truth')
        output['stage_processing_ms']=(time.perf_counter()-started)*1000
        self.audit.write(json.dumps({'kind':'derived_live_ik','data':output},allow_nan=False,separators=(',',':'))+'\n')
        return output

    def close(self):
        self.audit.close()
