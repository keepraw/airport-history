"""Materialize the complete pinned population and retained historical source records."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
from collections import Counter, defaultdict

from common import (ROOT, DISCOVERY, OUTPUT, canonical, checked, distance, manifest,
                    position, read_jsonl, stable_id, verify_discovery, write_json, write_jsonl)
from timezones import load_catalog

TYPES = {'balloonport', 'closed', 'heliport', 'large_airport', 'medium_airport', 'seaplane_base', 'small_airport'}
CODE_FIELDS = {'IATA': 'iata_code', 'ICAO': 'icao_code', 'GPS': 'gps_code', 'LOCAL': 'local_code', 'IDENT': 'ident'}


def identifiers(row):
    return {scheme: row.get(field) or None for scheme, field in CODE_FIELDS.items()}


def make_record(row, present, lock, airports):
    """A reference ID denotes a source record, never a verified physical airport."""
    entity = row['id']
    coords = position(row.get('latitude_deg'), row.get('longitude_deg'))
    flags = []
    if coords is None:
        flags.append('missing_or_invalid_coordinates')
    if not row.get('name'):
        flags.append('missing_name')
    if not re.fullmatch('[A-Z]{2}', row.get('iso_country', '')):
        flags.append('missing_or_invalid_country')
    codes = identifiers(row)
    for scheme, pattern in [('IATA', '[A-Z]{3}'), ('ICAO', '[A-Z]{4}')]:
        if codes[scheme] and not re.fullmatch(pattern, codes[scheme]):
            flags.append('invalid_' + scheme.lower())
    linked = []
    for airport in airports:
        # An external ID alone must not link a repurposed record to a different site.
        if airport['externalIds'].get('ourAirports') == entity:
            separation = distance(coords, airport['coordinates']['value'])
            if separation is not None and separation <= 1:
                linked.append(airport['airportId'])
            else:
                flags.append('curated_external_id_location_mismatch')
    if len(linked) > 1:
        flags.append('multiple_curated_identity_matches')
        linked = []
    loc = {'locationId': stable_id('loc_', ['ourairports', entity, coords]),
           'coordinates': coords, 'kind': 'snapshot' if present else 'last_known_row',
           'curatedAirportIds': linked, 'candidateIds': []}
    return {
        'referenceId': stable_id('ref_', ['ourairports', entity]),
        'sourceId': 'ourairports', 'sourceEntityId': entity,
        'identityStatus': 'external_record_only', 'historicallyVerified': False,
        'presentAtSnapshot': present, 'name': row.get('name') or None,
        'facilityType': row.get('type') or None, 'country': row.get('iso_country') or None,
        'region': row.get('iso_region') or None, 'municipality': row.get('municipality') or None,
        'identifiers': codes, 'timezone': None, 'timezoneEvidence': [],
        'locations': [loc], 'curatedAirportIds': linked,
        'observedAt': lock['observedAt'] if present else None,
        'observation': {'revision': lock['revision'], 'blob': lock['gitBlob'], 'kind': 'snapshot'} if present else None,
        'historicalIdentifiers': [], 'historicalNames': [], 'flags': flags,
    }


def add_transition(record, candidate):
    """Keep typed observations and location hypotheses, without asserting event dates."""
    changes = candidate['changes']
    obs = candidate['observations']
    first = min(obs, key=lambda x: (x['observedAt'], x['commit'], x['beforeBlob']))
    for side, value in enumerate(changes.get('name', [])):
        if value:
            record['historicalNames'].append({'name': value, 'candidateId': candidate['candidateId'],
                                               'sourceId': candidate.get('sourceId', 'ourairports'),
                                               'side': 'before' if side == 0 else 'after',
                                               'revisionObservedAt': first['observedAt']})
    for scheme, field in [('IATA', 'iata'), ('ICAO', 'icao')]:
        for side, value in enumerate(changes.get(field, [])):
            if value and re.fullmatch('[A-Z]{3}' if scheme == 'IATA' else '[A-Z]{4}', value):
                record['historicalIdentifiers'].append({
                    'sourceId': candidate.get('sourceId', 'ourairports'),
                    'scheme': scheme, 'code': value, 'candidateId': candidate['candidateId'],
                    'side': 'before' if side == 0 else 'after', 'commit': first['commit'],
                    'blob': first['beforeBlob'] if side == 0 else first['afterBlob'],
                    'revisionObservedAt': first['observedAt'],
                    'meaning': 'Source transition observation; physical attribution and effective dates unverified',
                })
    if (candidate.get('distanceKm') or 0) < 5:
        return
    record['flags'].append('possible_source_repurposing_or_coordinate_correction')
    # Only reconstruct coordinates explicitly present in BOTH changed axes.
    # Filling an unchanged axis from today's row would manufacture past positions.
    if 'lat' not in changes or 'lon' not in changes:
        record['flags'].append('incomplete_historical_location')
        return
    for side in (0, 1):
        coords = position(changes['lat'][side], changes['lon'][side])
        if coords is None:
            continue
        location_id = stable_id('loc_', ['ourairports', record['sourceEntityId'], coords])
        existing = next((p for p in record['locations'] if p['locationId'] == location_id), None)
        if existing:
            existing['candidateIds'].append(candidate['candidateId'])
        else:
            record['locations'].append({
                'locationId': location_id, 'coordinates': coords,
                'kind': 'unresolved_transition_location', 'curatedAirportIds': [],
                'candidateIds': [candidate['candidateId']],
            })


def enrich_timezones(records, inventory, source, allowed_zones):
    """Use a unique identifier + same country + <=1 km, never IATA alone."""
    index = defaultdict(list)
    for entry in inventory:
        if entry['presentAtTarget']:
            index[entry['sourceEntityId']].append(entry)
    for record in records.values():
        codes = record['identifiers']
        candidates = {}
        for code in {codes['ICAO'], codes['GPS'], codes['IDENT']} - {None}:
            for entry in index.get(code, []):
                row = entry['reference']['row']
                km = distance(record['locations'][0]['coordinates'], position(row.get('lat'), row.get('lon')))
                if row.get('country') == record['country'] and km is not None and km <= 1:
                    candidates[entry['sourceEntityId']] = row
        zones = set()
        for entity, row in sorted(candidates.items()):
            tz = row.get('tz')
            if tz:
                if tz in allowed_zones:
                    zones.add(tz)
                    record['timezoneEvidence'].append({'sourceId': 'airportsdata', 'sourceEntityId': entity,
                                                      'revision': source['revision'], 'timezone': tz})
                else:
                    record['flags'].append('invalid_timezone')
        if len(zones) == 1:
            record['timezone'] = next(iter(zones))
        elif zones:
            record['flags'].append('conflicting_timezone_observations')


def build(output=OUTPUT):
    lock_path = ROOT / 'reference/source-lock.json'
    lock = json.loads(lock_path.read_text())
    input_path = ROOT / 'reference/inputs/ourairports.csv.gz'
    raw = gzip.decompress(input_path.read_bytes())
    if hashlib.sha256(raw).hexdigest() != lock['sha256']:
        raise ValueError('Pinned snapshot SHA-256 mismatch')
    if hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != lock['gitBlob']:
        raise ValueError('Pinned snapshot Git blob mismatch')
    discovery_lock = json.loads((DISCOVERY / 'manifest.json').read_text())
    candidate_names = sorted(n for n in discovery_lock['files'] if n.startswith(('ourairports.candidates.', 'airport-codes-raw.candidates.')))
    names = ['ourairports.entities.jsonl.gz', 'ourairports.versions.jsonl.gz',
             'ourairports.coverage.json', 'airportsdata.entities.jsonl.gz', *candidate_names]
    verify_discovery(names)
    coverage = json.loads((DISCOVERY / 'ourairports.coverage.json').read_text())
    if coverage['revision'] != lock['revision']:
        raise ValueError('Discovery inventory and pinned snapshot revisions differ')
    versions = list(read_jsonl(DISCOVERY / 'ourairports.versions.jsonl.gz'))
    target = [v for v in versions if v['commit'] == lock['revision'] and v['afterBlob'] == lock['gitBlob']]
    if len(target) != 1 or target[0]['observedAt'] != lock['observedAt']:
        raise ValueError('Snapshot observation metadata is not pinned to its source revision')
    dataset = json.loads((ROOT / 'data/airports.json').read_text())
    inventory = {e['sourceEntityId']: e for e in read_jsonl(DISCOVERY / 'ourairports.entities.jsonl.gz')}
    if len(inventory) != coverage['history']['entitiesEverObserved']:
        raise ValueError('Incomplete source identity inventory')
    records, snapshot_ids = {}, set()
    rejected = Counter()
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True):
        entity = row['id']
        if not re.fullmatch('[0-9]+', entity) or entity in snapshot_ids:
            raise ValueError('Duplicate or invalid source identity')
        snapshot_ids.add(entity)
        if row['type'] not in TYPES:
            rejected['unsupported_type'] += 1
            continue
        records[entity] = make_record(row, True, lock, dataset['airports'])
    if len(snapshot_ids) != lock['records'] or snapshot_ids != {k for k, v in inventory.items() if v['presentAtTarget']}:
        raise ValueError('Snapshot population differs from pinned inventory')
    for entity, entry in inventory.items():
        if not entry['presentAtTarget']:
            row = entry['reference']['row']
            if row.get('type') not in TYPES:
                rejected['unsupported_historical_type'] += 1
                continue
            record = make_record(row, False, lock, dataset['airports'])
            # The inventory's removal afterBlob may not contain this row. Do not cite it as an observation.
            record['observation'] = {'kind': 'retained_inventory_row', 'inventory': 'ourairports.entities.jsonl.gz',
                                     'lastChangedAt': entry['lastChangedAt'], 'revision': None, 'blob': None}
            record['flags'].append('absent_at_pinned_snapshot')
            records[entity] = record
    for name in candidate_names:
        for candidate in read_jsonl(DISCOVERY / name):
            record = records.get(candidate['sourceEntityId'])
            if record is not None:
                add_transition(record, candidate)
                if candidate['sourceId'] == 'ourairports' and not record['presentAtSnapshot'] and 'record_removed' in candidate['types']:
                    # Exact last-known row provenance is the PRE-removal blob, never the removal commit's row.
                    inv = inventory[candidate['sourceEntityId']]
                    matching = [o for o in candidate['observations'] if o['commit'] == inv['reference']['version']]
                    if matching:
                        before = matching[0]['beforeBlob']
                        sightings = [v for v in versions if v['afterBlob'] == before]
                        if sightings:
                            v = min(sightings, key=lambda x: (x['observedAt'], x['commit']))
                            record['observedAt'] = v['observedAt']
                            record['observation'] = {'kind': 'pre_removal_blob', 'revision': v['commit'], 'blob': before,
                                                     'removalCandidateId': candidate['candidateId']}
    source_config = json.loads((ROOT / 'research/discovery/sources.json').read_text())
    tz_source = next(s for s in source_config['sources'] if s['id'] == 'airportsdata')
    enrich_timezones(records, read_jsonl(DISCOVERY / 'airportsdata.entities.jsonl.gz'), tz_source, load_catalog())
    code_index, country_index = defaultdict(set), defaultdict(list)
    for entity, record in sorted(records.items()):
        rid = record['referenceId']
        country_index[record['country'] or 'unknown'].append(rid)
        record['flags'] = sorted(set(record['flags']))
        for loc in record['locations']:
            loc['candidateIds'] = sorted(set(loc['candidateIds']))
        record['locations'].sort(key=lambda x: (x['kind'] not in ('snapshot', 'last_known_row'), x['locationId']))
        record['historicalIdentifiers'] = sorted({canonical(x): x for x in record['historicalIdentifiers']}.values(), key=canonical)
        record['historicalNames'] = sorted({canonical(x): x for x in record['historicalNames']}.values(), key=canonical)
        for scheme, code in record['identifiers'].items():
            if code and (scheme not in ('IATA', 'ICAO') or 'invalid_' + scheme.lower() not in record['flags']):
                code_index[scheme + ':' + code].add(rid)
        for claim in record['historicalIdentifiers']:
            code_index[claim['scheme'] + ':' + claim['code']].add(rid)
    output.mkdir(parents=True, exist_ok=True)
    for record in records.values():
        for scheme in ('IATA', 'ICAO'):
            code = record['identifiers'][scheme]
            if code and len(code_index.get(scheme + ':' + code, [])) > 1:
                record['flags'].append('ambiguous_' + scheme.lower() + '_reference')
        record['flags'] = sorted(set(record['flags']))
    ordered = sorted(records.values(), key=lambda x: x['referenceId'])
    for shard in '0123456789abcdef':
        write_jsonl(output / f'records.{shard}.jsonl.gz', (r for r in ordered if r['referenceId'][4] == shard))
    for scheme in CODE_FIELDS:
        write_jsonl(output / f'index.{scheme}.jsonl.gz',
                    ({'key': key.split(':', 1)[1], 'referenceIds': sorted(ids)}
                     for key, ids in sorted(code_index.items()) if key.startswith(scheme + ':')))
    write_jsonl(output / 'countries.jsonl.gz',
                ({'key': key, 'referenceIds': sorted(ids)} for key, ids in sorted(country_index.items())))
    # Remove only the obsolete output of this builder's first format iteration.
    (output / 'index.jsonl.gz').unlink(missing_ok=True)
    by_id = {r['referenceId']: r for r in ordered}
    metrics = {
        'sourceRecordsInspected': len(inventory), 'pinnedSnapshotRecords': len(snapshot_ids),
        'eligibleReferenceRecords': len(records), 'rejected': dict(rejected),
        'presentAtSnapshot': sum(r['presentAtSnapshot'] for r in ordered),
        'historicalOnly': sum(not r['presentAtSnapshot'] for r in ordered),
        'closed': sum(r['facilityType'] == 'closed' for r in ordered),
        'snapshotClosed': sum(r['presentAtSnapshot'] and r['facilityType'] == 'closed' for r in ordered),
        'snapshotNotMarkedClosed': sum(r['presentAtSnapshot'] and r['facilityType'] != 'closed' for r in ordered),
        'activeOrOtherNotMarkedClosed': sum(r['facilityType'] != 'closed' for r in ordered),
        'withoutCurrentIataOrIcao': sum(not r['identifiers']['IATA'] and not r['identifiers']['ICAO'] for r in ordered),
        'withoutCurrentIataIcaoOrGps': sum(not any(r['identifiers'][s] for s in ('IATA', 'ICAO', 'GPS')) for r in ordered),
        'withTimezone': sum(r['timezone'] is not None for r in ordered),
        'curatedLinkedReferenceRecords': sum(bool(r['curatedAirportIds']) for r in ordered),
        'distinctCuratedAirportIds': len({a for r in ordered for a in r['curatedAirportIds']}),
        'recordsWithMultipleLocationHypotheses': sum(len(r['locations']) > 1 for r in ordered),
        'unresolvedLocationHypotheses': sum(p['kind'] == 'unresolved_transition_location' for r in ordered for p in r['locations']),
        'referenceLookups': {s: {'uniqueSourceRecord': sum(k.startswith(s + ':') and len(v) == 1 for k, v in code_index.items()),
                                'multipleSourceRecords': sum(k.startswith(s + ':') and len(v) > 1 for k, v in code_index.items()),
                                'multipleLocationHypotheses': sum(k.startswith(s + ':') and (len(v) > 1 or any(len(by_id[rid]['locations']) > 1 for rid in v)) for k, v in code_index.items())}
                             for s in ('IATA', 'ICAO')},
        'newVerifiedAirports': 0, 'newVerifiedAssignments': 0, 'newVerifiedNames': 0,
    }
    write_json(output / 'metrics.json', metrics)
    write_json(output / 'sources.json', {
        'ourairports': lock,
        'airportsdata': {**{k: tz_source[k] for k in ('url', 'revision', 'path', 'license')},
                         'observedAt': '2026-09-05T13:59:21+08:00',
                         'meaning': 'Timezone reference enrichment only; matching is not independent historical confirmation'},
        'airport-codes-raw': {**{k: next(s for s in source_config['sources'] if s['id'] == 'airport-codes-raw')[k]
                                    for k in ('url', 'revision', 'path', 'license')},
                              'meaning': 'Derived OurAirports numeric-ID transition observations; one source family, not independent historical confirmation'},
        'iana-tzdb': json.loads((ROOT / 'reference/timezones-lock.json').read_text()),
        'licenseScope': 'OurAirports and IANA timezone names: public domain. airportsdata: MIT; see LICENSE-airportsdata. airport-codes-raw transition evidence: ODC-PDDL-1.0. Original IDs/annotations: CC0. No primary-source documents redistributed.',
    })
    inputs = [lock_path, input_path, ROOT / 'data/airports.json', ROOT / 'reference/LICENSE-airportsdata',
              ROOT / 'schema/reference-record.schema.json',
              ROOT / 'reference/timezones-lock.json', ROOT / 'reference/inputs/iana-timezones.json',
              ROOT / 'research/discovery/sources.json', DISCOVERY / 'manifest.json', *(DISCOVERY / n for n in names),
              *sorted((ROOT / 'scripts/reference').glob('*.py'))]
    manifest(output, inputs, referenceVersion=lock['referenceVersion'], schemaVersion='1.0.0',
             evidenceStatus='reference_observations_only', historicalDataVersion=dataset['dataVersion'])
    print(canonical(metrics))
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=__import__('pathlib').Path, default=OUTPUT)
    build(parser.parse_args().output)
