"""Owner authorization, honest policy dossiers, and the original admission gate.

Trust root: owner-reviewed repository authorization registry. Activation retrieves
the actual GitHub owner comment, never a caller-supplied identity. Offline replay
does not claim a cryptographic human signature or a human reading of originals.
"""
from copy import deepcopy
import hashlib
import re
import subprocess
import sys

from policy_review import (ROOT, DIRECTORY, inputs, load, sha, require, evaluate,
                           proposed_dataset, replay_originals, write_json, digest, fixed_batches)


def grant_text(policy):
    return (f"Authorize policy {policy['policyId']}@{policy['policyVersion']} "
            f"sha256:{policy['policySha256']} scope-sha256:{sha(policy['scope'])}. "
            'Allow future low-risk records in this exact scope to be policy-reviewed and proposed in PRs. Human merge required.')


def authorization(policy):
    require(policy['status'] == 'authorized', 'Policy is not authorized')
    registry = load(DIRECTORY / 'authorizations.json')
    require(registry['formatVersion'] == 1, 'Unsupported authorization registry')
    matches = [a for a in registry['authorizations'] if a.get('policySha256') == policy['policySha256'] and
               a.get('policyId') == policy['policyId'] and a.get('policyVersion') == policy['policyVersion']]
    require(len(matches) == 1, 'Missing or ambiguous owner policy authorization')
    a = matches[0]
    require(a['state'] == 'authorized' and a['authorizedBy'] == {'login': 'keepraw', 'githubUserId': 49091395} and
            a['scopeSha256'] == sha(policy['scope']) and a['authorizationText'] == grant_text(policy) and
            a['authorizationTextSha256'] == hashlib.sha256(a['authorizationText'].encode()).hexdigest() and
            re.fullmatch(r'https://github.com/keepraw/airport-history/issues/\d+#issuecomment-\d+', a['authorizationSource']) and
            a['recordedBy'] == 'policy-activation-cli' and a['approvedOn'], 'Invalid owner policy authorization')
    return a


def medium_batch(batch_sha):
    matches = [b for b in fixed_batches(evaluate(), 'medium') if b['batchSha256'] == batch_sha]
    require(len(matches) == 1, 'Missing, changed or expanded fixed medium batch')
    return matches[0]


def batch_grant_text(batch):
    return (f"Authorize batch sha256:{batch['batchSha256']} baseline-sha256:{batch['baseline']['sha256']}. "
            'Accept only this exact medium-risk record list and its stated residual risks. Human merge required.')


def batch_authorization(batch):
    registry = load(DIRECTORY / 'batch-authorizations.json')
    require(registry['formatVersion'] == 1, 'Unsupported batch authorization registry')
    matches = [a for a in registry['authorizations'] if a.get('batchSha256') == batch['batchSha256']]
    require(len(matches) == 1, 'Missing exact owner batch authorization')
    grant = matches[0]
    require(grant['state'] == 'authorized' and grant['authorizedBy'] == {'login': 'keepraw', 'githubUserId': 49091395} and
            grant['authorizationText'] == batch_grant_text(batch) and
            grant['authorizationTextSha256'] == hashlib.sha256(grant['authorizationText'].encode()).hexdigest() and
            re.fullmatch(r'https://github.com/keepraw/airport-history/issues/\d+#issuecomment-\d+', grant['authorizationSource']) and
            grant['recordedBy'] == 'policy-activation-cli' and grant['approvedOn'], 'Invalid owner batch authorization')
    return grant


def activate(url, batch_sha=None):
    policy, *_ = inputs()
    require(policy['status'] != 'disabled' and (batch_sha or policy['status'] == 'draft'),
            'Only a draft policy can be activated; revocation needs explicit review')
    batch = medium_batch(batch_sha) if batch_sha else None
    expected = batch_grant_text(batch) if batch else grant_text(policy)
    match = re.fullmatch(r'https://github.com/keepraw/airport-history/issues/(\d+)#issuecomment-(\d+)', url or '')
    require(match, 'Use an owner GitHub issue comment URL')
    # Read only: never post a message or invent an approval on the owner's behalf.
    import json
    comment = json.loads(subprocess.check_output(['gh', 'api',
        f'repos/keepraw/airport-history/issues/comments/{match[2]}'], cwd=ROOT, text=True))
    require(comment['html_url'] == url and comment['user']['login'] == 'keepraw' and
            comment['user']['id'] == 49091395 and comment['body'].strip() == expected,
            'GitHub comment does not contain the exact owner grant')
    registry_path = DIRECTORY / ('batch-authorizations.json' if batch else 'authorizations.json')
    registry = load(registry_path)
    require(not any(a.get('batchSha256') == batch_sha if batch else a['policySha256'] == policy['policySha256']
                    for a in registry['authorizations']),
            'Policy authorization already exists')
    text = comment['body'].strip()
    grant = {'policyId': policy['policyId'], 'policyVersion': policy['policyVersion'],
        'policySha256': policy['policySha256'], 'scopeSha256': sha(policy['scope']), 'state': 'authorized',
        'authorizedBy': {'login': 'keepraw', 'githubUserId': 49091395}, 'authorizationSource': url,
        'authorizationText': text, 'authorizationTextSha256': hashlib.sha256(text.encode()).hexdigest(),
        'approvedOn': comment.get('updated_at', comment['created_at'])[:10],
        'githubCommentCreatedAt': comment['created_at'],
        'githubCommentUpdatedAt': comment.get('updated_at', comment['created_at']),
        'recordedBy': 'policy-activation-cli'}
    if batch:
        grant['batchSha256'] = batch_sha
    registry['authorizations'].append(grant)
    write_json(registry_path, registry)
    if not batch:
        policy['status'] = 'authorized'
        write_json(DIRECTORY / 'policy.json', policy)


