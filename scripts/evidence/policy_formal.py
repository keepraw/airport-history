"""Replay an authorized admission bundle against its frozen published baseline.

This CLI never treats an updated working-tree formal database as the old baseline.
It reads recorded original verification offline, without claiming to have fetched
private originals. The production preparation CLI must actually replay those bytes.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

from policy_review import ROOT, inputs, load, require, digest


def validate(bundle=None, candidate=None):
    _, lock, base, *_ = inputs()
    candidate = ROOT / 'data/airports.json' if candidate is None else candidate.resolve()
    current = load(candidate)
    if bundle is None and digest(candidate) == lock['baseline']['sha256']:
        print('Current formal bytes equal the independently published frozen baseline; no new admission.')
        return
    bundle = ROOT / f"research/admissions/{current['dataVersion']}" if bundle is None else bundle.resolve()
    require(load(bundle / 'proposed-data.json') == current, 'Formal candidate differs from its exact admission bundle')
    context = load(bundle / 'policy-receipt.json')
    require(load(bundle / 'original-verification.json') == context['originalVerification'], 'Detached original-verification file')
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        output = Path(tmp) / 'validated.json'
        # Exercise the original CLI, including its schema/semantic and immutable-record checks.
        subprocess.run(['python3', 'scripts/evidence/review.py', 'validate',
            '--base-dataset', str(ROOT / lock['baseline']['path']), '--dataset', str(candidate),
            '--batches', str(bundle / 'batches'), '--dossier', str(bundle / 'dossier.json'),
            '--policy-context', str(bundle / 'policy-receipt.json'), '--output', str(output)], cwd=ROOT, check=True)
        require(load(output) == current and base != current, 'Admission did not replay frozen old data to new candidate')
    subprocess.run(['node', 'scripts/evidence/policy_coverage.ts', 'gate', str(candidate)], cwd=ROOT, check=True)
    print('Original admission CLI and resolver replay passed; original-verification receipt checked OFFLINE, no bytes reacquired.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    validate(args.bundle, args.candidate)
