#!/usr/bin/env python3
"""GL-free CPU PoseLandmarker HTTP endpoint for live browser-submitted frames.

No video is read, decoded, or precomputed by this server. Each POST /infer contains
exactly the currently captured PNG or JPEG. Monotonic durations stay server-local.
"""
from __future__ import annotations
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

# Bound image decoder allocations before importing OpenCV.
os.environ.setdefault('OPENCV_IO_MAX_IMAGE_WIDTH', '1920')
os.environ.setdefault('OPENCV_IO_MAX_IMAGE_HEIGHT', '1920')
os.environ.setdefault('OPENCV_IO_MAX_IMAGE_PIXELS', str(1920 * 1920))
import cv2
import mediapipe as mp
import numpy as np
from aiohttp import web
from epoch_clock import EpochClock

EPOCH_POLICY = "cold"
MAX_FRAME_BYTES = 2 * 1024 * 1024
MAX_RESULTS_BYTES = 64 * 1024 * 1024

HERE = Path(__file__).resolve().parent
BACKEND_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EPOCH_CLOCK_SOURCE_SHA256 = hashlib.sha256((HERE / 'epoch_clock.py').read_bytes()).hexdigest()
ROOT = HERE.parent / 'pose-v52'
MODEL = ROOT / 'assets/pose_landmarker_lite.task'
EXPECTED_MODEL_SHA256 = '59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a'
MODEL_SHA256 = hashlib.sha256(MODEL.read_bytes()).hexdigest()
RUNTIME_OPTIONS = {'num_poses': 1, 'min_pose_detection_confidence': 0.5, 'min_pose_presence_confidence': 0.5, 'min_tracking_confidence': 0.5, 'output_segmentation_masks': False}
if MODEL_SHA256 != EXPECTED_MODEL_SHA256:
    raise RuntimeError('The local model differs from the audited lite.task')


def ms_since(t: int) -> float:
    return (time.monotonic_ns() - t) / 1_000_000


def packed(poses):
    return [[{'x': p.x, 'y': p.y, 'z': p.z, 'visibility': p.visibility, 'presence': p.presence} for p in pose] for pose in poses]


class CpuBackend:
    """Called only on one executor thread. One epoch owns one VIDEO tracker."""
    def __init__(self):
        self.model = None
        self.epoch = None
        self.clock = EpochClock(EPOCH_POLICY)
        self.roi_history_retained = False
        self.last_timestamp_ms = -1
        self.calls = 0
        self.initialization_ms = self.create_model()

    def create_model(self):
        started = time.monotonic_ns()
        close_started = time.monotonic_ns()
        if self.model is not None:
            self.model.close()
        self.last_close_ms = ms_since(close_started)
        create_started = time.monotonic_ns()
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(MODEL),
                delegate=mp.tasks.BaseOptions.Delegate.CPU),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_segmentation_masks=False)
        self.model = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        self.last_create_ms = ms_since(create_started)
        self.last_timestamp_ms = -1
        return ms_since(started)

    def prepare(self, epoch: str):
        changed = self.epoch is not None and self.epoch != epoch
        reset = changed and EPOCH_POLICY == 'cold'
        reset_ms = self.create_model() if reset else 0.0
        if self.epoch != epoch:
            self.roi_history_retained = changed and EPOCH_POLICY == 'warm' and self.calls > 0
        self.clock.prepare(epoch)
        self.epoch = epoch
        return {'ok': True, 'epoch': epoch, 'epoch_changed': changed,
                'epoch_policy': EPOCH_POLICY, 'tracker_reset': reset,
                'model_reused_across_context': self.roi_history_retained,
                'tracker_roi_history_retained': self.roi_history_retained,
                'backend_reset_ms': reset_ms,
                'backend_close_ms': self.last_close_ms if reset else 0.0,
                'backend_create_ms': self.last_create_ms if reset else 0.0,
                'backend_init_ms': reset_ms, 'inference_performed': False}

    def infer(self, data: bytes, meta: dict):
        total_start = time.monotonic_ns()
        prep = self.prepare(meta['epoch'])
        warm_epoch_first_frame = self.roi_history_retained and self.clock.last_source_ms is None
        clock = self.clock.map(meta['source_pts_ms'], meta['source_fps'])
        timestamp_ms = clock['model_timestamp_ms']
        init_ms = prep['backend_init_ms']
        tracker_reset = prep['tracker_reset']
        if timestamp_ms <= self.last_timestamp_ms:
            raise ValueError('source_pts_ms must increase within an epoch; use a new epoch after seek/loop/source change')
        decode_start = time.monotonic_ns()
        if meta.get('encoding') == 'rgba':
            width, height = meta['width'], meta['height']
            if len(data) != width * height * 4:
                raise ValueError('RGBA length does not match dimensions')
            rgba = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
            rgb = np.ascontiguousarray(rgba[:, :, :3])
        else:
            bgr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if bgr is None:
                raise ValueError('Body is not a valid PNG/JPEG image')
            height, width = bgr.shape[:2]
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if max(height, width) > 1920 or min(height, width) < 8:
            raise ValueError('Frame dimensions must be between 8 and 1920 pixels; send max-edge 512 for testing')
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        decode_ms = ms_since(decode_start)
        inference_start = time.monotonic_ns()
        result = self.model.detect_for_video(image, timestamp_ms)
        inference_ms = ms_since(inference_start)
        self.last_timestamp_ms = timestamp_ms
        self.clock.commit(meta['source_pts_ms'], timestamp_ms)
        self.calls += 1
        output = dict(meta,
            ok=True,
            backend='mediapipe-python-cpu',
            mediapipe_version=mp.__version__,
            delegate='CPU',
            running_mode='VIDEO',
            model_sha256=MODEL_SHA256,
            runtime_options=RUNTIME_OPTIONS,
            backend_sequence=self.calls,
            input_sha256=hashlib.sha256(data).hexdigest(),
            input_width=width,
            input_height=height,
            model_timestamp_ms=timestamp_ms,
            source_pts_rounded_ms=clock['source_pts_rounded_ms'],
            model_epoch_offset_ms=clock['model_epoch_offset_ms'],
            previous_model_timestamp_ms=clock['previous_model_timestamp_ms'],
            epoch_source_pts_start_ms=clock['epoch_source_pts_start_ms'],
            epoch_policy=EPOCH_POLICY,
            epoch_changed=prep['epoch_changed'],
            warm_epoch_first_frame=warm_epoch_first_frame,
            backend_source_sha256=BACKEND_SOURCE_SHA256,
            epoch_clock_source_sha256=EPOCH_CLOCK_SOURCE_SHA256,
            tracker_roi_history_retained=prep['tracker_roi_history_retained'],
            model_timestamp_rule='round(source_pts_ms) + model_epoch_offset_ms; warm epoch offset advances previous model time by one nominal source-frame interval',
            pose_output_cache_used=False,
            landmarks=packed(result.pose_landmarks),
            world_landmarks=packed(result.pose_world_landmarks),
            inference_ms=inference_ms,
            backend_decode_ms=decode_ms,
            backend_init_ms=init_ms,
            backend_reset_ms=init_ms,
            backend_close_ms=prep['backend_close_ms'],
            backend_create_ms=prep['backend_create_ms'],
            tracker_reset=tracker_reset,
            model_reused_across_context=prep['model_reused_across_context'])
        output['backend_processing_ms'] = ms_since(total_start)
        return output

    def close(self):
        if self.model is not None:
            self.model.close()
            self.model = None


