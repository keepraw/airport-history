"""Replay the exact thirteen owner-approved records through the existing admission gate."""
import json
from pathlib import Path
import subprocess
import tempfile

from pipeline import ROOT
from common import checked
from admissions import validate_admission
from review import validate_batch_series

REVIEW = ROOT / 'research/admissions/0.9.0'
PREPARATION = ROOT / 'research/evidence/first-admission'
BASELINE = ROOT / 'test/curated-0.8.0.json'
BASE_SHA256 = 'b7880507c50cf8f993c98b3ec66f34e6433c452d7637eea7c6bfe61edbf166a3'
CODES = {'VOSR', 'VOGB', 'VEKI', 'VEPY', 'VOKU', 'LELC'}


def load(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_records(dataset, approval, dossier, source_reviews, batches):
    checked(BASELINE, BASE_SHA256)
    checked(ROOT / approval['selectionPath'], approval['selectionSha256'])
    selection, base = load(PREPARATION / 'selection.json'), load(BASELINE)
    require(approval['authorizedBy'] == {'login': 'keepraw', 'githubUserId': 49091395} and
            approval['approvedOn'] == '2026-10-29' and approval['recordedBy'] == 'Codex' and
            approval['authorizationSource'] and approval['authorizationMeaning'], 'Missing truthful owner authorization')
    require(approval['baseCommit'] == 'f43e172d8833317086a94d0c23302b42f509dcee' and
            approval['baseDataset'] == 'test/curated-0.8.0.json' and approval['baseSha256'] == BASE_SHA256,
            'Wrong reviewed admission baseline')
    require(dataset['dataVersion'] == '0.9.0' and dataset['schemaVersion'] == '3.0.0', 'Wrong data/schema version')
    physical = selection['physicalAirports']
    assignments = [a for a in selection['assignments'] if a['code'] in CODES]
    require(approval['approvedPhysicalAirports'] == [{'recordId': p['recordId'], 'exactAuthorization': p['exactAuthorization']} for p in physical]
            and len(physical) == 7, 'Physical authorization differs from PR16 exact attributes')
    require(approval['approvedAssignments'] == [{'recordId': a['recordId'], 'exactAuthorization': a['exactAuthorization']} for a in assignments]
            and len(assignments) == 6, 'Assignment authorization exceeds exact six PR16 scopes')
    require(approval['deferredAssignmentIds'] == [a['recordId'] for a in selection['assignments'] if a['code'] not in CODES],
            'Deferred authorization scope changed')
    expected_ids = {r['recordId'] for r in [*physical, *assignments]}
    require(len(dossier) == 13 and {d['recordId'] for d in dossier} == expected_ids, 'Wrong per-record claim review scope')
    by_id = {d['recordId']: d for d in dossier}
    for d in dossier:
        require(d['decision'] == 'accepted' and d['reviewer'] == 'keepraw' and d['reviewedOn'] == approval['approvedOn'],
                'Missing explicit human claim review')
        require(d['reviewBasis']['approvalId'] == approval['approvalId'] and d['reviewBasis']['recordedBy'] == 'Codex',
                'Wrong per-record approval provenance')
    for p in physical:
        actual = next((a for a in dataset['airports'] if a['airportId'] == p['recordId']), None)
        expected = {k: v for k, v in p['exactAuthorization'].items() if k != 'scope'}
        require(actual == expected == by_id[p['recordId']]['approvedRecord'], 'Unapproved physical/reference attribute change')
    for a in assignments:
        actual = next((r for r in dataset['assignments'] if r['assignmentId'] == a['recordId']), None)
        require(actual is not None and actual == by_id[a['recordId']]['approvedRecord'], 'Dossier differs from admitted assignment')
        for key, value in a['exactAuthorization'].items():
            if key not in ('recordId', 'requiresSeparatePhysicalIdentityApproval'):
                require(actual[key] == value, 'Assignment exceeds exact approved window or source scope')
        require(actual['verificationStatus'] == 'verified' and actual['verifiedOn'] == approval['approvedOn'], 'Missing assignment verification')
    used = {sid for p in physical for sid in p['evidenceSourceIds']} | {sid for a in assignments for sid in a['evidenceSourceIds']}
    old_sources = {s['sourceId'] for s in base['sources']}
    formal_sources = {s['sourceId']: s for s in dataset['sources'] if s['sourceId'] not in old_sources}
    require(len(source_reviews) == 18 and len({s['sourceId'] for s in source_reviews}) == 18 and
            set(formal_sources) == used == {s['sourceId'] for s in source_reviews}, 'Unused, duplicate or missing reviewed source')
    lock = {s['sourceId']: s for s in load(PREPARATION / 'source-lock.json')['sources']}
    for s in source_reviews:
        pinned = lock[s['sourceId']]
        for key in ('originalSha256', 'textOriginalSha256', 'excerptSha256', 'excerptPath', 'originalPublicationKey',
                    'sourceFamily', 'documentEffectiveDate', 'editionEffectiveDate', 'componentEffectiveDate', 'publicationDate', 'rights'):
            require(s[key] == pinned[key], 'Original provenance/date/rights changed')
        checked(PREPARATION / s['excerptPath'], s['excerptSha256'])
        excerpt = load(PREPARATION / s['excerptPath'])
        require(excerpt['originalSha256'] == s['originalSha256'] and excerpt['textOriginalSha256'] == s['textOriginalSha256'],
                'Detached original citation')
        require(excerpt['spans'] and all(p['characterEnd'] - p['characterStart'] == len(p['quote']) for p in excerpt['spans']),
                'Malformed minimal citation')
        formal = formal_sources[s['sourceId']]
        require(formal['url'] == s['url'] and formal['sourceType'] == 'primary' and formal['license']['id'] and
                formal['verificationStatus'] == s['verificationStatus'] == 'verified', 'Unreviewed formal source')
        require(formal['accessedOn'] == s['accessedAt'][:10] <= s['reviewedOn'] == approval['approvedOn'], 'Invalid source chronology')
        require(s['contentCheckedBy'] == 'Codex' and s['claimApprovalBy'] == 'keepraw' and s['approvalId'] == approval['approvalId']
                and s['supportedFacts'] and s['limitations'] and s['originalVerification'], 'Missing scoped source review')
    for d in dossier:
        for o in d['observations']:
            require(o['sourceId'] in used and o['originalSha256'] == lock[o['sourceId']]['originalSha256'] and
                    o['textOriginalSha256'] == lock[o['sourceId']]['textOriginalSha256'], 'Unlinked dossier observation')
    # Canonical proposal owners are reused; readiness grants only the listed IDs.
    owners = {e['eventGroupId']: e for n in (1, 2) for e in
              load(ROOT / f'research/evidence/global/generated/batches/global-evidence-proposal-{n}.json')['events']}
    require(len(batches) == 1 and len(batches[0]['events']) == 6, 'Wrong admission event mapping')
    for e in batches[0]['events']:
        owner = owners[e['eventGroupId']]
        require(e['candidateIds'] == owner['candidateIds'] and e['relatedCandidateIds'] == owner['relatedCandidateIds'],
                'Canonical event ownership changed')
    existing = [load(p) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing, *batches])
    counts = validate_admission(base, dataset, batches, dossier)
    require(counts == {'airports': 7, 'assignments': 6, 'names': 0, 'sources': 18}, 'Admission exceeds exact approved additions')
    return counts


