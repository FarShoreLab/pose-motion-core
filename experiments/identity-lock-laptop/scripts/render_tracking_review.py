"""Render an auditable replay and every-frame contact sheets; no model inference."""
from isolation import BASE, ROOT
import argparse
import json
import math
from pathlib import Path
import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch


FONT_PATH = r'C:\Windows\Fonts\arial.ttf'
FONT = ImageFont.truetype(FONT_PATH, 15)
SMALL = ImageFont.truetype(FONT_PATH, 13)
WHITE, YELLOW, MAGENTA, GREEN, CYAN, ORANGE = '#f4f7fa', '#ffd54f', '#ed6bf5', '#45ff8a', '#49cdf0', '#ff9f43'


def box(draw, b, label, color, width=3, offset=(0, 0), dashed=False):
    if b is None or not np.isfinite(b).all(): return
    x1, y1, x2, y2 = [float(v) for v in b]
    x1, y1, x2, y2 = max(0, min(639, x1)), max(0, min(367, y1)), max(0, min(639, x2)), max(0, min(367, y2))
    if x2 <= x1 or y2 <= y1: return
    x1, x2 = x1 + offset[0], x2 + offset[0]
    y1, y2 = y1 + offset[1], y2 + offset[1]
    if dashed:
        for x in range(round(x1), round(x2), 12):
            draw.line((x, y1, min(x + 7, x2), y1), fill=color, width=width)
            draw.line((x, y2, min(x + 7, x2), y2), fill=color, width=width)
        for y in range(round(y1), round(y2), 12):
            draw.line((x1, y, x1, min(y + 7, y2)), fill=color, width=width)
            draw.line((x2, y, x2, min(y + 7, y2)), fill=color, width=width)
    else:
        draw.rectangle((x1, y1, x2, y2), outline=color, width=width)
    if label:
        loc = (x1, max(offset[1], y1 - 18))
        textbox = draw.textbbox(loc, label, font=SMALL)
        draw.rectangle(textbox, fill='#101820')
        draw.text(loc, label, font=SMALL, fill=color)