def metadata(query):
    frame = query.get('frame_id', '')
    epoch = query.get('epoch', '')
    if not re.fullmatch(r'[0-9]{1,16}', frame):
        raise ValueError('frame_id must be a nonnegative integer')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', epoch):
        raise ValueError('epoch must be a 1-128 character stream identifier')
    pts = float(query['source_pts_ms'])
    fps = float(query['source_fps'])
    if not math.isfinite(pts) or pts < 0:
        raise ValueError('source_pts_ms must be finite and nonnegative')
    if not math.isfinite(fps) or fps <= 0 or fps > 240:
        raise ValueError('source_fps must be in (0, 240]')
    return {'frame_id': int(frame), 'epoch': epoch, 'source_pts_ms': pts, 'source_fps': fps}


@web.middleware
async def browser_headers(request, handler):
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = exc
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store'
    return response


async def health(request):
    backend = request.app['backend']
    return web.json_response({'ok': True, 'backend': 'mediapipe-python-cpu', 'mediapipe_version': mp.__version__, 'delegate': 'CPU', 'model_sha256': MODEL_SHA256, 'running_mode': 'VIDEO', 'runtime_options': RUNTIME_OPTIONS, 'initialization_ms': backend.initialization_ms, 'epoch_policy': EPOCH_POLICY, 'tracker_roi_history_retained': backend.roi_history_retained, 'backend_source_sha256': BACKEND_SOURCE_SHA256, 'epoch_clock_source_sha256': EPOCH_CLOCK_SOURCE_SHA256, 'calls': backend.calls, 'busy': request.app['busy'], 'frame_policy': 'one live submitted frame per inference; no video file reader'})


async def read_limited(request, limit):
    if request.content_length is not None and request.content_length > limit:
        raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=request.content_length)
    data = bytearray()
    async for chunk in request.content.iter_chunked(65536):
        data.extend(chunk)
        if len(data) > limit:
            raise web.HTTPRequestEntityTooLarge(max_size=limit, actual_size=len(data))
    return bytes(data)


