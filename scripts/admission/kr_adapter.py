"""Independent, versioned Korean proposal CLI. Never edits formal data or Indian grants."""
import argparse
import base64
from copy import deepcopy
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

from kr_evidence import ROOT, PACKET, evaluate, load, require

DIRECTORY = ROOT / 'research/admission/kr-molit-v1'
KEY = 'kr-molit-bounded-icao@1.0.0'
OWNER = {'login': 'keepraw', 'id': 49091395}
AUTHORITY_KIND = 'github-owner'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b'\n')


def fingerprint():
    # Include transitive local imports and every executable selector, not only the adapter.
    paths = sorted({p for base in ('scripts', 'src', 'schema') for p in (ROOT / base).rglob('*')
                    if p.is_file() and p.suffix in ('.py', '.ts', '.json')})
    paths += [ROOT / 'pnpm-lock.yaml']
    manifest = {'formatVersion': 1, 'files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in paths}, 'canonicalJsonInputs': {'package.json': sha(load(ROOT / 'package.json'))}}
    return {**manifest, 'executorSha256': sha(manifest)}


def policy(key=KEY):
    # An exact registry entry selects code. Policy-like strings never select authority.
    require(key == KEY, 'Unknown policy/version: default deny')
    p = load(DIRECTORY / 'policy.json')
    require(p['policyKey'] == key and p['scope']['namespace'] == 'ICAO' and
            p['scope']['country'] == 'KR' and p['scope']['issuerFamily'] == 'KR-MOLIT-AIP' and
            not any(p['scope'][k] for k in ('newPhysicalIdentities', 'newIataAssignments', 'publishedCorrections')),
            'Unsupported policy semantics')
    return p


def bindings(p):
    return {'policyKey': p['policyKey'], 'policySha256': sha(p), 'scopeSha256': sha(p['scope']),
            'executorSha256': fingerprint()['executorSha256']}


def checked_bindings(p):
    actual = bindings(p)
    require(load(DIRECTORY / 'bindings.json') == {**actual, 'manifest': fingerprint()},
            'Policy/Scope/Executor changed; new review and authorization required')
    return actual


def github(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], cwd=ROOT, text=True))


def read_owner_comment(url, expected):
    match = re.fullmatch(r'https://github.com/keepraw/airport-history/(?:issues|pull)/(\d+)#issuecomment-(\d+)', url or '')
    require(match, 'Exact repository issue-comment URL required')
    repo = github('repos/keepraw/airport-history')
    require({k: repo['owner'][k] for k in OWNER} == OWNER and repo['owner']['type'] == 'User',
            'Repository owner identity changed')
    c = github('repos/keepraw/airport-history/issues/comments/' + match[2])
    require(c['html_url'] == url and c['issue_url'] ==
            'https://api.github.com/repos/keepraw/airport-history/issues/' + match[1] and
            {k: c['user'][k] for k in OWNER} == OWNER and c['user']['type'] == 'User' and
            c['body'] == expected, 'Comment actor, repository, content or scope does not match real owner')
    for k in ('created_at', 'updated_at'):
        time = dt.datetime.fromisoformat(c[k].replace('Z', '+00:00'))
        require(time <= dt.datetime.now(dt.timezone.utc), 'Future comment timestamp')
    require(c['created_at'] <= c['updated_at'], 'Invalid approval timestamps')
    return {k: c[k] for k in ('html_url', 'body', 'created_at', 'updated_at')} | {'principal': OWNER, 'kind': AUTHORITY_KIND}


def identity_batch():
    b = load(PACKET / 'identity-batch.json')
    require(b['batchSha256'] == sha(b['payload']) and b['authorization'] is None and
            len(b['payload']['records']) == 2 and
            all(r['proposedPermanentAirportId'] is None for r in b['payload']['records']), 'Invalid identity batch')
    return b


def identity_text():
    identity_batch()
    return load(PACKET / 'authorization-proposal.json')['futureIdentityOnlyOwnerText']


def identity_baseline(batch, data):
    reviewed = ROOT / ('test/curated-' + batch['payload']['dataVersion'] + '.json')
    require(data == load(reviewed),
            'Identity batch baseline changed; renew physical-site competition review and batch approval')


