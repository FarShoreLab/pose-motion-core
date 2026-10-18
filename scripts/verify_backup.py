#!/usr/bin/env python3
"""Verify unchanged archival source; no network, installation, or model imports."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'manifests/baseline-sources.json').read_text())
    problems = []
    expected = set()
    for row in manifest['files']:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            problems.append(f'Unsafe manifest path: {relative}')
            continue
        expected.add(relative.as_posix())
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            problems.append(f'Missing or non-regular source: {relative}')
            continue
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            problems.append(f'Changed archival source: {relative}')
    # Runtime additions such as restored dependencies/assets are permitted; this
    # check verifies the selected source snapshot, not a clean worktree policy.
    print(json.dumps({'ok': not problems, 'archival_files_checked': len(expected),
                      'problems': problems,
                      'scope': 'Archived file bytes only; no inference or dependency verification'}, indent=2))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