async def infer(request):
    started = time.monotonic_ns()
    if request.app['busy']:
        return web.json_response({'ok': False, 'error': 'backend_busy', 'detail': 'Only one inference may be in flight. Drop new browser frames while busy; never queue.'}, status=429)
    request.app['busy'] = True
    try:
        if request.content_type not in ('image/png', 'image/jpeg', 'application/octet-stream'):
            raise ValueError('Content-Type must be image/png or image/jpeg')
        meta = metadata(request.query)
        if request.query.get('encoding') == 'rgba':
            width, height = int(request.query.get('width', 0)), int(request.query.get('height', 0))
            if not (8 <= width <= 512 and 8 <= height <= 512):
                raise ValueError('RGBA dimensions must be 8..512')
            meta.update(encoding='rgba', width=width, height=height)
        data = await read_limited(request, MAX_FRAME_BYTES)
        if not data:
            raise ValueError('Frame body is empty')
        loop = asyncio.get_running_loop()
        pending = loop.run_in_executor(request.app['executor'], request.app['backend'].infer, data, meta)
        try:
            result = await asyncio.shield(pending)
        except asyncio.CancelledError:
            # A disconnected caller does not make an active native inference free.
            # Keep backpressure until it actually finishes; never queue stale frames.
            await pending
            raise
        result['backend_total_ms'] = ms_since(started)
        response = web.json_response(result, dumps=lambda x: json.dumps(x, allow_nan=False, separators=(',', ':')))
        log = {k: v for k, v in result.items() if k not in ('landmarks','world_landmarks')}
        log['pose_count'] = len(result['world_landmarks'])
        log['world_landmark_counts'] = [len(p) for p in result['world_landmarks']]
        print(json.dumps(log, allow_nan=False), flush=True)
        return response
    except (ValueError, KeyError, cv2.error) as exc:
        return web.json_response({'ok': False, 'error': 'invalid_frame', 'detail': str(exc)}, status=400)
    finally:
        request.app['busy'] = False


async def prepare(request):
    # Optional setup before source playback. No frames are read or inferred here.
    started = time.monotonic_ns()
    epoch = request.query.get('epoch', '')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', epoch):
        return web.json_response({'ok': False, 'error': 'invalid_epoch'}, status=400)
    if request.app['busy']:
        return web.json_response({'ok': False, 'error': 'backend_busy'}, status=429)
    request.app['busy'] = True
    try:
        pending = asyncio.get_running_loop().run_in_executor(request.app['executor'], request.app['backend'].prepare, epoch)
        try:
            result = await asyncio.shield(pending)
        except asyncio.CancelledError:
            await pending
            raise
        result['backend_total_ms'] = ms_since(started)
        return web.json_response(result)
    finally:
        request.app['busy'] = False


async def save_results(request):
    raw = await read_limited(request, MAX_RESULTS_BYTES)
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise web.HTTPBadRequest(text='Invalid JSON result payload') from exc
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text='Result payload must be an object')
    name = ''.join(c for c in str(data.get('name', '')) if c.isalnum() or c in '-_')[:150]
    if not name or 'log' not in data:
        raise web.HTTPBadRequest(text='name and log are required')
    output = ROOT / 'results'
    output.mkdir(exist_ok=True)
    (output / f'{name}.json').write_text(json.dumps(data['log'], allow_nan=False))
    return web.Response(text='ok')


async def static(request):
    path = request.match_info['path']
    if not path:
        relative = Path('public/index.html')
    elif path.startswith(('node_modules/', 'assets/')):
        relative = Path(path)
    else:
        relative = Path('public') / path
    file = (ROOT / relative).resolve()
    if not file.is_relative_to(ROOT.resolve()) or not file.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(file)


async def startup(app):
    app['executor'] = ThreadPoolExecutor(max_workers=1, thread_name_prefix='pose-cpu')
    app['backend'] = await asyncio.get_running_loop().run_in_executor(app['executor'], CpuBackend)
    app['busy'] = False
    print(json.dumps({'ready': True, 'backend': 'mediapipe-python-cpu', 'epoch_policy': EPOCH_POLICY, 'backend_source_sha256': BACKEND_SOURCE_SHA256, 'epoch_clock_source_sha256': EPOCH_CLOCK_SOURCE_SHA256, 'model_sha256': MODEL_SHA256}), flush=True)


async def cleanup(app):
    await asyncio.get_running_loop().run_in_executor(app['executor'], app['backend'].close)
    app['executor'].shutdown(wait=True)


def make_app():
    app = web.Application(middlewares=[browser_headers], client_max_size=MAX_RESULTS_BYTES)
    app.router.add_get('/health', health)
    app.router.add_post('/infer', infer)
    app.router.add_post('/prepare', prepare)
    app.router.add_post('/save-results', save_results)
    app.router.add_get('/{path:.*}', static)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--epoch-policy', choices=('cold', 'warm'), default='cold', help='cold recreates model; warm retains tracking ROI history with a monotonic model clock')
    args = parser.parse_args()
    EPOCH_POLICY = args.epoch_policy
    web.run_app(make_app(), host=args.host, port=args.port, access_log=None)