def require_published(data, identities=None):
    """A working-tree identity is not proof of admission to the owner's main branch."""
    commit = github('repos/keepraw/airport-history/branches/main')['commit']['sha']
    require(re.fullmatch(r'[0-9a-f]{40}', commit), 'Unknown published main commit')
    def at_main(path):
        obj = github('repos/keepraw/airport-history/contents/' + path + '?ref=' + commit)
        require(obj['encoding'] == 'base64' and obj['type'] == 'file', 'Missing published formal identity artifact')
        return json.loads(base64.b64decode(obj['content'], validate=False))
    require(at_main('data/airports.json') == data, 'Current dataset is not the exact published main dataset')
    if identities is not None:
        require(at_main('research/admission/kr-molit-v1/identities.json') == identities,
                'Identity registry is not formally published on main')
    return commit


def physical_identities(p, data, *, fresh=True):
    registry = load(DIRECTORY / 'identities.json')
    require(registry['formatVersion'] == 1 and len(registry['identities']) == len(p['scope']['sites']),
            'Approved formally existing permanent identities missing')
    batch = identity_batch()
    require(batch['batchSha256'] == p['identityBatchSha256'], 'Identity batch outside exact policy scope')
    records = {r['candidateKey']: r for r in batch['payload']['records']}
    result = []
    for site in p['scope']['sites']:
        entries = [r for r in registry['identities'] if r['candidateKey'] == site['candidateKey']]
        require(len(entries) == 1, 'Ambiguous/wrong physical identity')
        entry = entries[0]
        require(sha(entry['airportId']) not in p['rejectedResearchIdentitySha256'],
                'Research simulation identity can never become a permanent identity')
        require(entry['batchSha256'] == batch['batchSha256'] and re.fullmatch(
            r'apt_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', entry['airportId']),
            'Unapproved/non-permanent airport ID')
        record = next((r for r in data['airports'] if r['airportId'] == entry['airportId']), None)
        expected = records[site['candidateKey']]
        require(record is not None and sha(record) == entry['recordSha256'] and
                record['coordinates']['value'] == expected['arpDecimal'] and
                record['coordinates']['status'] == 'verified' and record['name']['value'] == expected['name'] and
                expected['arpDms'] == site['arpDms'], 'Identity not formal, different site or conflicting ARP')
        require(entry['approval']['kind'] == AUTHORITY_KIND and entry['approval']['principal'] == OWNER and
                entry['approval']['body'] == identity_text(), 'Invalid physical identity approval')
        if fresh:
            require(read_owner_comment(entry['approval']['html_url'], identity_text()) == entry['approval'],
                    'Physical identity approval edited/revoked')
        result.append(entry)
    require(len({r['airportId'] for r in result}) == len(result), 'Distinct physical sites merged')
    require_published(data, registry)
    return result


def policy_text(p, identities):
    b = checked_bindings(p)
    return (f"Authorize Korean policy {p['policyKey']} policy-sha256:{b['policySha256']} "
            f"scope-sha256:{b['scopeSha256']} executor-sha256:{b['executorSha256']} "
            f"identities-sha256:{sha(identities)}. "
            'Only the exact existing approved physical identities, ICAO codes and local-date window in this scope. '
            'Require original-byte and citation replay for every batch. No IATA, new identities, published corrections, '
            'expanded history, or inherited authorization. Prepare reviewable proposals only. Human merge required.')


def authorization(p, identities):
    registry = load(DIRECTORY / 'authorizations.json')
    require(registry['formatVersion'] == 1, 'Unsupported Korean authorization registry')
    grants = [g for g in registry['authorizations'] if g.get('policyKey') == p['policyKey']]
    require(len(grants) == 1, 'Missing or ambiguous real Owner policy authorization')
    grant = grants[0]
    require(set(grant) == {'policyKey', 'bindings', 'identitiesSha256', 'approval'},
            'Unknown authorization fields/state; default deny')
    require(grant['bindings'] == checked_bindings(p) and grant['identitiesSha256'] == sha(identities),
            'Exact policy/scope/executor/identity authorization mismatch')
    actual = read_owner_comment(grant['approval']['html_url'], policy_text(p, identities))
    require(actual == grant['approval'], 'Policy approval edited/revoked/test authority')
    return grant


def new_output(path):
    path = path.resolve()
    require(path.is_relative_to((ROOT / 'work').resolve()) and not path.exists(),
            'Use a new ignored work/ directory; formal writes are forbidden')
    return path


