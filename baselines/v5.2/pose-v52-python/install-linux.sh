#!/bin/sh
# Opt-in installer. This file is distributed; it is not run by packaging/tests.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3.12}
case "$(uname -s):$(uname -m)" in
 Linux:x86_64) ;;
 *) echo 'This installer is only validated in design for Linux x86_64; macOS/Windows/ARM are untested.' >&2; exit 2 ;;
esac
"$PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12 for this pinned environment"'
if [ -e "$HERE/.venv" ]; then
 echo 'Refusing to alter an existing .venv. Use a fresh extracted source directory.' >&2
 exit 2
fi
"$PYTHON" -m venv "$HERE/.venv"
"$HERE/.venv/bin/python" -m pip install --index-url https://pypi.org/simple --only-binary=:all: pip==25.0.1
"$HERE/.venv/bin/python" -m pip install --index-url https://pypi.org/simple --only-binary=:all: -r "$HERE/requirements-lock.txt"
"$HERE/.venv/bin/python" -m pip check
printf '\nPython packages installed. No server or inference has been started.\n'
printf 'Read INSTALL.md for OS libraries; then install frontend packages and run verify_layout.py.\n'
