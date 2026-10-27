"""Refresh review metadata over the shipped discovery snapshot, without rescanning."""
import hashlib
import json
from pathlib import Path

from core import write_json
from review import batch_summaries, require

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/discovery/generated'


def main():
    lock = json.loads((OUT / 'manifest.json').read_text())
    # Never use review refresh to silently bless changed discovery observations.
    for name, expected in lock['files'].items():
        if name == 'summary.json':
            continue
        raw = (OUT / name).read_bytes()
        require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
                f'Discovery artifact changed: {name}; review refresh cannot replace a scan')
    summary = json.loads((OUT / 'summary.json').read_text())
    summary['reviewBatches'] = batch_summaries(ROOT)
    write_json(OUT / 'summary.json', summary)
    inputs = [*(p for p in sorted((ROOT / 'research/discovery').glob('*.json')) if p.name != 'reviews.json'),
              *sorted((ROOT / 'scripts/discovery').glob('*.py'))]
    review_inputs = [ROOT / 'research/discovery/reviews.json',
                     *sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    def hashes(paths):
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    lock['inputs'] = hashes(inputs)
    lock['reviewInputs'] = hashes(review_inputs)
    raw = (OUT / 'summary.json').read_bytes()
    lock['files']['summary.json'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    write_json(OUT / 'manifest.json', lock)
    print('Refreshed review metadata; discovery observations, queue, source pins and formal data unchanged.')


if __name__ == '__main__':
    main()
