"""Validate shipped research artifacts offline, including full record counts/hashes."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from core import apply_review, read_candidates, read_jsonl, stable_id
from review import REVIEW_STATUSES as STATUSES, batch_summaries, validate_review_overrides

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/discovery/generated'


def require(test, message):
    if not test:
        raise ValueError(message)


def main():
    lock = json.loads((OUT / 'manifest.json').read_text())
    for name, expected in lock['files'].items():
        path = OUT / name
        require(path.stat().st_size == expected['bytes'], f'Wrong size: {name}')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256'], f'Wrong hash: {name}')
    require(set(lock['files']) == {p.name for p in OUT.iterdir() if p.is_file() and p.name != 'manifest.json'}, 'Unmanifested artifact')
    for name, digest in {**lock['inputs'], **lock.get('reviewInputs', {})}.items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, f'Changed generation input: {name}; regenerate report')
    baseline = json.loads((ROOT / 'research/discovery/curated-baseline.json').read_text())
    # Discovery observations were generated against this immutable research input.
    # Later formal admissions may append records, never change the reviewed ones.
    frozen_path = ROOT / f"test/curated-{baseline['dataVersion']}.json"
    require(hashlib.sha256(frozen_path.read_bytes()).hexdigest() == baseline['sha256'], 'Curated historical facts changed')
    frozen = json.loads(frozen_path.read_text())
    dataset = json.loads((ROOT / 'data/airports.json').read_text())
    require(all(baseline[k] == len(frozen[k]) for k in ('airports', 'assignments', 'names', 'sources')) and
            baseline['dataVersion'] == frozen['dataVersion'], 'Curated baseline counts/version are stale')
    for key, id_key in (('airports', 'airportId'), ('assignments', 'assignmentId'), ('names', 'nameId'), ('sources', 'sourceId')):
        current = {r[id_key]: r for r in dataset[key]}
        require(all(current.get(r[id_key]) == r for r in frozen[key]), f'Frozen research baseline {key} changed')
    # Every earlier reviewed dataset stays protected: its records must survive byte-for-byte as JSON values.
    for previous in baseline['preservedBaselines']:
        raw = (ROOT / previous['record']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == previous['sha256'], f"Preserved curated record changed: {previous['record']}")
        frozen = json.loads(raw)
        for key, id_key in (('airports', 'airportId'), ('assignments', 'assignmentId'), ('names', 'nameId'), ('sources', 'sourceId')):
            current = {r[id_key]: r for r in dataset[key]}
            require(all(current.get(r[id_key]) == r for r in frozen[key]),
                    f"Pre-{dataset['dataVersion']} curated {key} changed or removed (baseline {previous['dataVersion']})")
    airports = {r['airportId'] for r in dataset['airports']}
    assignments = {r['assignmentId'] for r in dataset['assignments']}
    names = {r['nameId'] for r in dataset['names']}
    config = json.loads((ROOT / 'research/discovery/sources.json').read_text())
    reviews = json.loads((ROOT / 'research/discovery/reviews.json').read_text())
    review_ids = set(reviews)
    seen_reviews = set()
    reviewed_rows = {}
    grand_total = 0
    all_ids = set()
    for source in config['sources']:
        sid = source['id']
        report = json.loads((OUT / (sid + '.coverage.json')).read_text())
        require(report['sourceId'] == sid and report['revision'] == source['revision'] and report['path'] == source['path'], f'Stale source coverage: {sid}; run research:scan')
        ids = set()
        counts, types, countries, years = Counter(), Counter(), Counter(), Counter()
        observations = 0
        for row in read_candidates(OUT, sid):
            cid = row['candidateId']
            require(cid not in ids, f'Duplicate candidate {cid}')
            ids.add(cid)
            if cid in review_ids:
                seen_reviews.add(cid)
                reviewed_rows[cid] = row
                reviewed = apply_review(row, reviews)['review']
                require(reviewed['status'] in STATUSES, 'Unknown live review status')
                require(reviewed.get('nextAction') and reviewed.get('evidenceGaps'), 'Incomplete live review')
                if reviewed['status'] == 'excluded':
                    require(reviewed.get('exclusionReason'), 'Missing live exclusion reason')
            extra = 'baseline_closed_record' if row['types'] == ['baseline_closed_record'] else None
            require(cid == stable_id('cand_', [sid, row['sourceEntityId'], row['changes'], extra]), f'Unstable ID {cid}')
            require(row['sourceId'] == sid, 'Wrong source')
            require(row['review']['status'] in STATUSES, 'Unknown review status')
            require(row['time']['eventDate'] is None and row['time']['eventDatePrecision'] == 'unknown', 'Machine revision promoted to event date')
            require(row['evidence']['evidenceType'] == 'indirect' and row['evidence']['verificationStatus'] == 'pending', 'Machine revision promoted to verified fact')
            for observation in row['observations']:
                require(all(re.fullmatch('[a-f0-9]{40}', observation[k]) for k in ('commit', 'beforeBlob', 'afterBlob')), 'Unpinned observation')
            require(set(row['matches']['airportIds']) <= airports, 'Missing airport match')
            require(set(row['matches']['assignmentIds']) <= assignments, 'Missing assignment match')
            require(set(row['matches']['nameIds']) <= names, 'Missing name match')
            if row['review']['status'] == 'excluded':
                require(bool(row['review']['exclusionReason']), 'Missing exclusion reason')
            observations += len(row['observations'])
            counts[row['review']['status']] += 1
            types.update(row['types'])
            countries[row['context']['country']] += 1
            years[row['time']['firstObservedRevisionAt'][:4]] += 1
        d = report['discovery']
        require(len(ids) == d['candidates'] and observations == d['rawCandidateObservations'], f'Wrong totals: {sid}')
        for actual, key in [(counts, 'byStatus'), (types, 'byType'), (countries, 'byCountry'), (years, 'byObservationYear')]:
            require(dict(actual) == d[key], f'Wrong {key}: {sid}')
        versions = list(read_jsonl(OUT / (sid + '.versions.jsonl.gz')))
        require(len(versions) == report['history']['parentDiffs'], f'Wrong version edge count: {sid}')
        require(len({v['commit'] for v in versions}) == report['history']['fileChangingCommits'], f'Wrong commit count: {sid}')
        unique = {v['afterBlob']: v['afterRecords'] for v in versions}
        require(len(unique) == report['history']['uniqueFileVersions'], f'Wrong unique version count: {sid}')
        require(sum(v is None for v in unique.values()) == report['history']['unparsedFileVersions'], f'Wrong parse-gap count: {sid}')
        require(sum(1 for _ in read_jsonl(OUT / (sid + '.gaps.jsonl.gz'))) == report['history']['blockedComparisons'], f'Wrong blocked comparison count: {sid}')
        require(sum(n or 0 for n in unique.values()) == report['history']['recordVersionsProcessed'], f'Wrong record-version count: {sid}')
        entity_count = sum(1 for _ in read_jsonl(OUT / (sid + '.entities.jsonl.gz')))
        require(entity_count == report['history']['entitiesEverObserved'], f'Wrong inventory count: {sid}')
        grand_total += len(ids)
        require(not (all_ids & ids), 'Cross-source ID collision')
        all_ids.update(ids)
    require(review_ids == seen_reviews, 'Orphaned review override; never silently discard curation')
    summary = json.loads((OUT / 'summary.json').read_text())
    require(summary['sourceRevisionCandidates'] == grand_total, 'Wrong global source total')
    link_count = 0
    for row in read_jsonl(OUT / 'code-links.candidates.jsonl.gz'):
        require(set(row['relatedCandidateIds']) <= all_ids, 'Dangling code-link candidate reference')
        link_count += 1
    require(link_count == summary['codeAssociationCandidates'], 'Wrong relational candidate count')
    group_count, excess = 0, 0
    for row in read_jsonl(OUT / 'duplicate-groups.jsonl.gz'):
        require({m['candidateId'] for m in row['members']} <= all_ids, 'Dangling duplicate-group member')
        group_count += 1
        excess += len(row['members'])-1
    require(group_count == summary['exactCrossSourceDuplicateGroups']['groups'], 'Wrong duplicate-group total')
    require(grand_total-excess == summary['sourceTransitionLeadsAfterExactCrossSourceGrouping'], 'Wrong deduplicated total')
    legacy = json.loads((ROOT / 'research/discovery/legacy.json').read_text())
    require(sum(r['status'] == 'insufficient_evidence' for r in legacy) >= 8, 'Lost deferred leads')
    batches = batch_summaries(ROOT)
    require(summary.get('reviewBatches', []) == batches, 'Stale batch review summary')
    known_ids = all_ids | {r['candidateId'] for r in legacy}
    batch_records = [(entry['path'], json.loads((ROOT / entry['path']).read_text())) for entry in batches]
    validate_review_overrides(reviews, batch_records)
    for _, batch in batch_records:
        for event in batch['events']:
            ids = event['candidateIds'] + event['relatedCandidateIds']
            require(set(ids) <= known_ids, 'Dangling reviewed candidate')
            observation = event.get('sourceObservation')
            if observation:
                raw = reviewed_rows[observation['candidateId']]
                require(all(observation[k] == raw[k] for k in ('sourceId', 'sourceEntityId', 'changes', 'observations')), 'Review altered pinned source transition')
        for follow_up in batch.get('followUps', []):
            require(set(follow_up.get('admittedAirportIds', [])) <= airports, 'Follow-up admits a missing airport')
            require(set(follow_up.get('admittedAssignmentIds', [])) <= assignments, 'Follow-up admits a missing assignment')
            require(set(follow_up.get('admittedNameIds', [])) <= names, 'Follow-up admits a missing name')
        for lead in batch['nextBatch']:
            require(lead['candidateId'] in known_ids, 'Dangling next-batch lead')
    require(set(lock.get('reviewInputs', {})) == {'research/discovery/reviews.json', *(r['path'] for r in batches)}, 'Unmanifested review evidence')
    print(f'Validated {grand_total:,} source candidates, {link_count:,} code-association leads, {len(legacy)} legacy leads; curated data matches the reviewed baseline and preserved earlier records.')
    print(f'Validated {len(batches)} bounded review batch(es), {len(reviews)} live candidate review overrides.')


if __name__ == '__main__':
    main()
