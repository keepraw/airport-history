"""Validate bounded, claim-specific admission reviews independently of discovery."""
import json
import re
from collections import Counter

DISPOSITIONS = {'ready_to_admit', 'insufficient_evidence', 'excluded', 'pending_review'}
CLAIMS = {'physicalIdentity', 'iata', 'icao', 'historicalBoundary', 'historicalNames', 'closureAndReplacement'}
EVIDENCE = {'primary_direct', 'indirect', 'continuity_inference'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_batch(batch):
    events = batch['events']
    require(0 < len(events) <= 20, 'A verification batch must contain at most 20 events')
    require(batch['selection']['eventCount'] == len(events), 'Wrong reviewed event count')
    require(batch['selection']['maximumEvents'] == 20, 'Wrong batch ceiling')
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', batch['reviewedOn']), 'Missing review date')
    counts = Counter(e['status'] for e in events)
    require(all(batch['statusCounts'].get(s, 0) == counts[s] for s in DISPOSITIONS), 'Wrong batch dispositions')
    require(set(counts) <= DISPOSITIONS, 'Unreviewed event in completed batch')
    sources = {s['sourceId']: s for s in batch['sources']}
    require(len(sources) == len(batch['sources']), 'Duplicate review source')
    for source in sources.values():
        require(source['url'].startswith('https://'), 'Missing concrete source URL')
        require(source['sourceType'] in {'primary', 'secondary'}, 'Unknown publication type')
        require(source['accessedOn'] == batch['reviewedOn'], 'Wrong source review date')
        require(source['supportedFacts'] and source['limitations'] and source['accessResult'], 'Missing source scope/access limits')
        require(source['license']['id'] and source['license']['note'], 'Missing review source license restrictions')
    groups, ids = set(), set()
    for event in events:
        require(event['eventGroupId'] not in groups, 'Duplicate event group')
        groups.add(event['eventGroupId'])
        require(event['reviewedOn'] == batch['reviewedOn'], 'Wrong event review date')
        related = event['candidateIds'] + event['relatedCandidateIds']
        require(related and not (ids & set(related)) and len(set(related)) == len(related), 'Duplicate or empty candidate mapping')
        ids.update(related)
        require(set(event['sourceIds']) <= sources.keys(), 'Unknown event evidence source')
        require(set(event['claims']) == CLAIMS, 'Missing claim-specific review')
        for claim in event['claims'].values():
            require(claim['conclusion'] and claim['evidenceType'] in EVIDENCE, 'Missing claim basis')
            require(claim['sourceIds'] and set(claim['sourceIds']) <= set(event['sourceIds']), 'Dangling claim source')
            if claim['evidenceType'] == 'primary_direct':
                require(any(sources[s]['sourceType'] == 'primary' for s in claim['sourceIds']), 'Primary claim lacks primary publication')
        require(event['continuityInference']['evidenceType'] == 'continuity_inference', 'Missing continuity assessment')
        require(event['nextAction'], 'Missing next review action')
        if event['status'] != 'ready_to_admit':
            require(event['evidenceGaps'], 'Deferred/excluded event lacks retained gaps')
            require(not any(event[k] for k in ('admittedAirportIds', 'admittedAssignmentIds', 'admittedNameIds')), 'Unready event promoted to formal data')
        if event['status'] == 'excluded':
            require(event['exclusionReason'], 'Missing exclusion reason')
        if event['status'] == 'pending_review':
            require(event['conflicts'], 'Missing independent-review conflict')


def batch_summaries(root):
    result = []
    for path in sorted((root / 'research/discovery/batches').glob('*.json')):
        batch = json.loads(path.read_text())
        validate_batch(batch)
        result.append({'batchId': batch['batchId'], 'path': str(path.relative_to(root)),
                       'reviewedOn': batch['reviewedOn'], 'eventCount': len(batch['events']),
                       'statusCounts': batch['statusCounts'], 'admission': batch['admission']})
    return result
