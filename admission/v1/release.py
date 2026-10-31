"""Release bundle v2: independent rule replay around immutable legacy releases."""
import argparse
from copy import deepcopy
import datetime as dt
from pathlib import Path
import re
import subprocess
import tempfile
import base64

from runtime import ROOT, PUBLIC, PRIVATE, authorize, checked_bindings, legacy, load, policy, require, sha, version, private_path, write
from evidence import Store
from identity import allocate, classify, queue, AUTO
from batch import inventory, discover
import korean


def published_checkout(commit):
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == commit,
            'Production preparation requires the exact published main checkout')
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, text=True).strip(),
            'Production inputs are dirty or unreviewed; use a clean published main checkout')


def pending_from_github():
    """Read all owner-repository pending batch ledgers before allocating UUIDs."""
    result = []
    page = 1
    while True:
        prs = legacy.github(f'repos/keepraw/airport-history/pulls?state=open&per_page=100&page={page}')
        for pr in prs:
            head = pr['head']
            if (not head['ref'].startswith('data/rule-admission-') or
                    (head.get('repo') or {}).get('full_name') != 'keepraw/airport-history'):
                continue
            obj = legacy.github('repos/keepraw/airport-history/contents/research/admission/rule-v1/identities.json?ref=' + head['sha'])
            require(obj['encoding'] == 'base64' and obj['type'] == 'file', 'Pending batch identity ledger unavailable')
            registry = __import__('json').loads(base64.b64decode(obj['content']))
            require(registry['formatVersion'] == 1, 'Unknown pending identity ledger')
            result.extend(registry['identities'])
        if len(prs) < 100:
            break
        page += 1
    return result


def source_records(evidence, source_ids, day):
    result = []
    mapping = {}
    for entry in evidence['sources']:
        sid = entry['sourceId']
        if sid not in source_ids:
            continue
        key = entry.get('originalSha256') or sha(entry['components'])
        stable = sid + '-ev-' + key[:12]
        mapping[sid] = stable
        result.append({'sourceId': stable, 'title': sid, 'url': entry['url'], 'accessedOn': day,
            'sourceType': 'primary', 'verificationStatus': 'verified',
            'license': {'id': 'LicenseRef-Quotation-Only', 'url': entry['url'],
                        'note': 'Metadata and minimal attributed citations only. Originals remain in private content-addressed storage.'},
            'note': 'Evidence version ' + sha(evidence) + '; ' + ('original sha256 ' + key if 'originalSha256' in entry else 'derived set of separately hashed official originals ' + key)})
    require(set(mapping) == set(source_ids), 'Source provenance missing from evidence version')
    return result, mapping


def materialize(base, accepted, evidence, next_version, day, assignments=()):
    candidate = deepcopy(base)
    candidate['dataVersion'] = next_version
    ids = {s for a in accepted for s in a['identity']['sourceIds']}
    ids.update(s for assignment in assignments for s in assignment['sourceIds'])
    sources, mapping = source_records(evidence, ids, day)
    old_sources = {s['sourceId']: s for s in base['sources']}
    for source in sources:
        if source['sourceId'] in old_sources:
            previous = old_sources[source['sourceId']]
            require({**source, 'accessedOn': previous['accessedOn']} == previous, 'Published source collision')
        else:
            candidate['sources'].append(source)
    old_airports = {a['airportId'] for a in base['airports']}
    for record in accepted:
        identity, item = record['identity'], record['candidate']
        if identity['airportId'] in old_airports:
            continue
        source_ids = sorted(mapping[s] for s in identity['sourceIds'])
        candidate['airports'].append({'airportId': identity['airportId'],
            'name': {'value': item['name'], 'status': 'reference', 'sourceIds': source_ids,
                     'note': 'Display name only; no historical legal-name validity admitted.'},
            'coordinates': {'value': identity['coordinates'], 'status': 'verified', 'sourceIds': source_ids,
                            'note': 'Stable official AIP ARP; independent operator site/address support.'},
            'timezone': {'value': None, 'status': 'unknown', 'sourceIds': [], 'note': 'No timezone claim.'}, 'externalIds': {}})
        old_airports.add(identity['airportId'])
    for assignment in assignments:
        candidate['assignments'].append({**assignment, 'sourceIds': sorted(mapping[s] for s in assignment['sourceIds'])})
    return candidate


