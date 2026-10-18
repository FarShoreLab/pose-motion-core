"""One frozen tracking attempt, retaining all detections, embeddings and decisions."""
from isolation import BASE, ROOT
import argparse
import ast
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
from types import SimpleNamespace

import av
import numpy as np
import psutil
import torch
import ultralytics
from ultralytics import YOLO
from ultralytics.trackers.bot_sort import BOTSORT
from target_policy_v2 import GalleryTargetPolicy as TargetPolicy


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AuditedEncoder:
    def __init__(self, encoder):
        self.real = encoder
        self.cache = {}
        self.model_calls = 0
        self.model_seconds = 0.
        self.tracker_calls = 0
        self.vectors = 0

    @staticmethod
    def key(row):
        return tuple(np.rint(np.asarray(row[:4], dtype=np.float64) * 1000).astype(np.int64))

    def prepare(self, image, boxes):
        self.cache = {}
        if not len(boxes): return []
        start = time.perf_counter()
        result = self.real(image, boxes)
        self.model_seconds += time.perf_counter() - start
        self.model_calls += 1
        self.vectors += len(result)
        for box, feature in zip(boxes, result):
            assert feature is not None and np.isfinite(feature).all(), 'Invalid ReID vector'
            self.cache[self.key(box)] = np.asarray(feature, dtype=np.float32)
        return result

    def __call__(self, image, boxes):
        self.tracker_calls += 1
        return [self.cache[self.key(box)].copy() for box in boxes]