def validate():
    manifest = load(REVIEW / 'review-manifest.json')
    for path, sha in manifest['originalProposalInputs'].items():
        checked(ROOT / path, sha)
    for path, sha in manifest['reviewFiles'].items():
        checked(REVIEW / path, sha)
    frozen_path = ROOT / 'test/curated-0.9.0.json'
    checked(frozen_path, manifest['formalDatasetSha256'])
    frozen, current = load(frozen_path), load(ROOT / 'data/airports.json')
    for collection, key in [('airports', 'airportId'), ('assignments', 'assignmentId'), ('names', 'nameId'), ('sources', 'sourceId')]:
        actual = {r[key]: r for r in current[collection]}
        require(all(actual.get(r[key]) == r for r in frozen[collection]), 'Released 0.9.0 record changed')
    counts = validate_records(frozen, load(REVIEW / 'approval.json'), load(REVIEW / 'dossier.json'),
                             load(REVIEW / 'source-review.json'), [load(p) for p in sorted((REVIEW / 'batches').glob('*.json'))])
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        output = Path(tmp) / 'validated.json'
        subprocess.run(['python3', str(ROOT / 'scripts/evidence/review.py'), 'validate', '--base-dataset', str(BASELINE),
                        '--batches', str(REVIEW / 'batches'), '--dataset', str(frozen_path),
                        '--dossier', str(REVIEW / 'dossier.json'), '--output', str(output)], cwd=ROOT, check=True)
        require(load(output) == frozen, 'Admission replay differs from frozen released data')
    print('Validated user-approved actual 0.9.0 through original admission gate: ' + json.dumps(counts, sort_keys=True))


if __name__ == '__main__':
    validate()
