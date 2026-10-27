"""Validate bounded, claim-specific admission reviews independently of discovery."""
import json
import re
from collections import Counter

DISPOSITIONS = {'ready_to_admit', 'insufficient_evidence', 'excluded', 'pending_review'}
REVIEW_STATUSES = DISPOSITIONS | {'pending_investigation', 'already_curated'}
CLAIMS = {'physicalIdentity', 'iata', 'icao', 'historicalBoundary', 'historicalNames', 'closureAndReplacement'}
EVIDENCE = {'primary_direct', 'indirect', 'continuity_inference'}
MAX_EVENTS = 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_batch(batch):
    events = batch['events']
    ceiling = batch['selection']['maximumEvents']
    require(isinstance(ceiling, int) and 0 < ceiling <= MAX_EVENTS, 'Wrong batch ceiling')
    require(len(events) <= MAX_EVENTS, 'A verification batch must contain at most 20 events')
    # A batch may hold only follow-ups (e.g. an admission review of earlier events) but never nothing.
    require(events or batch.get('followUps'), 'A verification batch must review at least one event or follow-up')
    require(len(events) <= ceiling, f'A verification batch must contain at most {ceiling} events')
    require(batch['selection']['eventCount'] == len(events), 'Wrong reviewed event count')
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
    for follow_up in batch.get('followUps', []):
        validate_follow_up(follow_up, sources)


def validate_follow_up(follow_up, sources):
    """A follow-up re-investigates an event owned by an earlier batch; it never maps candidates."""
    require(follow_up.get('candidateIds') == [], 'Follow-up must not map candidates; the earlier batch keeps the sole mapping')
    for key in ('eventGroupId', 'priorBatchId', 'priorStatus', 'currentStatus', 'nextAction'):
        require(isinstance(follow_up.get(key), str) and follow_up[key].strip(), f'Missing follow-up {key}')
    require(follow_up['priorStatus'] in DISPOSITIONS and follow_up['currentStatus'] in DISPOSITIONS, 'Unknown follow-up disposition')
    require(isinstance(follow_up.get('dispositionChanged'), bool), 'Missing follow-up disposition flag')
    require(follow_up['dispositionChanged'] == (follow_up['priorStatus'] != follow_up['currentStatus']), 'Follow-up disposition flag disagrees with statuses')
    if follow_up['dispositionChanged']:
        require(follow_up.get('changeReason'), 'Changed follow-up disposition lacks a documented reason')
    require(follow_up.get('searches') and follow_up.get('negativeResults') is not None, 'Follow-up lacks documented searches/negative results')
    require(follow_up.get('remainingGaps') or follow_up['currentStatus'] == 'ready_to_admit', 'Follow-up lacks retained gaps')
    admitted = [follow_up.get(k, []) for k in ('admittedAirportIds', 'admittedAssignmentIds', 'admittedNameIds')]
    if follow_up['currentStatus'] != 'ready_to_admit':
        require(not any(admitted), 'Unready follow-up promoted to formal data')
    require(follow_up.get('sourceIds') and set(follow_up['sourceIds']) <= sources.keys(), 'Unknown follow-up evidence source')
    require(set(follow_up.get('claimFindings', {})) == CLAIMS, 'Missing claim-specific follow-up findings')
    for claim in follow_up['claimFindings'].values():
        require(claim['conclusion'] and claim['evidenceType'] in EVIDENCE, 'Missing follow-up claim basis')
        require(claim['sourceIds'] and set(claim['sourceIds']) <= set(follow_up['sourceIds']), 'Dangling follow-up claim source')
        if claim['evidenceType'] == 'primary_direct':
            require(any(sources[s]['sourceType'] == 'primary' for s in claim['sourceIds']), 'Primary follow-up claim lacks primary publication')


def batch_order(batch_id):
    require(isinstance(batch_id, str) and batch_id, 'Missing batch ID')
    match = re.fullmatch(r'(.*?)-(\d+)', batch_id)
    # Numbered series sort numerically (global-2 before global-10); other IDs sort lexically.
    return (match.group(1), int(match.group(2))) if match else (batch_id, -1)


