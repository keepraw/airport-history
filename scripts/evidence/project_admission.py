"""Replay project-authorized source/claim admissions; no personal claim review.

The original AAI validate_admission helper imports its AAI-specific policy gate
and all its files are covered by the existing owner grant's fingerprint. Keep
those files and that execution path unchanged. Reuse the same batch validator,
append-only record checks, pinned inputs and production schema/semantic gate here.
Only physical identity is activated; code and name intervals fail closed.
"""
import argparse
import csv
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/reference'))
sys.path.insert(0, str(ROOT / 'scripts/discovery'))
from common import checked, digest, distance, write_json
from review import validate_batch_series

POLICY = ROOT / 'research/admission/source-claims-v1/policy.json'
IDENTIFIERS = {'airports': 'airportId', 'assignments': 'assignmentId',
               'names': 'nameId', 'sources': 'sourceId'}


def load(path):
    return json.loads(Path(path).read_text())


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def policy():
    p = load(POLICY)
    require(p['formatVersion'] == 1 and p['policyKey'] == 'official-source-claims@1.0.0'
            and p['countries'] == ['CN'] and p['activatedClaims'] == ['physicalIdentity'],
            'Unsupported project source/claim policy')
    require(p['authorization']['kind'] == 'explicit-user-task' and
            p['authorization']['reviewer'] is None, 'Missing truthful task authorization')
    for path, expected in p['researchInputs'].items():
        checked(ROOT / path, expected)
    checked(ROOT / p['baseline']['path'], p['baseline']['sha256'])
    return p


def receipt(data, batches, dossier, source_reviews):
    p = policy()
    files = ['scripts/evidence/project_admission.py', 'schema/dataset.schema.json',
             'src/validate.ts', 'src/types.ts', 'scripts/discovery/review.py']
    return {'formatVersion': 1, 'reviewMode': 'policy', 'reviewer': None,
            'policyKey': p['policyKey'], 'policySha256': sha(p),
            'authorization': p['authorization'], 'baseline': p['baseline'],
            'executorFiles': {path: digest(ROOT / path) for path in files},
            'datasetSha256': sha(data), 'batchesSha256': sha(batches),
            'dossierSha256': sha(dossier), 'sourceReviewsSha256': sha(source_reviews),
            'meaning': 'Machine source/claim rule execution under the explicit user task. '
                       'No human per-record acceptance, inherited AAI/KR grant, or raw-byte reacquisition is asserted.'}


def source_evidence(review, formal, p):
    family = p['families'].get(review['policyFamily'])
    require(family and family['active'], 'Unsupported or inactive source family')
    require(review['documentClass'] in family['documentClasses'] and
            review['rightsBasis'] == family['rightsBasis'], 'Source class or rights outside policy')
    require(review['supportedFacts'] and review['limitations'], 'Missing source claim limits')
    lock_path = review['lockPath']
    require(lock_path in p['researchInputs'], 'Unpinned source lock')
    lock = load(ROOT / lock_path)
    if review['policyFamily'] == 'PUBLIC-DOMAIN-REFERENCE':
        require(lock_path == family['lockPath'] and lock['sourceId'] == review['lockSourceId'] == 'ourairports'
                and lock['license'] == 'Public-Domain' and formal['sourceType'] == 'secondary',
                'Unlicensed or substituted reference directory')
        raw = gzip.decompress((ROOT / family['inputPath']).read_bytes())
        require(hashlib.sha256(raw).hexdigest() == lock['sha256'], 'Changed reference bytes')
        require(formal['url'] == lock['downloadUrl'] and formal['license']['id'] == 'LicenseRef-Public-Domain',
                'Detached formal reference source')
        return {'referenceRows': {row['id']: row for row in csv.DictReader(io.StringIO(raw.decode()))}}
    matches = [s for s in lock['sources'] if s['sourceId'] == review['lockSourceId']]
    require(len(matches) == 1, 'Missing or duplicated locked publication')
    s = matches[0]
    host = urlparse(s['url']).hostname or ''
    require((host in family.get('hosts', []) or host.endswith(family.get('hostsSuffix', '\0')))
            and urlparse(s['url']).scheme == 'https', 'Source lacks official issuing custody')
    require(s.get('sourceType') == 'primary' and s.get('officialCustody') is True
            and s.get('originalBytesReadHere') is True and s.get('httpStatus') == 200,
            'Missing verified original publication')
    require(formal['url'] == s['url'] and formal['sourceType'] == 'primary' and
            formal['verificationStatus'] == 'verified' and formal['accessedOn'] == s['acquiredAt'][:10],
            'Detached formal publication metadata')
    require(review['rightsBasisUrl'].startswith('https://www.gov.cn/') and
            formal['license']['id'] == 'LicenseRef-PRC-Official-Administrative-Documents', 'Missing official document rights basis')
    require(review['originalSha256'] == s['originalSha256'], 'Detached source review hash')
    observed = datetime.date.fromisoformat(review['observedOn'])
    known = {d.get('date') for d in s.get('knownDates', [])} | {s.get('documentDate'), s.get('publicationDate')}
    require(str(observed) in known, 'Observation is not a documented date')
    citations = {c['citationId']: c for c in s['citations']}
    ids = review['citationIds']
    require(ids and len(set(ids)) == len(ids) and set(ids) <= citations.keys(), 'Missing original citations')
    for cid in ids:
        c = citations[cid]
        require(hashlib.sha256(c['quote'].encode()).hexdigest() == c['quoteSha256'] and
                c['characterEnd'] - c['characterStart'] == len(c['quote']) and len(c['quote']) <= 600,
                'Altered or excessive citation')
    proof_path = str(Path(lock_path).parent / 'original-verification.json')
    require(proof_path in p['researchInputs'], 'Unpinned original-verification receipt')
    proofs = [x for x in load(ROOT / proof_path)['sources'] if x['sourceId'] == s['sourceId']]
    require(len(proofs) == 1 and proofs[0]['originalBytesReadHere'] is True and
            all(proofs[0][k] == s[k] for k in ('originalSha256', 'extractedTextSha256', 'normalizedTextSha256'))
            and proofs[0]['citationsBound'] >= len(ids), 'Original/hash/citation receipt disagreement')
    return {'source': s, 'citations': {cid: citations[cid] for cid in ids}}


