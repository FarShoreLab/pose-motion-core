"""Set process-local paths before importing any third-party package."""
import os,pathlib
ROOT=pathlib.Path(os.environ.get('POSE_MOTION_ROOT',pathlib.Path(__file__).resolve().parents[1])).resolve()
CACHE=ROOT/'cache'/'round2'
PATH_VARS={'YOLO_CONFIG_DIR':'ultralytics','ULTRALYTICS_CONFIG_DIR':'ultralytics','MPLCONFIGDIR':'matplotlib','TORCH_HOME':'torch','HF_HOME':'huggingface','HF_HUB_CACHE':'huggingface/hub','HUGGINGFACE_HUB_CACHE':'huggingface/hub','HF_DATASETS_CACHE':'huggingface/datasets','XDG_CACHE_HOME':'xdg','CUDA_CACHE_PATH':'cuda','TORCH_EXTENSIONS_DIR':'torch-extensions','NUMBA_CACHE_DIR':'numba','TRITON_CACHE_DIR':'triton','UV_CACHE_DIR':'uv','PIP_CACHE_DIR':'pip','TMP':'tmp','TEMP':'tmp'}
def configure():
    for key,relative in PATH_VARS.items():
        path=CACHE/relative;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
    os.environ.update({'GVHMR_ASSET_ROOT':str(ROOT/'assets/checkpoints'),'GVHMR_BODY_MODEL_ROOT':str(ROOT/'assets/body_models'),'YOLO_AUTOINSTALL':'false','HF_HUB_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','WANDB_MODE':'disabled','PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'})
    return os.environ.copy()
configure()
