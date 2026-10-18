#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export XDG_CACHE_HOME="$HERE/.cache"
export MPLCONFIGDIR="$HERE/.mplconfig"
export LD_LIBRARY_PATH="$HERE/system-libs/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/.venv/bin/python" "$HERE/server_epoch_modes.py" "$@"