def sources_for(ids, reviewed_on):
    lock = {s['sourceId']: s for s in load(PACKET / 'source-lock.json')['sources']}
    return [{'sourceId': sid, 'title': lock[sid].get('title', sid), 'url': lock[sid]['url'],
             'accessedOn': reviewed_on, 'sourceType': 'primary', 'verificationStatus': 'verified',
             'license': {'id': 'LicenseRef-Quotation-Only', 'url': lock[sid]['url'],
                         'note': 'Minimal attributed citations only; full original redistribution not established.'},
             'note': 'Original-byte verification required; no first/last allocation date inferred.'} for sid in sorted(ids)]


def resolver_gate(base, candidate, evidence, output):
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        paths = [Path(tmp) / s for s in ('base.json', 'candidate.json', 'evidence.json')]
        for path, value in zip(paths, (base, candidate, evidence)):
            write(path, value)
        subprocess.run(['node', 'scripts/admission/kr_resolver.ts', *map(str, paths), str(output)], cwd=ROOT, check=True)


def prepare(p, output, version):
    output = new_output(output)
    checked_bindings(p)
    base = load(ROOT / 'data/airports.json')
    identities = physical_identities(p, base)
    grant = authorization(p, identities)  # Fail before evidence work and before any output directory.
    evidence = evaluate(p, originals=True)
    require(re.fullmatch(r'\d+\.\d+\.\d+', version or '') and version != base['dataVersion'],
            'A new reviewed data version is required')
    candidate = deepcopy(base)
    candidate['dataVersion'] = version
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    source_ids = {sid for c in evidence['candidates'] for sid in c['sourceIds']}
    existing = {s['sourceId']: s for s in base['sources']}
    for source in sources_for(source_ids, day):
        if source['sourceId'] in existing:
            prior = existing[source['sourceId']]
            require(prior['accessedOn'] <= day and prior == {**source, 'accessedOn': prior['accessedOn']},
                    'Existing source collision requires manual review')
        else:
            candidate['sources'].append(source)
    for c, identity in zip(evidence['candidates'], identities):
        require(not any(a['scheme'] == 'ICAO' and a['code'] == c['code'] for a in base['assignments']),
                'Existing assignment/correction requires manual review')
        candidate['assignments'].append({'assignmentId': 'kr-molit-' + sha([p['policyKey'], c])[:24],
            'airportId': identity['airportId'], 'scheme': 'ICAO', 'code': c['code'], 'verificationStatus': 'verified',
            'verifiedOn': day, 'validFrom': {'earliest': None, 'latest': c['window']['from'], 'precision': 'unknown'},
            'validTo': {'earliest': c['window']['toExclusive'], 'latest': None, 'precision': 'unknown'},
            'evidenceType': 'continuity_inference', 'sourceIds': c['sourceIds'],
            'note': 'Bounded controlled Korean AIP/NOTAM continuity; outer historical boundaries remain unknown.'})
    # All mutations remain in memory until the actual schema and resolver accept them.
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        report = Path(tmp) / 'resolver.json'
        resolver_gate(base, candidate, evidence, report)
        measurement = load(report)
    require(candidate['airports'] == base['airports'] and candidate['names'] == base['names'], 'Identity/name expansion')
    write(output / 'proposed-data.json', candidate)
    write(output / 'receipt.json', {'bindings': checked_bindings(p), 'authorizationSha256': sha(grant),
        'identitiesSha256': sha(identities), 'baselineSha256': sha(base), 'candidateSha256': sha(candidate),
        'evidence': evidence, 'resolver': measurement, 'humanMergeRequired': True})
    return measurement


