"""Batch-process existing worldwide transitions; never rescan upstream Git history."""
import argparse
import json
import sqlite3
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from common import (ROOT, DISCOVERY, OUTPUT, canonical, checked, distance, manifest, read_jsonl, stable_id,
                    verify_discovery, write_json, write_jsonl)

OUT = ROOT / 'reference/triage'
FAMILIES = {'ourairports': 'ourairports', 'airport-codes': 'ourairports',
            'airport-codes-raw': 'ourairports', 'airport-codes-initial': 'ourairports',
            'airport-codes-legacy': 'ourairports', 'airportsdata': 'lineage_unestablished',
            'mwgg': 'lineage_unestablished', 'airportsdata-city-codes': 'city_membership'}
EVENT_TYPES = {'iata_change', 'possible_relocation', 'possible_closure', 'possible_reopening', 'possible_rename'}


def reference_locations():
    lock = json.loads((OUTPUT / 'manifest.json').read_text())
    locations = {}
    for shard in '0123456789abcdef':
        filename = f'records.{shard}.jsonl.gz'
        checked(OUTPUT / filename, lock['files'][filename]['sha256'])
        for record in read_jsonl(OUTPUT / filename):
            locations[record['referenceId']] = record['locations']
    return lock, locations


def match_reference(entity, locations):
    candidate = stable_id('ref_', ['ourairports', entity]) if entity else None
    if candidate is not None and candidate in locations:
        return {'referenceId': candidate, 'basis': 'numeric_external_record_only', 'verifiedPhysicalIdentity': False}
    return {'referenceId': None, 'basis': 'numeric_external_record_unavailable' if entity else 'unestablished',
            'verifiedPhysicalIdentity': False}


def classify(candidate):
    kinds = set(candidate['types'])
    changes = candidate['changes']
    if 'city_code_membership_change' in kinds:
        return 'city_membership_excluded'
    # New empty ICAO columns produced tens of thousands of leads. These are not allocation events.
    if not (kinds & EVENT_TYPES) and 'icao_change' in kinds and not any(changes.get('icao', [])):
        return 'empty_namespace_backfill_excluded'
    if not (kinds & EVENT_TYPES) and not ('icao_change' in kinds and any(changes.get('icao', []))):
        return 'non_event_revision_deferred'
    if (candidate.get('distanceKm') or 0) >= 5:
        return 'location_change_or_directory_correction'
    if kinds & {'iata_change', 'icao_change'}:
        return 'code_change_observation'
    if kinds & {'possible_closure', 'possible_reopening'}:
        return 'closure_or_reopening_observation'
    return 'name_label_observation'


