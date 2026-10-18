"""Read-only model-output diagnostics; writes separate evidence without inference."""
from isolation import BASE, ROOT
import csv
import hashlib
import inspect
import json
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch
from ultralytics.utils.plotting import save_one_box
from ultralytics.trackers.utils.reid import ReID


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    attempt = ROOT / 'outputs/basketball-botsort-v1-model448'
    out = ROOT / 'diagnostics'
    out.mkdir(exist_ok=True)
    caches = []
    for name in ['basketball-botsort-v1-run2', 'basketball-botsort-v1-model448']:
        folder = ROOT / 'outputs' / name
        rows = [json.loads(x) for x in (folder / 'frame-decisions.jsonl').read_text().splitlines()]
        data = np.load(folder / 'detection-embeddings.npz', allow_pickle=False)
        feats, offsets = data['embeddings'], data['offsets']
        collisions = 0
        for i, row in enumerate(rows):
            det = np.asarray(row['raw_detections_xyxy_conf_cls'], dtype=np.float32).reshape(-1, 6)
            xywh = np.empty_like(det[:, :4]);xywh[:, :2] = (det[:, :2] + det[:, 2:4]) / 2;xywh[:, 2:] = det[:, 2:4] - det[:, :2]
            keys32 = [tuple(np.rint(x.astype(np.float64) * 1000).astype(np.int64)) for x in xywh]
            keys64 = [tuple(np.rint(x * 1000).astype(np.int64)) for x in xywh.astype(np.float64)]
            assert keys32 == keys64
            collisions += len(keys32) - len(set(keys32))
            assert offsets[i+1] - offsets[i] == len(det)
        norms = np.linalg.norm(feats, axis=1)
        assert np.isfinite(feats).all() and (norms > 0).all() and collisions == 0
        caches.append({'attempt': name, 'frames': len(rows), 'features_shape': list(feats.shape),
            'raw_feature_norm_min': float(norms.min()), 'raw_feature_norm_max': float(norms.max()),
            'integer_key_collisions': collisions, 'float32_float64_key_equivalence': True,
            'complete_detection_embedding_alignment': True,
            'files': {f: {'bytes': (folder/f).stat().st_size, 'sha256': digest(folder/f)}
                for f in ['frame-decisions.jsonl', 'detection-embeddings.npz', 'policy-frozen.json']}})
    assert caches[0]['files']['policy-frozen.json']['sha256'] == caches[1]['files']['policy-frozen.json']['sha256']
    (out / 'frozen-cache-verification.json').write_text(json.dumps(caches, indent=2), encoding='utf-8')
    rows = [json.loads(x) for x in (attempt / 'frame-decisions.jsonl').read_text().splitlines()]
    fields = ['frame', 'raw_track_id', 'det_index', 'bbox_xyxy', 'confidence', 'guard_state',
        'anchor_similarity', 'negative_margin', 'motion_distance_diagonals', 'other_person_overlap', 'reasons']
    with (out / 'candidate-gates-all-frames.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields);writer.writeheader()
        for row in rows:
            for c in row['candidates']:
                det = row['raw_detections_xyxy_conf_cls'][c['detection_index']]
                writer.writerow({'frame': row['input_frame'], 'raw_track_id': c.get('track_id'),
                    'det_index': c['detection_index'], 'bbox_xyxy': json.dumps(det[:4]), 'confidence': det[4],
                    'guard_state': row['state'], **{k: c.get(k) for k in fields[6:]}})
    source = BASE / 'outputs/r2_occlusion_basketball/input_30fps.mp4'
    select = [0, 3, 4, 5, 6, 8, 10]
    sheet = Image.new('RGB', (len(select)*240, 430), '#101820')
    draw = ImageDraw.Draw(sheet);font = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 14)
    details = []
    with av.open(str(source)) as container:
        for i, frame in enumerate(container.decode(video=0)):
            if i not in select: continue
            r = rows[i]
            target = next((t for t in r['botsort_tracks_xyxy_id_conf_cls_detidx'] if int(t[4]) == 2), None)
            assert target is not None
            det = np.array(r['raw_detections_xyxy_conf_cls'][int(target[-1])][:4], dtype=np.float32)
            bgr = frame.to_ndarray(format='bgr24')
            crop = save_one_box(torch.from_numpy(det), bgr, save=False, BGR=True)
            rgb = np.ascontiguousarray(crop[..., ::-1])
            col = select.index(i)*240
            image = Image.fromarray(rgb);image.thumbnail((230, 360))
            sheet.paste(image, (col + 5, 60))
            candidate = next((c for c in r['candidates'] if c.get('track_id') == 2), {})
            sim = candidate.get('anchor_similarity', 1.)
            draw.text((col+5, 5), f'Frame {i} / ID 2 / {r["state"]}', fill='white', font=font)
            draw.text((col+5, 25), f'anchor cosine: {sim:.3f}', fill='white', font=font)
            details.append({'frame': i, 'detection_bbox': det.tolist(), 'official_expanded_crop_shape': list(crop.shape),
                'rgb_float_input_range': [float(rgb.min()/255),float(rgb.max()/255)],
                'preprocessing': 'official save_one_box gain=1.02 pad=10; BGR->RGB; /255; bilinear resize to declared 448x448; float32',
                'normalization': 'raw encoder vector retained; target guard computes L2-normalized cosine; original anchor is immutable'})
    sheet.save(out / 'first-refusal-official-reid-crops.png')
    checks = {'crop_review': details, 'official_ReID_source_sha256': hashlib.sha256(inspect.getsource(ReID).encode()).hexdigest(),
        'inference_executed': False, 'policy_changed': False,
        'first_refusal_224': 'frame 5: raw ID2 remains tracked; motion and negative margin pass, anchor cosine 0.670<0.700 causes rejection; subsequent 0.780 reacquisition requirement blocks recovery',
        'model_metadata_size_correction': '224 generic dynamic-size fallback -> declared 448; separate preserved full runs; same policy hash'}
    (out / 'preprocessing-and-first-refusal-audit.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    print(json.dumps({'cache_checks': caches, 'diagnostics': str(out)}, indent=2))


if __name__ == '__main__': main()
