"""New data/config/cache root; read-only reuse of the already pinned isolated Python runtime."""
import os
from pathlib import Path
BASE=Path(os.environ.get('POSE_COMPARISON_BASE',r'C:\Users\Construct\Downloads\pose-motion-core\gvhmr-comparison-laptop')).resolve()
PRIOR=BASE/'identity-lock-2026-10-18'
ROOT=Path(os.environ.get('POSE_CONFLICT_ROOT',BASE/'conflict-tracklets-2026-10-18')).resolve()
for key,relative in {'YOLO_CONFIG_DIR':'ultralytics','ULTRALYTICS_CONFIG_DIR':'ultralytics','MPLCONFIGDIR':'matplotlib',
    'TORCH_HOME':'torch','HF_HOME':'huggingface','XDG_CACHE_HOME':'xdg','TEMP':'tmp','TMP':'tmp'}.items():
    path=ROOT/'cache'/relative;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',HF_HUB_OFFLINE='1',DO_NOT_TRACK='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4')
