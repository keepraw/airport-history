"""Extend reference:review without rewriting its hash-pinned admission implementation."""
import argparse
import sys
from pathlib import Path

from pipeline import OUT, validate
from common import read_jsonl, write_json
from admissions import main as original_review


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] != 'evidence':
        original_review()
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('command', choices=['evidence'])
        parser.add_argument('--output', type=Path, required=True)
        args = parser.parse_args()
        validate()
        if args.output.exists() and any(args.output.iterdir()):
            raise ValueError('Use an empty output directory')
        count = 0
        for batch in read_jsonl(OUT / 'review-packets.jsonl.gz'):
            write_json(args.output / (batch['batchId'] + '.json'), batch)
            count += len(batch['events'])
        print(f'Exported {count} pending-review events with primary evidence; no human approval or admission.')