def validate(base, data, batches, dossier, context, source_reviews):
    p = policy()
    require(base == load(ROOT / p['baseline']['path']), 'Admission requires its frozen published baseline')
    require(context == receipt(data, batches, dossier, source_reviews), 'Altered project policy receipt')
    require(data['schemaVersion'] == base['schemaVersion'] and data['dataVersion'] != base['dataVersion'],
            'Wrong schema or unchanged formal dataVersion')
    additions = {}
    for key, identifier in IDENTIFIERS.items():
        old = {r[identifier]: r for r in base[key]}
        new = {r[identifier]: r for r in data[key]}
        require(len(new) == len(data[key]) and all(new.get(k) == v for k, v in old.items()),
                'Bulk admission changes or duplicates existing permanent records')
        additions[key] = {k: v for k, v in new.items() if k not in old}
    require(additions['airports'] and not additions['assignments'] and not additions['names'],
            'Only physical identity is activated; code/name intervals require separate evidence rules')
    validate_batch_series(batches)
    existing_batches = [load(path) for path in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing_batches, *batches])
    require(not any(b.get('preparationOnly') for b in batches), 'Preparation packets are not admissions')
    ready = [e for b in batches for e in b['events'] if e['status'] == 'ready_to_admit']
    airport_ids = [aid for e in ready for aid in e['admittedAirportIds']]
    require(len(airport_ids) == len(set(airport_ids)) and set(airport_ids) == set(additions['airports'])
            and not any(e['admittedAssignmentIds'] or e['admittedNameIds'] for e in ready), 'Admission/event mapping disagrees')
    reviews = {r['sourceId']: r for r in source_reviews}
    require(len(reviews) == len(source_reviews) and set(reviews) == set(additions['sources']),
            'Missing, duplicate or unused source reviews')
    evidence = {sid: source_evidence(r, additions['sources'][sid], p) for sid, r in reviews.items()}
    entries = {d['recordId']: d for d in dossier}
    require(len(entries) == len(dossier) and set(entries) == set(additions['airports']), 'Wrong claim dossier population')
    used = set()
    for aid, record in additions['airports'].items():
        d = entries[aid]
        require(d.get('decision') == 'policy_accepted' and d.get('reviewMode') == 'policy'
                and d.get('reviewer') is None and d.get('policyKey') == p['policyKey']
                and d.get('country') in p['countries'] and d['approvedRecord'] == record,
                'Missing machine claim decision or expanded country scope')
        for supplemental in d.get('supplementalEvidence', []):
            require(supplemental['path'] in p['researchInputs'], 'Unpinned execution corroboration')
            checked(ROOT / supplemental['path'], supplemental['sha256'])
            require(load(ROOT / supplemental['path'])['originalSha256'] == supplemental['originalSha256'], 'Detached corroboration original')
        require(d.get('supplementalEvidence'), 'Missing actual airport execution corroboration')
        identity = d['physicalIdentity']
        require(identity['candidateConflictReviewed'] is True and identity['matchingExistingAirportId'] is None,
                'Competing physical identity must be resolved or existing airportId reused')
        event = next(e for e in ready if aid in e['admittedAirportIds'])
        ids = set(identity['sourceIds'])
        require(ids and ids <= evidence.keys() and ids <= set(event['claims']['physicalIdentity']['sourceIds'])
                and ids <= set(record['coordinates']['sourceIds']), 'Physical claim/source linkage disagrees')
        quotes = []
        for observation in d['observations']:
            sid = observation['sourceId']
            require(sid in ids and 'source' in evidence[sid] and observation['independentOriginal'] is True
                    and observation['observedOn'] == reviews[sid]['observedOn']
                    and datetime.date.fromisoformat(observation['observedOn']) <= datetime.date.fromisoformat(event['reviewedOn'])
                    and observation['claimScope'] and observation['basis'], 'Missing dated original primary observation')
            cids = observation['citationIds']
            require(cids and set(cids) <= evidence[sid]['citations'].keys(), 'Detached dossier citation')
            quotes += [evidence[sid]['citations'][cid]['quote'] for cid in cids]
        require(quotes and identity['officialName'] and identity['locationDescription'] in quotes,
                'Identity location lacks a bounded primary citation')
        require(record['coordinates']['status'] == record['name']['status'] == 'reference'
                and record['timezone']['status'] == 'unknown' and record['timezone']['value'] is None
                and not record['timezone']['sourceIds'], 'Reference attributes upgraded beyond evidence scope')
        rid = record['externalIds'].get('ourAirports')
        refs = [(sid, e['referenceRows'].get(rid)) for sid, e in evidence.items() if 'referenceRows' in e]
        require(len(refs) == 1 and refs[0][1] is not None, 'Missing pinned coordinate reference row')
        sid, row = refs[0]
        require(row['iso_country'] == d['country'] and record['name']['value'] == row['name'] and
                record['coordinates']['value'] == {'latitude': float(row['latitude_deg']), 'longitude': float(row['longitude_deg'])}
                and sid in record['coordinates']['sourceIds'] and sid in record['name']['sourceIds'],
                'Reference site or coordinate substitution')
        for rival in data['airports']:
            if rival['airportId'] == aid:
                continue
            require(rival['externalIds'].get('ourAirports') != rid and
                    (distance(record['coordinates']['value'], rival['coordinates']['value']) or 0) * 1000 >= p['identity']['duplicateRadiusMetres'],
                    'Duplicate or competing existing physical identity')
        used |= {s for attr in ('coordinates', 'name', 'timezone') for s in record[attr]['sourceIds'] if s in additions['sources']}
    require(used == set(additions['sources']), 'Unused formal source')
    return {key: len(value) for key, value in additions.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--write-receipt', action='store_true')
    args = parser.parse_args()
    data = load(ROOT / 'data/airports.json')
    bundle = args.bundle or ROOT / 'research/admissions' / data['dataVersion']
    require(load(bundle / 'proposed-data.json') == data, 'Formal bytes differ from admission proposal')
    batches = [load(path) for path in sorted((bundle / 'batches').glob('*.json'))]
    dossier, sources = load(bundle / 'dossier.json'), load(bundle / 'source-reviews.json')
    context = receipt(data, batches, dossier, sources)
    if args.write_receipt:
        write_json(bundle / 'policy-receipt.json', context)
    counts = validate(load(ROOT / policy()['baseline']['path']), data, batches, dossier,
                      load(bundle / 'policy-receipt.json'), sources)
    subprocess.run(['node', '--input-type=module', '-e',
        'import {readFileSync} from "node:fs"; import {assertDataset} from "./src/validate.ts"; '
        'assertDataset(JSON.parse(readFileSync("data/airports.json","utf8")));'], cwd=ROOT, check=True)
    print(json.dumps({'validatedProjectAdmissions': counts, 'reviewer': None}))


if __name__ == '__main__':
    main()
