"""Hash, population, namespace, identity-link and bulk-accounting checks, offline."""
import csv
import gzip
import json
from collections import Counter, defaultdict

from common import ROOT, DISCOVERY, OUTPUT, checked, distance, read_jsonl, stable_id
from build import TYPES, identifiers
from triage import OUT
from timezones import load_catalog


def validate_manifest(directory):
    lock = json.loads((directory / 'manifest.json').read_text())
    assert set(lock['files']) == {p.name for p in directory.iterdir() if p.is_file() and p.name != 'manifest.json'}, 'Unmanifested output'
    for name, expected in lock['files'].items():
        p = directory / name
        checked(p, expected['sha256'])
        assert p.stat().st_size == expected['bytes'], 'Artifact size mismatch'
    for name, sha in lock['inputs'].items():
        checked(ROOT / name, sha)


def main():
    validate_manifest(OUTPUT)
    validate_manifest(OUT)
    curated = json.loads((ROOT / 'data/airports.json').read_text())
    checked(ROOT / 'test/curated-0.7.0.json', '31c5735b333881d7afdd527fe4af1db8e28413d5bba114fbf88a4aad0809cff7')
    assert curated == json.loads((ROOT / 'test/curated-0.7.0.json').read_text()), 'Reviewed 0.7.0 changed'
    airports = {a['airportId']: a for a in curated['airports']}
    allowed_timezones = load_catalog()
    records = {}
    codes, countries = defaultdict(set), defaultdict(set)
    for shard in '0123456789abcdef':
        for row in read_jsonl(OUTPUT / f'records.{shard}.jsonl.gz'):
            rid = row['referenceId']
            assert rid == stable_id('ref_', ['ourairports', row['sourceEntityId']]) and rid[4] == shard
            assert rid not in records and row['historicallyVerified'] is False
            records[rid] = row
            assert row['timezone'] is None or row['timezone'] in allowed_timezones, 'Timezone outside the pinned catalog'
            countries[row['country'] or 'unknown'].add(rid)
            for scheme, code in row['identifiers'].items():
                if code and (scheme not in ('IATA', 'ICAO') or 'invalid_' + scheme.lower() not in row['flags']):
                    codes[scheme + ':' + code].add(rid)
            for claim in row['historicalIdentifiers']:
                assert 'validFrom' not in claim and 'validTo' not in claim
                codes[claim['scheme'] + ':' + claim['code']].add(rid)
            locations = row['locations']
            assert len({p['locationId'] for p in locations}) == len(locations)
            assert set(row['curatedAirportIds']) == set(locations[0]['curatedAirportIds'])
            for loc in locations:
                assert loc['locationId'] == stable_id('loc_', ['ourairports', row['sourceEntityId'], loc['coordinates']])
                if loc['kind'] == 'unresolved_transition_location':
                    assert loc['candidateIds'] and not loc['curatedAirportIds']
                for aid in loc['curatedAirportIds']:
                    a = airports[aid]
                    assert a['externalIds'].get('ourAirports') == row['sourceEntityId']
                    assert distance(a['coordinates']['value'], loc['coordinates']) <= 1
            if row['presentAtSnapshot']:
                assert row['observation']['kind'] == 'snapshot'
            elif row['observation']['kind'] == 'retained_inventory_row':
                assert row['observedAt'] is None and row['observation']['revision'] is None
            else:
                assert row['observation']['kind'] == 'pre_removal_blob'
    with gzip.open(ROOT / 'reference/inputs/ourairports.csv.gz', 'rt', newline='') as f:
        eligible = [r for r in csv.DictReader(f) if r['type'] in TYPES]
    assert len(eligible) == sum(r['presentAtSnapshot'] for r in records.values())
    for source_row in eligible:
        row = records[stable_id('ref_', ['ourairports', source_row['id']])]
        assert row['identifiers'] == identifiers(source_row)
        assert row['name'] == (source_row['name'] or None)
        assert row['country'] == (source_row['iso_country'] or None)
    inventory = {e['sourceEntityId'] for e in read_jsonl(DISCOVERY / 'ourairports.entities.jsonl.gz') if e['reference']['row'].get('type') in TYPES}
    assert inventory == {r['sourceEntityId'] for r in records.values()}, 'Incomplete historical population'
    actual_codes = {}
    for scheme in ('IATA', 'ICAO', 'GPS', 'LOCAL', 'IDENT'):
        for entry in read_jsonl(OUTPUT / f'index.{scheme}.jsonl.gz'):
            key = scheme + ':' + entry['key']
            assert key not in actual_codes
            actual_codes[key] = set(entry['referenceIds'])
    assert actual_codes == codes, 'Identifier index lost, confused or added observations'
    assert {r['key']: set(r['referenceIds']) for r in read_jsonl(OUTPUT / 'countries.jsonl.gz')} == countries
    group_ids, candidate_ids = set(), set()
    group_counts = Counter()
    for group in read_jsonl(OUT / 'groups.jsonl.gz'):
        assert group['eventGroupId'] not in group_ids
        group_ids.add(group['eventGroupId'])
        assert not candidate_ids.intersection(group['candidateIds']), 'Candidate maps to multiple groups'
        candidate_ids.update(group['candidateIds'])
        assert group['eventDate'] is None and not group['historicallyVerified'] and not group['proposedHistoricalIntervals']
        assert group['independentHistoricalConfirmations'] == 0
        assert group['physicalMatch']['referenceId'] is None or group['physicalMatch']['referenceId'] in records, 'Dangling reference match'
        group_counts[group['status']] += 1
    metrics = json.loads((OUT / 'metrics.json').read_text())
    assert len(group_ids) == metrics['eventGroups'] and len(candidate_ids) == metrics['selectedCandidates']
    assert metrics['sourceCandidatesInspected'] == sum(metrics[k] for k in ('selectedCandidates', 'mechanicallyExcludedCandidates', 'nonEventCandidatesDeferred'))
    assert metrics['sourceCandidatesInspected'] == json.loads((DISCOVERY / 'summary.json').read_text())['sourceRevisionCandidates']
    print(f'Validated {len(records):,} reference records, complete typed indexes, {len(group_ids):,} bulk groups and frozen historical 0.7.0.')


if __name__ == '__main__':
    main()