class AuditedBoTSORT(BOTSORT):
    def __init__(self, args):
        self.appearance_cost_calls = 0
        self.appearance_cost_pairs = 0
        super().__init__(args)

    def get_dists(self, tracks, detections):
        if tracks and detections and self.args.with_reid and self.encoder is not None:
            assert all(t.smooth_feat is not None for t in tracks)
            assert all(d.curr_feat is not None for d in detections)
            self.appearance_cost_calls += 1
            self.appearance_cost_pairs += len(tracks) * len(detections)
        return super().get_dists(tracks, detections)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clip', default='r2_occlusion_basketball')
    parser.add_argument('--attempt', default='basketball-botsort-v1')
    parser.add_argument("--policy", required=True)
    args = parser.parse_args()
    config_path = Path(__file__).with_name(args.policy)
    config = json.loads(config_path.read_text())
    assert ultralytics.__version__ == config['ultralytics_version']
    assert args.clip == config['initialization']['clip'], 'Use an explicitly reviewed initialization for another clip'
    out = ROOT / 'outputs' / args.attempt
    out.mkdir(parents=True, exist_ok=False)
    source = BASE / 'outputs' / args.clip
    mapping = list(csv.DictReader((source / 'frame-map.csv').open(encoding='utf-8')))
    input_manifest = json.loads((source / 'input-manifest.json').read_text(encoding='utf-8'))
    input_sha = sha(source / 'input_30fps.mp4')
    assert input_sha == input_manifest['input_sha256']
    tracked_source = {str(p.name): sha(p) for p in Path(__file__).parent.glob('*.py')}
    manifest = {'attempt': args.attempt, 'clip': args.clip, 'policy': config,
        'policy_sha256': sha(config_path), 'code_sha256': tracked_source,
        'input_sha256': input_sha, 'input_manifest': input_manifest,
        'initial_visual_seed_count': 1, 'additional_keyframe_hints': 0,
        'evaluation': 'fixed policy holdout tracking regression; assistant visual review to follow',
        'policy_tuned_on_this_clip': False,
        'versions': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}}
    (out / 'run-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (out / 'policy-frozen.json').write_bytes(config_path.read_bytes())
    torch.set_num_threads(4)
    assert torch.cuda.is_available()
    process = psutil.Process()
    started = time.perf_counter()
    detector = YOLO(str(BASE / 'assets/checkpoints/yolo/yolov8x.pt'))
    tracker_args = SimpleNamespace(**{k: config[k] for k in ['track_high_thresh', 'track_low_thresh',
        'new_track_thresh', 'track_buffer', 'match_thresh', 'fuse_score', 'gmc_method',
        'proximity_thresh', 'appearance_thresh']}, with_reid=True,
        model=str(ROOT / 'assets/yolo26n-reid.onnx'), device='cpu')
    tracker = AuditedBoTSORT(tracker_args)
    assert tracker.encoder is not None and type(tracker.encoder).__name__ == 'ReID'
    # Exported ONNX has dynamic spatial axes; use its declared training/export size,
    # not the generic ReID helper's 224px fallback. Preserve earlier run separately.
    session = tracker.encoder.model.session
    declared_size = ast.literal_eval(session.get_modelmeta().custom_metadata_map['imgsz'])
    assert len(declared_size) == 2 and all(isinstance(x, int) and x > 0 for x in declared_size)
    helper_default_size = tracker.encoder.imgsz
    tracker.encoder.imgsz = tuple(declared_size)
    encoder = AuditedEncoder(tracker.encoder)
    tracker.encoder = encoder
    ort_session = encoder.real.model.session
    manifest['encoder_runtime'] = {'class': type(encoder.real).__name__, 'providers': ort_session.get_providers(),
        'input_shape': ort_session.get_inputs()[0].shape,
        'output_shapes': [o.shape for o in ort_session.get_outputs()],
        'metadata': ort_session.get_modelmeta().custom_metadata_map,
        'helper_default_imgsz': helper_default_size,
        'effective_imgsz': encoder.real.imgsz,
        'weight_sha256': sha(ROOT / 'assets/yolo26n-reid.onnx')}
    (out / 'run-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    load_seconds = time.perf_counter() - started
    guard = TargetPolicy(config)
    records, all_features, offsets, resources = [], [], [0], []
    detection_seconds = 0.
    association_seconds = 0.
    guard_seconds = 0.
    decode_seconds = 0.
    loop_started = time.perf_counter()
    with (out / 'frame-decisions.jsonl').open('w', encoding='utf-8') as log, av.open(str(source / 'input_30fps.mp4')) as container:
        for frame_index, frame in enumerate(container.decode(video=0)):
            t = time.perf_counter()
            bgr = frame.to_ndarray(format='bgr24')
            decode_seconds += time.perf_counter() - t
            t = time.perf_counter()
            result = detector.predict(bgr, conf=config['detector_confidence'], iou=config['detector_iou'],
                classes=[0], device=0, imgsz=640, verbose=False, save=False)[0]
            torch.cuda.synchronize()
            detection_seconds += time.perf_counter() - t
            boxes = result.boxes.cpu().numpy()
            features = encoder.prepare(bgr, boxes.xywh)
            t = time.perf_counter()
            tracks = tracker.update(boxes, bgr)
            association_seconds += time.perf_counter() - t
            track_ids = {int(row[-1]): int(row[4]) for row in tracks}
            dets = np.concatenate([boxes.xyxy, boxes.conf[:, None], boxes.cls[:, None]], axis=1)
            t = time.perf_counter()
            decision = guard.step(frame_index, dets, features, track_ids)
            guard_seconds += time.perf_counter() - t
            decision.update({'input_timestamp_ms': int(mapping[frame_index]['input_timestamp_ms']),
                'source_frame': int(mapping[frame_index]['source_frame']),
                'source_pts_seconds': float(mapping[frame_index]['source_seconds']),
                'raw_detections_xyxy_conf_cls': dets.tolist(), 'botsort_tracks_xyxy_id_conf_cls_detidx': tracks.tolist(),
                'embedding_offset': offsets[-1], 'embedding_count': len(features)})
            records.append(decision)
            log.write(json.dumps(decision) + '\n')
            log.flush()
            all_features.extend(features)
            offsets.append(len(all_features))
            resources.append({'frame': frame_index, 'rss_bytes': process.memory_info().rss,
                'torch_allocated_bytes': torch.cuda.memory_allocated(), 'elapsed_s': time.perf_counter() - loop_started})
            if frame_index % 15 == 0:
                print(json.dumps({'frame': frame_index, 'total': len(mapping), 'state': decision['state'],
                    'track_id': decision['track_id'], 'valid': decision['valid'], 'seconds': round(time.perf_counter() - loop_started, 2)}), flush=True)
    assert len(records) == len(mapping)
    assert encoder.model_calls > 0 and encoder.tracker_calls > 0 and tracker.appearance_cost_pairs > 0
    np.savez_compressed(out / 'detection-embeddings.npz', embeddings=np.asarray(all_features, dtype=np.float32),
        offsets=np.asarray(offsets, dtype=np.int64))
    summary = {'frames': len(records), 'observed_valid_frames': sum(r['valid'] for r in records),
        'states': {s: sum(r['state'] == s for r in records) for s in sorted({r['state'] for r in records})},
        'identity_accuracy': 'PENDING per-frame visual review; validity is not correctness',
        'initial_visual_seed_count': 1, 'additional_keyframe_hints': 0, 'manual_tracking_corrections': 0,
        'template_updates': guard.template_updates, 'reacquisitions': guard.recoveries,
        'model_load_seconds': load_seconds, 'loop_seconds': time.perf_counter() - loop_started,
        'detector_seconds': detection_seconds, 'reid_seconds': encoder.model_seconds,
        'association_gmc_seconds': association_seconds, 'identity_guard_seconds': guard_seconds,
        'decode_conversion_seconds': decode_seconds, 'whole_run_seconds': time.perf_counter() - started,
        'reid_model_forward_calls': encoder.model_calls, 'official_tracker_encoder_calls': encoder.tracker_calls,
        'reid_embedding_vectors': encoder.vectors, 'official_appearance_cost_calls': tracker.appearance_cost_calls,
        'official_appearance_cost_pairs': tracker.appearance_cost_pairs,
        'peak_rss_sampled_bytes': max(x['rss_bytes'] for x in resources),
        'cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated(), 'inference_device': 'YOLO CUDA; official ReID ONNX CPU',
        'input_sha256_after': sha(source / 'input_30fps.mp4'), 'real_time_claim': False}
    (out / 'tracking-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (out / 'resources.json').write_text(json.dumps(resources), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