def mp_box(points, width, height):
    good = points[np.isfinite(points).all(axis=1) & (points[:, 3] >= .5)]
    if len(good) < 4: return None
    xy = good[:, :2] * [width, height]
    return [*xy.min(axis=0), *xy.max(axis=0)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', default='basketball-botsort-v1-run2')
    a = p.parse_args()
    out = ROOT / 'outputs' / a.attempt
    records = [json.loads(x) for x in (out / 'frame-decisions.jsonl').read_text().splitlines()]
    run = json.loads((out / 'run-manifest.json').read_text())
    source = BASE / 'outputs' / run['clip']
    old_boxes = torch.load(source / 'bbox.pt', map_location='cpu', weights_only=True)['bbx_xyxy'].numpy()
    mp = np.load(source / 'mediapipe_raw.npz', allow_pickle=False)['normalized']
    old_id = json.loads((source / 'bbox-metrics.json').read_text())['selected_track_id']
    initial_id = records[0]['track_id']
    contacts = out / 'every-frame-contact-sheets'
    contacts.mkdir(exist_ok=False)
    review_path = out / 'basketball-identity-before-after.mp4'
    video = av.open(str(review_path), 'w')
    stream = video.add_stream('libx264', rate=30)
    stream.width, stream.height, stream.pix_fmt = 1920, 440, 'yuv420p'
    stream.options = {'crf': '20', 'preset': 'medium'}
    page = None
    frames_rendered = 0
    with av.open(str(source / 'input_30fps.mp4')) as container:
        for i, frame in enumerate(container.decode(video=0)):
            r = records[i]
            raw = frame.to_image()
            mpbbox = mp_box(mp[i], raw.width, raw.height)
            id_track = next((x for x in r['botsort_tracks_xyxy_id_conf_cls_detidx'] if int(x[4]) == initial_id), None)
            composed = Image.new('RGB', (1920, 440), '#101820')
            d = ImageDraw.Draw(composed)
            for x in (0, 640, 1280): composed.paste(raw, (x, 48))
            d.text((8, 6), f'ORIGINAL independent selection | frame {i:03d} / {len(records)-1}', font=FONT, fill=WHITE)
            d.text((8, 26), f'GVHMR yellow ID {old_id}; MediaPipe magenta', font=SMALL, fill=WHITE)
            d.text((648, 6), f'OFFICIAL BoT-SORT + real ReID | seed numeric ID {initial_id}', font=FONT, fill=WHITE)
            d.text((648, 26), 'ID-only selection: no external identity guard', font=SMALL, fill=WHITE)
            d.text((1288, 6), f'SHARED TARGET GUARD | {r["state"].upper()} | valid={r["valid"]}', font=FONT, fill=GREEN if r['valid'] else ORANGE)
            d.text((1288, 26), f't={i/30:.3f}s  source={r["source_pts_seconds"]:.3f}s  id={r["track_id"]}', font=SMALL, fill=WHITE)
            box(d, old_boxes[i], f'GV {old_id}', YELLOW, offset=(0, 48))
            box(d, mpbbox, 'MP', MAGENTA, offset=(0, 48))
            if id_track is not None: box(d, id_track[:4], f'ID {initial_id}', CYAN, offset=(640, 48))
            for track in r['botsort_tracks_xyxy_id_conf_cls_detidx']:
                box(d, track[:4], str(int(track[4])), '#bbbbbb', width=1, offset=(1280, 48))
            box(d, r['display_bbox_xyxy'], f'TARGET {r["track_id"]}' if r['valid'] else 'PREDICTED / INVALID', GREEN if r['valid'] else ORANGE,
                width=4, offset=(1280, 48), dashed=not r['valid'])
            d.text((8, 420), 'Azorbli / Wikimedia Commons / CC BY-SA 4.0 | Offline replay; all 207 frames; no real-time claim', font=SMALL, fill=WHITE)
            d.text((1288, 420), f'{r["reason"]} | extra keyframe hints=0', font=SMALL, fill=WHITE)
            vf = av.VideoFrame.from_ndarray(np.asarray(composed), format='rgb24')
            vf.pts = i
            for packet in stream.encode(vf): video.mux(packet)
            if i % 9 == 0: page = Image.new('RGB', (1920, 1248), '#101820')
            tile = Image.new('RGB', (640, 416), '#101820')
            tile.paste(raw, (0, 48)); td = ImageDraw.Draw(tile)
            td.text((6, 3), f'FRAME {i:03d} | {i/30:.3f}s | {r["state"]} | valid={r["valid"]}', font=FONT, fill=WHITE)
            td.text((6, 23), f'OLD=yellow MP=magenta RAW=cyan GUARD=green/orange ID={r["track_id"]}', font=SMALL, fill=WHITE)
            box(td, old_boxes[i], f'old{old_id}', YELLOW, width=2, offset=(0, 48))
            box(td, mpbbox, 'MP', MAGENTA, width=2, offset=(0, 48))
            if id_track is not None: box(td, id_track[:4], f'RAW {initial_id}', CYAN, width=2, offset=(0, 48))
            box(td, r['display_bbox_xyxy'], 'NEW' if r['valid'] else 'INVALID', GREEN if r['valid'] else ORANGE,
                width=4, offset=(0, 48), dashed=not r['valid'])
            page.paste(tile, ((i % 3) * 640, ((i % 9) // 3) * 416))
            if i % 9 == 8 or i == len(records) - 1:
                page.save(contacts / f'frames-{i//9*9:03d}-{i:03d}.jpg', quality=91)
            frames_rendered += 1
    for packet in stream.encode(): video.mux(packet)
    video.close()
    with av.open(str(review_path)) as check:
        decoded = sum(1 for _ in check.decode(video=0))
    assert decoded == frames_rendered == len(records)
    receipt = {'video': str(review_path), 'bytes': review_path.stat().st_size, 'decoded_frames': decoded,
        'frame_rate': 30, 'contact_sheet_pages': math.ceil(decoded/9), 'all_frames_rendered': True,
        'ground_truth_status': 'Awaiting assistant visual annotation of every contact-sheet frame',
        'original_outputs_reused_without_new_pose_inference': True}
    (out / 'render-verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__': main()
