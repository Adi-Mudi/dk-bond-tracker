#!/usr/bin/env bash
# Feature-isolation + layer-direction boundary check (Essential 0.5 / 0.6 / 0.12 / 0.17).
# Enforced in CI (.github/workflows/flutter.yml). Usage: bash scripts/check_flutter_imports.sh
set -euo pipefail
cd "$(dirname "$0")/../frontend/app"
python3 - << 'PY'
import re, sys, pathlib

VIOL = []
def vi(f, rule, line):
    VIOL.append(f"{f}:{line} [{rule}]")

import_re = re.compile(r"""(?:import|export)\s+(['"])([^'"]+)\1""")

for f in sorted(pathlib.Path('lib').rglob('*.dart')):
    s = str(f)
    parts = s.split('/')
    is_feature = parts[1] == 'features' if len(parts) > 2 else False
    feat = parts[2] if is_feature and len(parts) > 3 else None
    in_data = is_feature and 'data' in parts
    in_ui = is_feature and 'ui' in parts
    is_shared = len(parts) > 2 and parts[1] == 'shared'
    is_shared_utils = is_shared and len(parts) > 3 and parts[2] == 'utils'
    for i, raw in enumerate(f.read_text().splitlines(), 1):
        for m in import_re.finditer(raw):
            kind = m.group(0).split()[0]
            target = m.group(2)
            # relative paths banned (0.12 stable aliases — package:app/ root)
            if target.startswith('.'):
                vi(s, '0.12 relative import — use package:app/', i)
                continue
            if not target.startswith('package:app/'):
                # pure helpers must not pull network/storage (0.5)
                if is_shared_utils and (target.startswith('dart:io') or target in
                        ('package:http/http.dart', 'package:dio/dio.dart')):
                    vi(s, '0.5 helper imports network/storage', i)
                continue
            # normalize path after package:app/
            tp = target[len('package:app/'):]
            tparts = tp.split('/')
            # cross-feature (0.6): features/<a> touching features/<b≠a>, via import or export
            if len(tparts) > 2 and tparts[0] == 'features':
                other = tparts[1]
                if is_feature and other != feat:
                    vi(s, f'0.6 {kind} cross-feature -> features/{other}', i)
                    continue
                if is_shared:
                    vi(s, f'0.5 shared {kind} from features/{other}', i)
                    continue
            # data -> ui is upward (0.5)
            if in_data and len(tparts) > 3 and tparts[0] == 'features' and tparts[2] == 'ui' and tparts[3] != '':
                if tparts[1] == feat and 'ui' in tparts:
                    vi(s, '0.5 data imports ui (upward)', i)
            # ui -> other-layer already covered; utils must not import widgets or other features (0.5)
            if is_shared_utils:
                if len(tparts) > 2 and tparts[0] == 'features':
                    vi(s, '0.5 helper imports feature', i)
                if len(tparts) > 1 and tparts[0] == 'shared' and tparts[1] == 'widgets':
                    vi(s, '0.5 helper imports widgets layer', i)

if VIOL:
    print("FEATURE/LAYER BOUNDARY VIOLATIONS (Essential 0.5/0.6/0.12):")
    for v in VIOL:
        print("  " + v)
    sys.exit(1)
print("flutter import boundaries OK")
PY
