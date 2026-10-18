#!/usr/bin/env python3
"""HTTP contract smoke test on a few selected frames. NOT realtime evidence."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
import aiohttp
import cv2

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8766'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / 'pose-v5'

def selected_frame(filename, source_ms):
    cap = cv2.VideoCapture(str(ROOT / 'assets/videos' / filename))
    fps = cap.get(cv2.CAP_PROP_FPS)
    index = round(source_ms * fps / 1000)
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, img = cap.read()
    cap.release()
    assert ok
    height, width = img.shape[:2]
    img = cv2.resize(img, (round(width * 512 / max(width,height)), round(height * 512 / max(width,height))))
    ok, encoded = cv2.imencode('.png', img)
    assert ok
    return encoded.tobytes(), index / fps * 1000, fps

async def main():
    report = {'scope': 'HTTP contract and selected-frame functionality only, not realtime playback', 'checks': []}
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE + '/health') as res:
            health = await res.json()
            assert res.status == 200 and health['ok'] and health['delegate'] == 'CPU'
            report['health'] = health
        async with session.get(BASE + '/assets/videos/smoke-google-squats-5fps.mp4', headers={'Range':'bytes=0-1023'}) as res:
            body = await res.read()
            assert res.status == 206 and len(body) == 1024
            report['checks'].append({'range': True, 'cross_origin_isolation': res.headers.get('Cross-Origin-Embedder-Policy') == 'require-corp'})
        async def submit(body, meta):
            start = time.monotonic_ns()
            async with session.post(BASE+'/infer', params=meta, data=body, headers={'Content-Type':'image/png'}) as res:
                output = await res.json()
                rtt = (time.monotonic_ns()-start)/1e6
                assert all(output[k] == (int(v) if k=='frame_id' else float(v) if k in ('source_pts_ms','source_fps') else v) for k,v in meta.items()) if res.status == 200 else True
                if res.status == 200:
                    assert output['input_sha256'] == hashlib.sha256(body).hexdigest()
                    assert output['inference_ms'] > 0
                    assert output['backend_total_ms'] >= output['inference_ms']
                return res.status, output, rtt
        for i, (filename, at_ms) in enumerate([('smoke-google-squats-5fps.mp4', 0),('smoke-google-squats-5fps.mp4', 200),('intel-worker-zone-detection.mp4', 10000)]):
            body, pts, fps = selected_frame(filename, at_ms)
            meta = {'frame_id':str(i),'epoch':'api-smoke-google' if i < 2 else 'api-smoke-intel','source_pts_ms':str(pts),'source_fps':str(fps)}
            status, result, rtt = await submit(body, meta)
            assert status == 200, result
            if i < 2:
                assert [len(x) for x in result['world_landmarks']] == [33]
            report['checks'].append({'filename': filename, 'source_pts_ms':pts, 'status':status, 'world_landmark_counts':[len(p) for p in result['world_landmarks']], 'client_http_rtt_ms':rtt, **{k:result[k] for k in ['inference_ms','backend_decode_ms','backend_init_ms','backend_total_ms','input_sha256']}})
            if i == 1:
                duplicate_status, duplicate, _ = await submit(body, meta)
                assert duplicate_status == 400 and duplicate['error'] == 'invalid_frame'
                report['checks'].append({'duplicate_pts_rejected':True})
        body, pts, fps = selected_frame('smoke-google-squats-5fps.mp4', 400)
        meta = {'frame_id':'100','epoch':'api-busy-check','source_pts_ms':str(pts),'source_fps':str(fps)}
        concurrent = await asyncio.gather(submit(body, meta), submit(body, meta))
        statuses = sorted(x[0] for x in concurrent)
        assert statuses == [200,429], statuses
        report['checks'].append({'concurrent_request_statuses': statuses, 'no_queue_busy_reject':True})
        async with session.post(BASE+'/infer', params={**meta,'epoch':'api-invalid-image'},data=b'not an image',headers={'Content-Type':'image/png'}) as res:
            result = await res.json()
            assert res.status == 400 and result['error'] == 'invalid_frame'
            report['checks'].append({'invalid_image_rejected':True})
    report['passed'] = True
    (HERE / 'api-test-results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

asyncio.run(main())