def packet(decisions, data, *, mode='policy', reviewed_on=None):
    """Reuse original event ownership and admission evidence structure, without claiming human review."""
    policy, lock, base, _, _, _, sources, _ = inputs()
    reviewed = reviewed_on or lock['reviewedOn']
    selected = [d for d in decisions if d['sample'] == 'unpublished' and d['risk'] == ('low' if mode == 'policy' else 'medium')]
    templates = [e for n in (1, 2) for e in load(ROOT /
        f'research/evidence/global/generated/batches/global-evidence-proposal-{n}.json')['events']]
    events, dossier = [], []
    for d in selected:
        event = deepcopy(next(e for e in templates if d['recordId'] in e['proposedRecordIds']))
        existing = {p['airportId'] for p in base['airports']}
        ids = ([] if d['airportId'] in existing else [d['airportId']]) + [d['recordId']]
        event.update(status='ready_to_admit', reviewedOn=reviewed, sourceIds=d['sourceIds'],
            admittedAirportIds=ids[:-1], admittedAssignmentIds=[d['recordId']], admittedNameIds=[],
            evidenceGaps=d['residualRisks'], conflicts=[], exclusionReason=None,
            continuityInference={'evidenceType': 'continuity_inference', 'usedForAdmission': True,
                                 'note': 'Bounded policy inference. No personal owner review asserted.'},
            nextAction='Create a reviewable admission PR; human merge required.')
        for k, claim in event['claims'].items():
            claim.update(sourceIds=d['sourceIds'], conclusion='Only locked physical identity and bounded ICAO scope; other claims excluded.',
                         evidenceType='continuity_inference' if k in ('icao', 'historicalBoundary') else 'indirect')
        events.append(event)
        for rid in ids:
            dossier.append({'recordId': rid, 'decision': mode + '_accepted', 'reviewMode': mode,
                'reviewer': None if mode == 'policy' else 'keepraw',
                'reviewMeaning': 'Policy execution' if mode == 'policy' else 'Exact batch acceptance; no personal reading of originals asserted',
                'reviewedByEngine': policy['policyId'], 'policyVersion': policy['policyVersion'],
                'policySha256': policy['policySha256'], 'inputSha256': sha(lock), 'evidenceSha256': d['evidenceSha256'],
                'observations': [{'sourceId': s['sourceId'], 'observedOn': s['editionEffectiveDate'],
                    'sourceFamily': s['sourceFamily'], 'independentOriginal': True,
                    'claimScope': 'Official named physical site, ARP and bounded ICAO observations only.',
                    'basis': 'Hash-locked original and citation replay; same issuer, no independent-publisher claim.'}
                    for s in (sources[sid] for sid in d['sourceIds'])],
                'boundaryAssessment': 'Unknown first/last boundary retained; first and last local observation days excluded.',
                'continuityAssessment': d['residualRisks'][0]})
    size = policy['parameters']['maximumEventsPerBatch']
    batches = []
    for start in range(0, len(events), size):
        chunk = events[start:start+size]
        batches.append({'formatVersion': 1, 'batchId': f'policy-{sha(decisions)[:16]}-{start//size+1}',
            'baseCommit': lock['baseline']['baseCommit'], 'reviewedOn': reviewed,
            'selection': {'maximumEvents': size, 'eventCount': len(chunk), 'scope': 'Exact policy-selected records'},
            'statusCounts': {'ready_to_admit': len(chunk), 'pending_review': 0, 'excluded': 0, 'insufficient_evidence': 0},
            'admission': {'airports': sum(len(e['admittedAirportIds']) for e in chunk),
                          'assignments': len(chunk), 'names': 0,
                          'formalSources': len({sid for e in chunk for sid in e['sourceIds']})},
            'events': chunk, 'nextBatch': [], 'sources': [{**s, 'accessedOn': reviewed,
                'supportedFacts': ['Named official physical site, ARP and bounded ICAO observations.'],
                'limitations': ['Unknown outer boundaries. One issuer, no independent-publisher claim.'],
                'accessResult': 'Original hash and extraction replay required by the policy admission gate.'}
                for s in data['sources'] if any(s['sourceId'] in e['sourceIds'] for e in chunk)]})
    return batches, dossier


