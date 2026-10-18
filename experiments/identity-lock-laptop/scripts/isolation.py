"""Experiment-local configuration; import before third-party packages."""
import os
from pathlib import Path

BASE = Path(os.environ.get('POSE_COMPARISON_BASE', r'C:\Users\Construct\Downloads\pose-motion-core\gvhmr-comparison-laptop')).resolve()
ROOT = Path(os.environ.get('POSE_IDENTITY_ROOT', BASE / 'identity-lock-2026-10-18')).resolve()
for key, relative in {
    'YOLO_CONFIG_DIR': 'ultralytics', 'ULTRALYTICS_CONFIG_DIR': 'ultralytics',
    'MPLCONFIGDIR': 'matplotlib', 'TORCH_HOME': 'torch', 'HF_HOME': 'huggingface',
    'HF_HUB_CACHE': 'huggingface/hub', 'HUGGINGFACE_HUB_CACHE': 'huggingface/hub',
    'XDG_CACHE_HOME': 'xdg', 'CUDA_CACHE_PATH': 'cuda', 'TORCH_EXTENSIONS_DIR': 'torch-extensions',
    'NUMBA_CACHE_DIR': 'numba', 'TRITON_CACHE_DIR': 'triton', 'UV_CACHE_DIR': 'uv',
    'PIP_CACHE_DIR': 'pip', 'TMP': 'tmp', 'TEMP': 'tmp',
}.items():
    path = ROOT / 'cache' / relative
    path.mkdir(parents=True, exist_ok=True)
    os.environ[key] = str(path)
os.environ.update({
    'YOLO_AUTOINSTALL': 'false', 'HF_HUB_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
    'DO_NOT_TRACK': '1', 'WANDB_MODE': 'disabled', 'PYTHONUTF8': '1',
    'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '4', 'MKL_NUM_THREADS': '4',
    'YOLO_OFFLINE': 'true', 'RUST_LOG': 'warn',
})
