#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export XDG_CACHE_HOME="$HERE/.cache"
export MPLCONFIGDIR="$HERE/.mplconfig"
export LD_LIBRARY_PATH="$HERE/pose-v52-python/system-libs/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/../.venv/bin/python" "$HERE/pose-v52-python/server_epoch_modes.py" --port 8770 --host 127.0.0.1 --epoch-policy warm "$@"
