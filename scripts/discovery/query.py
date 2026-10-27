"""Inspect candidate shards without network or loading the entire registry."""
import argparse
import json
from pathlib import Path

from core import canonical, read_candidates

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('code', 'country', 'type', 'source', 'id', 'status'):
        parser.add_argument('--' + flag)
    parser.add_argument('--limit', type=int, default=20, help='0 means all matches')
    args = parser.parse_args()
    config = json.loads((ROOT / 'research/discovery/sources.json').read_text())
    count = 0
    for source in config['sources']:
        if args.source and source['id'] != args.source:
            continue
        for row in read_candidates(ROOT / 'research/discovery/generated', source['id']):
            if args.code and args.code.upper() not in row['context']['codes']:
                continue
            if args.country and args.country.upper() != row['context']['country']:
                continue
            if args.type and args.type not in row['types']:
                continue
            if args.id and args.id != row['candidateId']:
                continue
            if args.status and args.status != row['review']['status']:
                continue
            print(canonical(row))
            count += 1
            if args.limit and count >= args.limit:
                return


if __name__ == '__main__':
    main()
