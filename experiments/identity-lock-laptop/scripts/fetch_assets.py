"""Fetch only the explicitly selected official ReID weight and provenance."""
from isolation import BASE, ROOT
import hashlib
import json
import urllib.request

assets = ROOT / 'assets'
assets.mkdir(exist_ok=True)
url = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-reid.onnx'
path = assets / 'yolo26n-reid.onnx'
if not path.exists():
    request = urllib.request.Request(url, headers={'User-Agent': 'pose-motion-identity-research'})
    with urllib.request.urlopen(request, timeout=90) as response:
        content = response.read()
    assert len(content) > 1_000_000, 'Unexpected model response'
    path.write_bytes(content)
record = {
    'filename': path.name, 'requested_url': url,
    'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'source': 'Official Ultralytics assets release v8.4.0, linked from official tracking documentation',
    'license': 'Ultralytics AGPL-3.0 model licensing; research experiment; no Enterprise entitlement claimed',
    'license_url': 'https://www.ultralytics.com/license',
    'documentation_url': 'https://docs.ultralytics.com/modes/track/',
    'explicit_clickthrough_or_new_legal_acceptance': False,
}
detector = BASE / 'assets/checkpoints/yolo/yolov8x.pt'
record['reused_detector'] = {'path': str(detector), 'bytes': detector.stat().st_size,
    'sha256': hashlib.sha256(detector.read_bytes()).hexdigest()}
(ROOT / 'asset-provenance.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record, indent=2))
