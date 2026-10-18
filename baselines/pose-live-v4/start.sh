#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d node_modules/@mediapipe/tasks-vision ]; then npm ci --ignore-scripts; fi
python3 scripts/download_assets.py
exec python3 server.py