def validate_batch_series(batches):
    """Check all completed batches together: unique IDs and mappings, follow-ups only reference earlier events."""
    ordered = sorted(batches, key=lambda b: batch_order(b['batchId']))
    batch_ids, events, candidates, chain = set(), {}, {}, {}
    for batch in ordered:
        validate_batch(batch)
        require(batch['batchId'] not in batch_ids, f"Duplicate batch ID: {batch['batchId']}")
        for follow_up in batch.get('followUps', []):
            target = events.get(follow_up['eventGroupId'])
            require(target is not None, f"Follow-up references no earlier event: {follow_up['eventGroupId']}")
            owner, event = target
            require(follow_up['priorBatchId'] == owner, f"Follow-up names the wrong owning batch: {follow_up['eventGroupId']}")
            # Follow-ups form an ordered chain from the owning batch's original disposition.
            require(chain[follow_up['eventGroupId']] == follow_up['priorStatus'],
                    f"Follow-up prior status breaks the disposition chain: {follow_up['eventGroupId']}")
            chain[follow_up['eventGroupId']] = follow_up['currentStatus']
        batch_ids.add(batch['batchId'])
        for event in batch['events']:
            for cid in event['candidateIds'] + event['relatedCandidateIds']:
                require(cid not in candidates, f'Candidate maps to multiple batch events: {cid}')
                candidates[cid] = event['eventGroupId']
            require(event['eventGroupId'] not in events, f"Duplicate event group across batches: {event['eventGroupId']}")
            events[event['eventGroupId']] = (batch['batchId'], event)
            history = event.get('dispositionHistory', [])
            for entry in history:
                require(entry.get('status') in DISPOSITIONS and entry.get('recordedIn') and entry.get('reason'),
                        f"Incomplete disposition history: {event['eventGroupId']}")
            chain[event['eventGroupId']] = history[0]['status'] if history else event['status']
    for group, (owner, event) in events.items():
        history = event.get('dispositionHistory', [])
        require(not history or history[0]['recordedIn'] == owner, f"Disposition history must start in the owning batch: {group}")
    for group, status in chain.items():
        # The owning record is the live disposition; the last follow-up must agree with it.
        require(events[group][1]['status'] == status, f"Follow-up status disagrees with owning event: {group}")
    return candidates


def batch_summaries(root):
    result, batches = [], []
    for path in sorted((root / 'research/discovery/batches').glob('*.json')):
        batch = json.loads(path.read_text())
        batches.append(batch)
        entry = {'batchId': batch['batchId'], 'path': str(path.relative_to(root)),
                 'reviewedOn': batch['reviewedOn'], 'eventCount': len(batch['events']),
                 'statusCounts': batch['statusCounts'], 'admission': batch['admission']}
        if batch.get('followUps'):
            entry['followUps'] = [{'eventGroupId': f['eventGroupId'], 'priorBatchId': f['priorBatchId'],
                                   'currentStatus': f['currentStatus'], 'dispositionChanged': f['dispositionChanged']}
                                  for f in batch['followUps']]
        result.append(entry)
    validate_batch_series(batches)
    result.sort(key=lambda entry: batch_order(entry['batchId']))
    return result


def validate_review_overrides(reviews, batches):
    """Check live overrides against all completed batches before publishing them."""
    require(isinstance(reviews, dict), 'Review overrides must be an object')
    candidate_events = {}
    seen_ids = set()
    validate_batch_series([batch for _, batch in batches])
    for batch_path, batch in batches:
        for event in batch['events']:
            for cid in event['candidateIds'] + event['relatedCandidateIds']:
                require(isinstance(cid, str) and cid.startswith(('cand_', 'legacy-')), 'Invalid reviewed candidate ID')
                require(cid not in seen_ids, f'Candidate maps to multiple batch events: {cid}')
                seen_ids.add(cid)
                # Legacy leads retain their review in legacy.json, not overrides.
                if cid.startswith('cand_'):
                    candidate_events[cid] = (event, batch_path)
    require(not (set(candidate_events) - set(reviews)), 'Missing candidate review mappings')
    require(not (set(reviews) - set(candidate_events)), 'Orphaned candidate review overrides')
    for cid, override in reviews.items():
        require(isinstance(override, dict), f'Invalid review override: {cid}')
        status = override.get('status')
        require(isinstance(status, str) and status in REVIEW_STATUSES, f'Invalid review status: {cid}')
        event, batch_path = candidate_events[cid]
        require(status == event['status'], f'Review status disagrees with batch: {cid}')
        require(override.get('eventGroupId') == event['eventGroupId'], f'Review event group disagrees with batch: {cid}')
        require(override.get('evidenceReview') == batch_path, f'Review evidence path disagrees with batch: {cid}')
        action = override.get('nextAction')
        require(isinstance(action, str) and action.strip(), f'Missing review nextAction: {cid}')
        gaps = override.get('evidenceGaps')
        require(isinstance(gaps, list) and gaps and all(isinstance(g, str) and g.strip() for g in gaps),
                f'Missing review evidenceGaps: {cid}')
        if status == 'excluded':
            reason = override.get('exclusionReason')
            require(isinstance(reason, str) and reason.strip(), f'Missing review exclusionReason: {cid}')
