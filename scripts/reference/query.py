"""Offline worldwide reference lookup. Results never resolve historical validity."""
import argparse
import json
import re
import sys

from common import OUTPUT, canonical, read_jsonl, stable_id


def lookup(directory=OUTPUT, *, code=None, scheme='IATA', source_id=None, name=None, country=None, limit=20, offset=0):
    if scheme not in ('IATA', 'ICAO', 'GPS', 'LOCAL', 'IDENT'):
        raise ValueError('Unknown identifier namespace')
    if limit < 0 or offset < 0:
        raise ValueError('limit and offset must be nonnegative; limit=0 returns all')
    if not any((code, source_id, name, country)):
        raise ValueError('Specify at least one search filter')
    if code:
        code = code.strip()
        if scheme in ('IATA', 'ICAO'):
            code = code.upper()
        if scheme in ('IATA', 'ICAO') and not re.fullmatch('[A-Z]{3}' if scheme == 'IATA' else '[A-Z]{4}', code):
            raise ValueError('Code does not match the selected namespace')
    filters = []
    if code:
        filters.append({rid for entry in read_jsonl(directory / f'index.{scheme}.jsonl.gz')
                        if entry['key'] == code for rid in entry['referenceIds']})
    if source_id:
        filters.append({stable_id('ref_', ['ourairports', source_id])})
    if country:
        filters.append({rid for entry in read_jsonl(directory / 'countries.jsonl.gz')
                        if entry['key'] == country.upper() for rid in entry['referenceIds']})
    if filters:
        ids = set.intersection(*filters)
        shards = sorted({rid[4] for rid in ids})
    else:
        ids = None
        shards = list('0123456789abcdef')
    matches = []
    total = 0
    location_count = 0
    for shard in shards:
        for row in read_jsonl(directory / f'records.{shard}.jsonl.gz'):
            if ids is not None and row['referenceId'] not in ids:
                continue
            if name and not any(name.casefold() in value.casefold()
                                for value in [row['name'] or '', *(n['name'] for n in row['historicalNames'])]):
                continue
            total += 1
            location_count += len(row['locations'])
            if total > offset and (limit == 0 or len(matches) < limit):
                matches.append(row)
    lock = json.loads((directory / 'manifest.json').read_text())
    return {
        'status': 'not_found' if not total else 'ambiguous_reference' if total > 1 or location_count > 1 else 'reference_only',
        'historicallyVerified': False, 'referenceVersion': lock['referenceVersion'],
        'totalMatches': total, 'returnedMatches': len(matches), 'offset': offset,
        'possibleLocationCount': location_count,
        'query': {'code': code, 'scheme': scheme, 'sourceId': source_id, 'name': name, 'country': country},
        'candidates': matches, 'sources': json.loads((directory / 'sources.json').read_text()),
        'meaning': 'Reference observations and unresolved location hypotheses; no event or code-validity dates. Use resolveAirport() for historical resolution.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('code', 'source-id', 'name', 'country'):
        parser.add_argument('--' + flag)
    parser.add_argument('--scheme', choices=['IATA', 'ICAO', 'GPS', 'LOCAL', 'IDENT'], default='IATA')
    parser.add_argument('--limit', type=int, default=20, help='0 returns all')
    parser.add_argument('--offset', type=int, default=0)
    args = parser.parse_args()
    try:
        print(canonical(lookup(**vars(args))))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