def prepare_identities(output, url, version):
    output = new_output(output)
    approval = read_owner_comment(url, identity_text())
    batch = identity_batch()
    p = policy()
    evaluate(p, originals=True)
    base = load(ROOT / 'data/airports.json')
    identity_baseline(batch, base)
    require_published(base)
    require(re.fullmatch(r'\d+\.\d+\.\d+', version or '') and version != base['dataVersion'], 'New identity data version required')
    candidate = deepcopy(base)
    candidate['dataVersion'] = version
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    all_ids = {sid for r in batch['payload']['records'] for sid in r['sourceHashes']}
    additions = sources_for(all_ids, day)
    require(not all_ids & {s['sourceId'] for s in base['sources']}, 'Identity source collision')
    candidate['sources'].extend(additions)
    entries, dossiers, events = [], [], []
    sys.path.insert(0, str(ROOT / 'scripts/reference'))
    from admissions import validate_admission, CLAIMS
    for r in batch['payload']['records']:
        require(not any(a['coordinates']['value'] == r['arpDecimal'] for a in base['airports']), 'Possible existing physical site')
        aid = 'apt_' + str(uuid.uuid4())  # Only after live owner approval, never a simulation ID.
        require(sha(aid) not in p['rejectedResearchIdentitySha256'], 'Research simulation UUID collision')
        sids = sorted(r['sourceHashes'])
        record = {'airportId': aid, 'name': {'value': r['name'], 'status': 'reference', 'sourceIds': sids,
                   'note': 'Physical-site display name; no legal-name timeline.'},
                  'coordinates': {'value': r['arpDecimal'], 'status': 'verified', 'sourceIds': sids,
                                  'note': 'Exact MOLIT AIP ARP. NOAA is vicinity corroboration only.'},
                  'timezone': {'value': None, 'status': 'unknown', 'sourceIds': [], 'note': 'No timezone fact admitted.'},
                  'externalIds': {}}
        candidate['airports'].append(record)
        entries.append({'candidateKey': r['candidateKey'], 'airportId': aid, 'recordSha256': sha(record),
                        'batchSha256': batch['batchSha256'], 'approval': approval})
        dossiers.append({'recordId': aid, 'decision': 'accepted', 'reviewer': 'keepraw',
            'reviewMode': 'human', 'approval': approval, 'observations': [{'sourceId': sids[0],
            'observedOn': day, 'sourceFamily': r['operator'], 'independentOriginal': True,
            'claimScope': 'Named physical site and exact AIP ARP only.',
            'basis': 'Exact owner identity batch approval; original bytes and independent operator location replayed.'}]})
        events.append({'eventGroupId': r['candidateKey'], 'candidateIds': [r['candidateKey']], 'relatedCandidateIds': [],
            'reviewedOn': day, 'status': 'ready_to_admit', 'sourceIds': sids,
            'claims': {k: {'conclusion': 'Approved physical site only; code/name dates excluded.',
                         'evidenceType': 'indirect', 'sourceIds': sids} for k in CLAIMS},
            'continuityInference': {'evidenceType': 'continuity_inference', 'usedForAdmission': False},
            'nextAction': 'Separate identity admission PR, human merge required.',
            'admittedAirportIds': [aid], 'admittedAssignmentIds': [], 'admittedNameIds': []})
    b = {'batchId': batch['payload']['batchId'], 'reviewedOn': day,
         'selection': {'maximumEvents': 2, 'eventCount': 2}, 'statusCounts': {'ready_to_admit': 2},
         'sources': [{**s, 'supportedFacts': ['Named physical site and AIP ARP'],
                      'limitations': ['No code or name validity dates.'], 'accessResult': 'Original-byte replay.'} for s in additions],
         'events': events}
    validate_admission(base, candidate, [b], dossiers)  # Actual existing HUMAN identity gate, no policy_context.
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        resolver_gate(base, candidate, {'candidates': [], 'daysPerAirport': 0}, Path(tmp) / 'resolver.json')
    write(output / 'proposed-data.json', candidate)
    write(output / 'identities.json', {'formatVersion': 1, 'identities': entries})
    write(output / 'dossier.json', dossiers)
    write(output / 'batches' / (b['batchId'] + '.json'), b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'identity-text', 'prepare-identities', 'policy-text', 'record-policy', 'admit'])
    parser.add_argument('--policy', default=KEY)
    parser.add_argument('--comment-url')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--data-version')
    args = parser.parse_args()
    p = policy(args.policy)
    if args.command == 'inspect':
        print(json.dumps(checked_bindings(p), sort_keys=True))
    elif args.command == 'identity-text':
        print(identity_text())
    elif args.command == 'prepare-identities':
        require(args.output is not None, 'Output required')
        prepare_identities(args.output, args.comment_url, args.data_version)
    elif args.command in ('policy-text', 'record-policy'):
        identities = physical_identities(p, load(ROOT / 'data/airports.json'))
        text = policy_text(p, identities)
        if args.command == 'policy-text':
            print(text)
        else:
            require(args.output is not None, 'Output required')
            out = new_output(args.output)
            approval = read_owner_comment(args.comment_url, text)
            write(out / 'authorizations.json', {'formatVersion': 1, 'authorizations': [
                {'policyKey': KEY, 'bindings': checked_bindings(p), 'identitiesSha256': sha(identities), 'approval': approval}]})
    else:
        require(args.output is not None, 'Output required')
        print(json.dumps(prepare(p, args.output, args.data_version), sort_keys=True))


if __name__ == '__main__':
    main()
