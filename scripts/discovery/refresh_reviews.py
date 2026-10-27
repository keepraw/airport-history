"""Refresh review metadata over the shipped discovery snapshot, without rescanning."""
import hashlib
import json
from pathlib import Path

from core import write_json
from review import batch_summaries, require, validate_review_overrides

ROOT = Path(__file__).resolve().parents[2]


def refresh_reviews(root):
    out = root / 'research/discovery/generated'
    lock = json.loads((out / 'manifest.json').read_text())
    # Verify the entire old snapshot, including summary, before any writes.
    require('summary.json' in lock['files'], 'Summary is missing from the manifest')
    require(set(lock['files']) == {p.name for p in out.iterdir() if p.is_file() and p.name != 'manifest.json'},
            'Unmanifested discovery artifact; review refresh cannot replace a report')
    for name, expected in lock['files'].items():
        raw = (out / name).read_bytes()
        require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
                f'Discovery artifact changed: {name}; review refresh cannot replace a scan')
    for name, digest in lock['inputs'].items():
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest,
                f'Non-review input changed: {name}; run research:report explicitly')
    review_inputs = [root / 'research/discovery/reviews.json',
                     *sorted((root / 'research/discovery/batches').glob('*.json'))]
    require(not (set(lock['inputs']) & {str(p.relative_to(root)) for p in review_inputs}),
            'Review input is registered as a non-review input; run research:report explicitly')
    summary = json.loads((out / 'summary.json').read_text())
    summary['reviewBatches'] = batch_summaries(root)
    # Read/validate all allowed review inputs before changing either output.
    review_hashes = {}
    review_records = {}
    for path in review_inputs:
        raw = path.read_bytes()
        name = str(path.relative_to(root))
        record = json.loads(raw)
        require(isinstance(record, dict), f'Invalid review record: {name}')
        review_records[name] = record
        review_hashes[name] = hashlib.sha256(raw).hexdigest()
    reviews_path = 'research/discovery/reviews.json'
    validate_review_overrides(review_records[reviews_path],
                              [(name, record) for name, record in review_records.items() if name != reviews_path])
    lock['reviewInputs'] = review_hashes
    write_json(out / 'summary.json', summary)
    raw = (out / 'summary.json').read_bytes()
    lock['files']['summary.json'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    write_json(out / 'manifest.json', lock)
    print('Refreshed review metadata; discovery observations, queue, source pins and formal data unchanged.')


if __name__ == '__main__':
    refresh_reviews(ROOT)