def receipt(decisions, data, batches, dossier, owner_grant, *, mode='policy', batch_sha=None):
    policy, lock, *_ = inputs()
    return {'formatVersion': 1, 'reviewMode': mode, 'reviewer': None if mode == 'policy' else 'keepraw',
            'batchSha256': batch_sha,
            'policyId': policy['policyId'], 'policyVersion': policy['policyVersion'], 'baseline': lock['baseline'],
            'authorizationSource': owner_grant['authorizationSource'], 'authorizedBy': owner_grant['authorizedBy'],
            'policySha256': policy['policySha256'], 'inputSha256': sha(lock),
            'decisionsSha256': sha(decisions), 'datasetSha256': sha(data), 'batchesSha256': sha(batches),
            'dossierSha256': sha(dossier), 'authorizationSha256': sha(owner_grant)}


def validate_context(base, proposed, batches, dossier, context):
    policy, lock, actual_base, *_ = inputs()
    require(context.get('reviewMode') in ('policy', 'batch') and policy['status'] != 'disabled', 'Invalid review mode')
    mode = context['reviewMode']
    batch = medium_batch(context.get('batchSha256')) if mode == 'batch' else None
    grant = batch_authorization(batch) if batch else authorization(policy)
    require(base == actual_base and digest(ROOT / 'data/airports.json') == lock['baseline']['sha256'],
            'Admission requires the latest hash-locked formal baseline')
    if not batch:
        require(lock['reviewedOn'] >= grant['approvedOn'], 'Admission review predates policy authorization; freeze a new batch')
    decisions = batch['records'] if batch else evaluate()
    reviewed = grant['approvedOn'] if batch else lock['reviewedOn']
    expected = proposed_dataset(decisions, verified=True, risks=('medium',) if batch else ('low',), reviewed_on=reviewed)
    expected_batches, expected_dossier = packet(decisions, expected, mode=mode, reviewed_on=reviewed)
    require(proposed == expected and batches == expected_batches and dossier == expected_dossier and
            context == receipt(decisions, expected, expected_batches, expected_dossier, grant,
                               mode=mode, batch_sha=batch['batchSha256'] if batch else None),
            'Altered policy decision, scope, receipt, dossier or proposal')
    replay_originals()
    return {d['recordId'] for d in dossier}


def admit(output, batch_sha=None):
    policy, lock, base, *_ = inputs()
    batch = medium_batch(batch_sha) if batch_sha else None
    grant = batch_authorization(batch) if batch else authorization(policy)  # Fail before writing any file.
    require(not output.exists(), 'Use a new output directory for an immutable admission proposal')
    decisions = batch['records'] if batch else evaluate()
    mode = 'batch' if batch else 'policy'
    reviewed = grant['approvedOn'] if batch else lock['reviewedOn']
    data = proposed_dataset(decisions, verified=True, risks=('medium',) if batch else ('low',), reviewed_on=reviewed)
    batches, dossier = packet(decisions, data, mode=mode, reviewed_on=reviewed)
    context = receipt(decisions, data, batches, dossier, grant, mode=mode, batch_sha=batch_sha)
    sys.path.insert(0, str(ROOT / 'scripts/reference'))
    from admissions import validate_admission
    counts = validate_admission(base, data, batches, dossier, policy_context=context)
    # Production schema, semantics, resolver preservation and conflicts also gate emission.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(dir=ROOT / 'work') as tmp:
        candidate = __import__('pathlib').Path(tmp) / 'data.json'
        write_json(candidate, data)
        subprocess.run(['node', 'scripts/evidence/policy_coverage.ts', 'gate', str(candidate)], cwd=ROOT, check=True)
    write_json(output / 'proposed-data.json', data)
    write_json(output / 'policy-receipt.json', context)
    write_json(output / 'dossier.json', dossier)
    for b in batches: write_json(output / 'batches' / (b['batchId'] + '.json'), b)
    print(f'Authorized policy admission proposal generated: {counts}. Human merge required.')
