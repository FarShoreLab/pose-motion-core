#!/bin/sh
# Optional local extraction; no sudo, system installation, or browser flags.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$(uname -s):$(uname -m)" in
 Linux:x86_64) ;;
 *) echo 'This Debian amd64 package is not for this platform.' >&2; exit 2 ;;
esac
DEST="$HERE/system-libs"
FILE="$DEST/libgles2_1.7.0-1+b2_amd64.deb"
mkdir -p "$DEST"
curl --fail --location --connect-timeout 20 --max-time 120 \
 'https://deb.debian.org/debian/pool/main/libg/libglvnd/libgles2_1.7.0-1+b2_amd64.deb' -o "$FILE"
printf 'e12c18aa77939d122ee1dea520ba0440b97dc19200b7396e03dff03a3ece74c1  %s\n' "$FILE" | sha256sum -c -
dpkg-deb -x "$FILE" "$DEST"
printf 'Extracted the verified Debian libgles2 into %s. start.sh uses this path.\n' "$DEST"
printf 'This only supplies libGLESv2; EGL/GLdispatch/other dependencies must exist separately.\n'