def gate(base, candidate, code_evidence):
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        path = Path(tmp) / 'resolver.json'
        legacy.resolver_gate(base, candidate, code_evidence, path)
        return load(path)


def already_covered(base, accepted, code_evidence):
    """An already merged batch is a no-op, not a new identity/data proposal."""
    formal_ids = {a['airportId'] for a in base['airports']}
    by_code = {a['candidate']['observedCode']: a for a in accepted}
    if not accepted or any(a['identity']['airportId'] not in formal_ids for a in accepted):
        return False
    if set(by_code) != {c['code'] for c in code_evidence['candidates']}:
        return False
    for row in code_evidence['candidates']:
        matches = [a for a in base['assignments'] if a['scheme'] == 'ICAO' and a['code'] == row['code']]
        if not (len(matches) == 1 and matches[0]['airportId'] == by_code[row['code']]['identity']['airportId'] and
                matches[0]['verificationStatus'] == 'verified' and
                matches[0]['validFrom']['latest'] == row['window']['from'] and
                matches[0]['validTo']['earliest'] == row['window']['toExclusive']):
            return False
    return True


def _prepare(evidence, store, grants, next_version, output, *, candidates=None):
    output = private_path(output, new=True)
    ip, cp = policy('identity'), policy('kr-code')
    # Fail before evaluating originals or minting a UUID if either grant is absent.
    identity_grant, code_grant = authorize(ip, grants), authorize(cp, grants)
    base = load(ROOT / 'data/airports.json')
    version(next_version, base['dataVersion'])
    baseline_commit = legacy.require_published(base)
    published_checkout(baseline_commit)
    registry = load(PUBLIC / 'identities.json')
    pending = PRIVATE / 'pending-identities.json'
    pending_entries = pending_from_github() + (load(pending)['identities'] if pending.exists() else [])
    if pending_entries:
        for entry in pending_entries:
            require(entry['bindings'] == checked_bindings(ip) and entry['authorizationSha256'] == sha(identity_grant), 'Pending identity bound to a different authority')
            existing = next((r for r in registry['identities'] if r['siteKey'] == entry['siteKey']), None)
            if existing is not None:
                require(existing['airportId'] == entry['airportId'], 'Competing pending UUIDs for one physical site')
            else:
                registry['identities'].append(entry)
    # Include an already prepared batch's registry by publishing it in the
    # review branch, then rebase/merge under the main lease. Never trust a daily
    # process-local counter as a permanent identity registry.
    competition = inventory(base, registry)
    candidates = discover(competition) if candidates is None else candidates
    code_evidence = korean.evaluate(evidence, store)
    admitted = allocate(candidates, ip, grants, evidence, store, competition, registry)
    pending_exceptions = PRIVATE / 'exceptions.json'
    from identity import queue
    write(pending_exceptions, queue(admitted['decisions'], load(pending_exceptions) if pending_exceptions.exists() else []))
    accepted = admitted['accepted']
    require(accepted, 'No AUTO_ELIGIBLE physical identities; inspect the exception queue')
    if already_covered(base, accepted, code_evidence):
        return {'formatVersion': 2, 'status': 'NO_CHANGES', 'originalBytesReadHere': code_evidence['originalBytesReadHere'],
                'formalRecordsWritten': 0, 'newPermanentIds': 0, 'newPullRequests': 0,
                'retainedIdentityCount': len(accepted), 'evidenceVersionSha256': sha(evidence)}
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    identity_data = materialize(base, accepted, evidence, next_version, day)
    identity_measurement = gate(base, identity_data, {'candidates': [], 'daysPerAirport': 0})
    code_assignments, code_evidence = korean.assignments(cp, grants, accepted, evidence, store, base, day)
    # Link every fact-bearing original to the code claim, not merely AD pages.
    all_sources = sorted(e['sourceId'] for e in evidence['sources'])
    for assignment in code_assignments:
        assignment['sourceIds'] = all_sources
    candidate = materialize(base, accepted, evidence, next_version, day, code_assignments)
    selected_codes = {a['code'] for a in code_assignments}
    scoped_evidence = {**code_evidence, 'candidates': [c for c in code_evidence['candidates'] if c['code'] in selected_codes]}
    measurement = gate(base, candidate, scoped_evidence)
    receipt = {'formatVersion': 2, 'releaseValidator': 'rule-bundle@1.0.0', 'baselineCommit': baseline_commit,
        'baselineSha256': sha(base), 'candidateSha256': sha(candidate), 'identityCandidateSha256': sha(identity_data),
        'evidenceVersionSha256': sha(evidence), 'registrySha256': sha(admitted['registry']),
        'policies': [checked_bindings(ip), checked_bindings(cp)],
        'authorizationSha256': [sha(identity_grant), sha(code_grant)], 'reviewedOn': day,
        'originalBytesReadHere': code_evidence['originalBytesReadHere'], 'testOnly': False, 'humanMergeRequired': True,
        'identityResolver': identity_measurement, 'resolver': measurement,
        'decisions': admitted['decisions'], 'competitionInventorySha256': sha(competition)}
    # Only after both actual schema/resolver gates succeed do candidate files exist.
    for name, value in [('baseline.json', base), ('baseline-identities.json', registry), ('proposed-data.json', candidate),
        ('identity-data.json', identity_data), ('receipt.json', receipt), ('evidence-version.json', evidence),
        ('identities.json', admitted['registry']), ('authorizations.json', grants),
        ('candidates.json', candidates), ('exceptions.json', admitted['exceptions']), ('code-evidence.json', scoped_evidence)]:
        write(output / name, value)
    write(PRIVATE / 'pending-identities.json', admitted['registry'])
    return receipt


