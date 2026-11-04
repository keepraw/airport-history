"""Current-tree replay of `python3 scripts/evidence/korea_readiness.py rights` after a human-v1 release.

The legacy rights audit (korea_readiness -> code_dates -> priority_markets.rights_audit)
starts with priority_markets.verify(), whose baseline lock pins the exact 0.10.0 bytes of
data/airports.json and requires package.json/dataVersion 0.10.0. A human-v1 release changes
exactly those, so the unchanged command can only hold in the frozen published tree, where
the router still runs it unchanged.

Here the same protected executors run unmodified; only that one entry check is narrowed:
every other file in the priority-markets baseline lock must still match byte for byte, and
data/airports.json plus the version fields must be the ones the approved human-v1 bundle
publishes (core.ci() has already proven that before this runs). The ancestry, blob, staged
file and citation checks of all three audits then run in full over HEAD.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import core  # noqa: E402
import priority_markets as pm  # noqa: E402
import korea_readiness  # noqa: E402

RELEASED = {'data/airports.json'}


def narrowed_verify(original):
    def verify(*, originals=False, baseline=True):
        if baseline:
            frozen = pm.load(pm.BASE / 'baseline-lock.json')
            if pm.digest((ROOT / 'data/airports.json').read_bytes()) == frozen['files']['data/airports.json']:
                return original(originals=originals, baseline=True)  # no release yet: the unchanged check
            require = pm.require
            require(RELEASED <= set(frozen['files']), 'Priority-markets baseline lock no longer pins the released data')
            for path, expected in frozen['files'].items():
                if path not in RELEASED:
                    require(pm.digest((ROOT / path).read_bytes()) == expected, 'Protected baseline changed: ' + path)
            data = pm.load(ROOT / 'data/airports.json')
            bundle = core.bundle_dir(data['dataVersion'])
            require(bundle.exists(), 'No human-v1 release bundle for dataVersion ' + data['dataVersion'])
            require(pm.load(bundle / 'proposed-data.json') == data, 'Published data detached from its approved candidate')
            require(pm.load(ROOT / 'package.json')['version'] == data['dataVersion'], 'package.json version detached from data')
            require(data['schemaVersion'] == pm.load(ROOT / ('test/curated-%s.json' % frozen['dataVersion']))['schemaVersion'],
                    'Schema version changed')
        return original(originals=originals, baseline=False)
    return verify


def main():
    pm.verify = narrowed_verify(pm.verify)
    result = korea_readiness.rights()
    result['humanV1Narrowing'] = ('priority-markets baseline entry check: data/airports.json and version fields bound to '
                                  'the approved human-v1 bundle instead of the 0.10.0 bytes; all other locked files unchanged')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
