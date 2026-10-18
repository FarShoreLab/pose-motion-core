#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/hash_source.py
exec sh ../pose-v52-python/start-epoch-modes.sh --epoch-policy warm --port "${1:-8768}"