def prepare(*args, **kwargs):
    import fcntl
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with (PRIVATE / 'allocation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _prepare(*args, **kwargs)


def validate(bundle, store=None, *, originals=True):
    bundle = Path(bundle)
    receipt = load(bundle / 'receipt.json')
    require(receipt['formatVersion'] == 2 and receipt['releaseValidator'] == 'rule-bundle@1.0.0' and
            receipt['testOnly'] is False and receipt['humanMergeRequired'] is True, 'Unsupported or simulated release bundle')
    base, candidate = load(bundle / 'baseline.json'), load(bundle / 'proposed-data.json')
    require(sha(base) == receipt['baselineSha256'] and sha(candidate) == receipt['candidateSha256'], 'Bundle data detached')
    # Prove the archived baseline against Git, never a mutable working-tree baseline.
    raw = subprocess.check_output(['git', 'show', receipt['baselineCommit'] + ':data/airports.json'], cwd=ROOT)
    require(__import__('json').loads(raw) == base, 'Baseline is not the recorded published commit')
    version(candidate['dataVersion'], base['dataVersion'])
    ip, cp = policy('identity'), policy('kr-code')
    require(receipt['policies'] == [checked_bindings(ip), checked_bindings(cp)], 'Release executor/policy changed')
    evidence, candidates = load(bundle / 'evidence-version.json'), load(bundle / 'candidates.json')
    registry, grants = load(bundle / 'identities.json'), load(bundle / 'authorizations.json')
    require(sha(evidence) == receipt['evidenceVersionSha256'] and sha(registry) == receipt['registrySha256'], 'Detached evidence/identity registry')
    require(receipt['authorizationSha256'] == [sha(authorize(ip, grants)), sha(authorize(cp, grants))], 'Detached authorization')
    if not originals:
        # Offline CI can establish schema/immutability/resolver replay only.
        # It cannot promote a bundle or return the production validation result.
        measurement = gate(base, candidate, load(bundle / 'code-evidence.json'))
        require(measurement == receipt['resolver'], 'Offline resolver receipt mismatch')
        return {'mode': 'offline-structure-and-resolver', 'originalBytesReadHere': False,
                'productionValidationPassed': False, 'resolver': measurement}
    store = store or Store()
    require(load(PUBLIC / 'identities.json') == {'formatVersion': 1, 'identities': []} or
            all(r in registry['identities'] for r in load(PUBLIC / 'identities.json')['identities']), 'Published identities lost')
    baseline_registry = load(bundle / 'baseline-identities.json') if (bundle / 'baseline-identities.json').exists() else {'formatVersion': 1, 'identities': []}
    competition = inventory(base, baseline_registry)
    require(sha(competition) == receipt['competitionInventorySha256'], 'Competition inventory changed; regenerate bundle')
    accepted, decisions = [], []
    used = set()
    for item in candidates:
        decision = classify(item, ip, evidence, store, competition)
        decisions.append(decision)
        if decision['classification'] != AUTO:
            continue
        entry = next((r for r in registry['identities'] if r['siteKey'] == decision['siteKey']), None)
        require(entry is not None and re.fullmatch(r'apt_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', entry['airportId']) and
                entry['airportId'] not in used and sha(entry['airportId']) not in legacy.policy()['rejectedResearchIdentitySha256'], 'Invalid, reused or research UUID')
        proof = {'candidateSha256': sha(item), 'evidenceVersionSha256': sha(evidence),
                 'bindings': checked_bindings(ip), 'authorizationSha256': receipt['authorizationSha256'][0]}
        require((all(entry[k] == v for k, v in proof.items()) or proof in entry.get('revalidations', [])) and
                entry['coordinates'] == decision['coordinates'], 'Unapproved identity provenance')
        used.add(entry['airportId'])
        accepted.append({'candidate': item, 'identity': entry, 'decision': decision})
    require(decisions == receipt['decisions'] and queue(decisions) == load(bundle / 'exceptions.json'), 'Stale/tampered decisions')
    require({r['airportId'] for r in registry['identities']} == used | {r['airportId'] for r in baseline_registry['identities']}, 'Extra unreviewed identity')
    assignments, code_evidence = korean.assignments(cp, grants, accepted, evidence, store, base, receipt['reviewedOn'])
    for assignment in assignments: assignment['sourceIds'] = sorted(e['sourceId'] for e in evidence['sources'])
    reconstructed = materialize(base, accepted, evidence, candidate['dataVersion'], receipt['reviewedOn'], assignments)
    require(reconstructed == candidate, 'Rule replay differs from formal candidate')
    identity_data = materialize(base, accepted, evidence, candidate['dataVersion'], receipt['reviewedOn'])
    require(identity_data == load(bundle / 'identity-data.json') and sha(identity_data) == receipt['identityCandidateSha256'], 'Identity admission stage detached')
    require(gate(base, identity_data, {'candidates': [], 'daysPerAirport': 0}) == receipt['identityResolver'], 'Identity schema/resolver changed')
    scoped_codes = {a['code'] for a in assignments}
    code_evidence['candidates'] = [c for c in code_evidence['candidates'] if c['code'] in scoped_codes]
    require(code_evidence == load(bundle / 'code-evidence.json'), 'Detached code evidence')
    require(gate(base, candidate, code_evidence) == receipt['resolver'], 'Resolver changed')
    return {'mode': 'fresh-private-original-replay', 'originalBytesReadHere': True, 'productionValidationPassed': True,
            'candidateSha256': sha(candidate), 'resolver': receipt['resolver']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'validate'])
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--data-version')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        require(not args.offline and args.manifest is not None, 'Production preparation requires originals')
        result = prepare(load(args.manifest), Store(), load(PUBLIC / 'authorizations.json'), args.data_version, args.bundle)
    else:
        result = validate(args.bundle, originals=not args.offline)
    print(__import__('json').dumps({k: v for k, v in result.items() if k not in ('decisions', 'resolver', 'identityResolver')}))
