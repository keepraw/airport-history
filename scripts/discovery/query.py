"""Inspect candidate shards without network or loading the entire registry."""
import argparse
import json
from pathlib import Path

from core import apply_review, canonical, read_candidates, read_jsonl

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('code', 'country', 'type', 'source', 'id', 'status'):
        parser.add_argument('--' + flag)
    parser.add_argument('--limit', type=int, default=20, help='0 means all matches')
    parser.add_argument('--snapshot', action='store_true', help='Inspect the original exported review state without live overrides')
    parser.add_argument('--queue', action='store_true', help='Inspect the existing ranked queue with current review overrides')
    args = parser.parse_args()
    config = json.loads((ROOT / 'research/discovery/sources.json').read_text())
    reviews = {} if args.snapshot else json.loads((ROOT / 'research/discovery/reviews.json').read_text())
    out = ROOT / 'research/discovery/generated'
    count = 0
    collections = ([read_jsonl(out / 'verification-queue.jsonl.gz')] if args.queue else
                   [read_candidates(out, s['id']) for s in config['sources'] if not args.source or s['id'] == args.source])
    for collection in collections:
        for original in collection:
            row = apply_review(original, reviews)
            if args.source and row['sourceId'] != args.source:
                continue
            if args.code and args.code.upper() not in row['context']['codes']:
                continue
            if args.country and args.country.upper() != row['context']['country']:
                continue
            if args.type and args.type not in row['types']:
                continue
            if args.id and args.id != row['candidateId']:
                continue
            if args.status and args.status != row.get('review', {}).get('status', row.get('status')):
                continue
            print(canonical(row))
            count += 1
            if args.limit and count >= args.limit:
                return


if __name__ == '__main__':
    main()
