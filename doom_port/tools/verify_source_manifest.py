#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description='Verify an exact-Doom source evidence manifest against a supplied linuxdoom-1.10 source tree.')
    ap.add_argument('manifest', type=Path)
    ap.add_argument('source', type=Path)
    ns = ap.parse_args()

    doc = json.loads(ns.manifest.read_text(encoding='utf-8'))
    expected = doc.get('original_source_c_h_sha256')
    if not isinstance(expected, dict):
        raise SystemExit('manifest does not contain original_source_c_h_sha256 (format >= 2 required)')

    source = ns.source.resolve()
    errors = []
    actual_paths = set()
    for path in sorted(source.rglob('*')):
        if path.is_file() and path.suffix.lower() in {'.c', '.h'}:
            rel = path.relative_to(source).as_posix()
            actual_paths.add(rel)
            want = expected.get(rel)
            if want is None:
                errors.append(f'unexpected C/header file: {rel}')
                continue
            got = sha256_file(path)
            if got != want:
                errors.append(f'hash mismatch: {rel}: expected {want}, got {got}')

    for rel in sorted(set(expected) - actual_paths):
        errors.append(f'missing C/header file: {rel}')

    if errors:
        print('SOURCE MANIFEST VERIFY: FAIL', file=sys.stderr)
        for e in errors:
            print('  ' + e, file=sys.stderr)
        raise SystemExit(1)

    print(f'SOURCE MANIFEST VERIFY: PASS ({len(expected)} C/header files)')


if __name__ == '__main__':
    main()