def build(output=OUT):
    lock = json.loads((DISCOVERY / 'manifest.json').read_text())
    names = sorted(n for n in lock['files'] if '.candidates.' in n and n != 'code-links.candidates.jsonl.gz')
    verify_discovery([*names, 'duplicate-groups.jsonl.gz'])
    reviewed = json.loads((ROOT / 'research/discovery/reviews.json').read_text())
    stats, classifications = Counter(), Counter()
    reference_lock, locations_by_reference = reference_locations()
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / 'work').mkdir(exist_ok=True)
    # Disk-backed joins keep memory bounded and never rewrite original candidate payloads.
    with tempfile.TemporaryDirectory(dir=ROOT / 'work', prefix='triage-') as temp:
        db = sqlite3.connect(str(Path(temp) / 'join.sqlite'))
        db.executescript('''
            CREATE TABLE selected (id TEXT PRIMARY KEY, groupid TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX selected_group ON selected(groupid,id);
        ''')
        for name in names:
            for candidate in read_jsonl(DISCOVERY / name):
                stats['sourceCandidatesInspected'] += 1
                classification = classify(candidate)
                classifications[classification] += 1
                if classification.endswith('_excluded'):
                    stats['mechanicallyExcludedCandidates'] += 1
                    continue
                if classification == 'non_event_revision_deferred':
                    stats['nonEventCandidatesDeferred'] += 1
                    continue
                observations = candidate['observations']
                payload = {
                    'candidateId': candidate['candidateId'], 'sourceId': candidate['sourceId'],
                    'sourceEntityId': candidate['sourceEntityId'], 'classification': classification,
                    'sourceFamily': FAMILIES[candidate['sourceId']], 'types': candidate['types'],
                    'distanceKm': candidate['distanceKm'], 'country': candidate['context']['country'],
                    'name': candidate['context']['airport'], 'changes': candidate['changes'],
                    'firstRevisionObservedAt': min(o['observedAt'] for o in observations),
                    'lastRevisionObservedAt': max(o['observedAt'] for o in observations),
                    'observationCount': len(observations),
                    'alreadyReviewed': candidate['candidateId'] in reviewed,
                }
                db.execute('INSERT INTO selected VALUES (?,?,?)',
                           (candidate['candidateId'], stable_id('lead_', [candidate['candidateId']]), canonical(payload)))
                stats['selectedCandidates'] += 1
                stats['selectedSourceObservations'] += len(observations)
            db.commit()
        # The existing exact normalized transition groups are reused as-is. Similar codes/names
        # alone never group events. Recurrences retain observation counts and original IDs.
        for group in read_jsonl(DISCOVERY / 'duplicate-groups.jsonl.gz'):
            db.executemany('UPDATE selected SET groupid=? WHERE id=?',
                           ((group['eventGroupId'], m['candidateId']) for m in group['members']))
        db.commit()
        def groups():
            cursor = db.execute('SELECT groupid, group_concat(payload, char(10)) FROM '
                                '(SELECT * FROM selected ORDER BY groupid,id) GROUP BY groupid ORDER BY groupid')
            for gid, payloads in cursor:
                members = [json.loads(p) for p in payloads.split('\n')]
                families = sorted({m['sourceFamily'] for m in members})
                already = any(m['alreadyReviewed'] for m in members)
                stats['eventGroups'] += 1
                stats['groupsAlreadyUnderReview'] += already
                stats['groupsAwaitingEvidence'] += not already
                stats['duplicateMembersGrouped'] += len(members) - 1
                stats['groupsWithOurairportsDerivatives'] += sum(m['sourceFamily'] == 'ourairports' for m in members) > 1
                primary = next((m for m in members if m['sourceId'] == 'ourairports'), None)
                if primary is None:
                    primary = next((m for m in members if m['sourceId'] in ('airport-codes-raw', 'airport-codes-initial') and m['sourceEntityId'].isdigit()), None)
                entity = primary['sourceEntityId'] if primary else None
                match = match_reference(entity, locations_by_reference)
                stats['groupsLinkedToReferenceRecord'] += match['referenceId'] is not None
                stats['groupsWithoutReferenceRecordMatch'] += match['referenceId'] is None
                stats['groupsWithUnavailableNumericReferenceRecord'] += match['basis'] == 'numeric_external_record_unavailable'
                yield {
                    'eventGroupId': gid, 'evidenceStatus': 'unresolved_historical_lead',
                    'historicallyVerified': False, 'status': 'existing_review' if already else 'awaiting_primary_evidence',
                    'candidateIds': [m['candidateId'] for m in members],
                    'members': [{k: m[k] for k in ('candidateId', 'sourceId', 'sourceEntityId', 'classification',
                                                'distanceKm', 'firstRevisionObservedAt', 'lastRevisionObservedAt', 'observationCount')} for m in members],
                    'sourceFamilies': families, 'independentHistoricalConfirmations': 0,
                    'physicalMatch': match,
                    'country': members[0]['country'], 'name': members[0]['name'],
                    'classifications': sorted({m['classification'] for m in members}),
                    'eventDate': None, 'proposedHistoricalIntervals': [],
                    'evidenceGaps': ['Dated authoritative code/identity evidence and effective-date bounds require review.',
                                     'OurAirports derivatives are one source family; other directory lineage is unestablished.',
                                     'A source revision may be a correction; its timestamp is not an event date.'],
                    'nextAction': 'Attach claim-specific authoritative observations, review physical continuity and boundaries, then export bounded admission batches.',
                }
        write_jsonl(output / 'groups.jsonl.gz', groups())
        db.close()
    # Geographically distinct code associations are review leads, not proven transfers.
    reuse = []
    for scheme in ('IATA', 'ICAO'):
        filename = f'index.{scheme}.jsonl.gz'
        checked(OUTPUT / filename, reference_lock['files'][filename]['sha256'])
        for association in read_jsonl(OUTPUT / filename):
            locations = [(rid, p) for rid in association['referenceIds'] for p in locations_by_reference[rid]]
            distinct = any((distance(a[1]['coordinates'], b[1]['coordinates']) or 0) >= 5
                           for i, a in enumerate(locations) for b in locations[i + 1:])
            if distinct:
                reuse.append({'scheme': scheme, 'code': association['key'],
                              'referenceIds': association['referenceIds'],
                              'locationIds': sorted({p['locationId'] for _, p in locations}),
                              'classification': 'geographically_distinct_code_associations',
                              'historicallyVerified': False, 'eventDate': None,
                              'meaning': 'Possible reuse, source repurposing or directory error; code-to-location chronology requires independent review.'})
    write_jsonl(output / 'code-reuse-leads.jsonl.gz', reuse)
    stats['geographicallyDistinctCodeLeads'] = len(reuse)
    stats['newVerifiedHistoricalAdmissions'] = 0
    metrics = {**dict(stats), 'candidateClassifications': dict(classifications), 'maximumEventsPerReviewBatch': 20}
    write_json(output / 'metrics.json', metrics)
    inputs = [DISCOVERY / 'manifest.json', ROOT / 'research/discovery/reviews.json',
              *(DISCOVERY / n for n in [*names, 'duplicate-groups.jsonl.gz']),
              OUTPUT / 'manifest.json', *(OUTPUT / n for n in reference_lock['files']),
              ROOT / 'scripts/reference/triage.py', ROOT / 'scripts/reference/common.py']
    manifest(output, inputs, schemaVersion='1.0.0', evidenceStatus='unresolved_historical_leads')
    print(canonical(metrics))
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    build(parser.parse_args().output)
