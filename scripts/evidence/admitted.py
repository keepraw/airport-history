"""Validate the actual 0.8.0 admission, including the existing human-review CLI gate."""
import gzip
import json
import subprocess
import tempfile
from pathlib import Path

from pipeline import ROOT
from common import checked, research_baseline_path
from admissions import validate_admission
from review import validate_batch_series
import direct

REVIEW = ROOT / 'research/admissions/0.8.0'


def load(path):
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def validate_records(dataset, approval, dossier, source_reviews, batches):
    """Authorization is the user's recorded instruction, not a fabricated signature."""
    require(approval['authorizedBy'] == {'login': 'keepraw', 'githubUserId': 49091395}, 'Wrong approving user')
    require(approval['recordedBy'] == 'Codex' and approval['authorizationSource'] and approval['authorizationMeaning'],
            'Missing truthful approval provenance')
    base = load(research_baseline_path())
    expected_airports = set(approval['approvedAirportIds'])
    expected_assignments = {a['assignmentId']: a for a in approval['approvedAssignments']}
    require(len(expected_airports) == 4 and len(expected_assignments) == 3, 'Wrong authorized scope')
    for collection, key, expected in [('airports', 'airportId', expected_airports),
                                      ('assignments', 'assignmentId', set(expected_assignments)),
                                      ('names', 'nameId', set())]:
        old_ids = {r[key] for r in base[collection]}
        require({r[key] for r in dataset[collection]} - old_ids == expected, 'Unapproved admission scope: ' + collection)
    require(len(dossier) == 7 and {d['recordId'] for d in dossier} == expected_airports | set(expected_assignments),
            'Admission needs exactly seven per-record decisions')
    for d in dossier:
        require(d['decision'] == 'accepted' and d['reviewer'] == 'keepraw' and d['reviewedOn'] == approval['approvedOn'],
                'Missing actual user-approved record decision')
        require(d['reviewBasis']['approvalId'] == approval['approvalId'] and d['reviewBasis']['recordedBy'] == 'Codex',
                'Wrong per-record authorization')
    for a in dataset['assignments']:
        if a['assignmentId'] not in expected_assignments:
            continue
        approved = expected_assignments[a['assignmentId']]
        require(all(a[key] == value for key, value in approved.items()), 'Assignment exceeds approved boundaries')
        require(a['verificationStatus'] == 'verified' and a['verifiedOn'] == approval['approvedOn'], 'Missing assignment review date')
        require(next(d for d in dossier if d['recordId'] == a['assignmentId'])['approvedRecord'] == a,
                'Dossier does not describe the actual admitted record')
    for a in dataset['airports']:
        if a['airportId'] in expected_airports:
            require(a['coordinates']['status'] == a['name']['status'] == 'reference', 'Reference attribute upgraded')
            require(a['timezone']['status'] == 'unknown' and a['timezone']['value'] is None and not a['timezone']['sourceIds'],
                    'Unapproved timezone claim')
    old_sources = {s['sourceId'] for s in base['sources']}
    sources = {s['sourceId']: s for s in dataset['sources'] if s['sourceId'] not in old_sources}
    require(len(sources) == 7 and set(sources) == {s['sourceId'] for s in source_reviews}, 'Wrong admitted source set')
    require(len({s['originalPublicationKey'] for s in source_reviews}) == 7, 'Repeated publication counted independently')
    used = {sid for a in dataset['assignments'] if a['assignmentId'] in expected_assignments for sid in a['sourceIds']}
    used |= {sid for a in dataset['airports'] if a['airportId'] in expected_airports
             for key in ('name', 'coordinates', 'timezone') for sid in a[key]['sourceIds']}
    require(used == set(sources), 'Unused or missing formal source')
    for s in source_reviews:
        formal = sources[s['sourceId']]
        require(formal['verificationStatus'] == s['verificationStatus'] == 'verified', 'Unreviewed cited source')
        require(formal['accessedOn'] == s['accessedAt'][:10] <= s['reviewedOn'] == approval['approvedOn'],
                'Source access/review chronology is invalid')
        require(s['contentCheckedBy'] == 'Codex' and s['claimApprovalBy'] == 'keepraw' and s['supportedFacts'] and s['limitations'],
                'Missing scoped source verification')
    existing = [load(p) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing, *batches])
    return validate_admission(base, dataset, batches, dossier)


def validate():
    manifest = load(REVIEW / 'review-manifest.json')
    for name, sha in manifest['originalProposalInputs'].items():
        checked(ROOT / name, sha)
    for name, sha in manifest['reviewFiles'].items():
        checked(REVIEW / name, sha)
    checked(ROOT / 'test/curated-0.8.0.json', manifest['formalDatasetSha256'])
    formal = load(ROOT / 'data/airports.json')
    frozen = load(ROOT / 'test/curated-0.8.0.json')
    for collection, key in [('airports', 'airportId'), ('assignments', 'assignmentId'), ('names', 'nameId'), ('sources', 'sourceId')]:
        current = {r[key]: r for r in formal[collection]}
        require(all(current.get(r[key]) == r for r in frozen[collection]), 'Released 0.8.0 record changed')
    approval, dossier = load(REVIEW / 'approval.json'), load(REVIEW / 'dossier.json')
    sources = load(REVIEW / 'source-review.json')
    batches = [load(p) for p in sorted((REVIEW / 'batches').glob('*.json'))]
    dataset = load(ROOT / 'test/curated-0.8.0.json')
    counts = validate_records(dataset, approval, dossier, sources, batches)
    originals = direct.locked_sources()
    for s in sources:
        locked, text = originals[s['sourceId']]
        require(locked['originalSha256'] == s['originalSha256'] and locked['originalPublicationKey'] == s['originalPublicationKey'],
                'Original source provenance changed')
        checked(ROOT / s['originalArchive'], s['originalArchiveSha256'])
        for observation in [o for d in dossier for o in d['observations'] if o['sourceId'] == s['sourceId']]:
            cite = observation['citation']
            if cite.get('extractionTool') == 'pdftotext -raw':
                raw = gzip.decompress((ROOT / s['originalArchive']).read_bytes())
                text_page = subprocess.run(['pdftotext', '-raw', '-f', str(cite['extractedPage']), '-l', str(cite['extractedPage']), '-', '-'],
                                           input=raw, stdout=subprocess.PIPE, check=True).stdout.decode()
            else:
                text_page = text.split('\f')[cite['extractedPage'] - 1]
            require(direct.normalized(cite['anchor']) in direct.normalized(text_page), 'Admitted citation does not match its original page')
    # Run the requested real admission command against the actual formal data.
    # The replay base is restricted to the hash-pinned reviewed snapshot.
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        output = Path(tmp) / 'validated.json'
        subprocess.run(['python3', str(ROOT / 'scripts/evidence/review.py'), 'validate',
                        '--base-dataset', str(research_baseline_path()), '--batches', str(REVIEW / 'batches'),
                        '--dataset', str(ROOT / 'test/curated-0.8.0.json'), '--dossier', str(REVIEW / 'dossier.json'),
                        '--output', str(output)], cwd=ROOT, check=True)
        require(load(output) == dataset, 'Validated output differs from formal data')
    print('Validated user-approved formal 0.8.0: ' + json.dumps(counts, sort_keys=True))


if __name__ == '__main__':
    validate()
