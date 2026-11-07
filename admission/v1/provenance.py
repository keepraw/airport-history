"""Replay complete identity provenance across evidence and executor generations.

The origin envelope is an explicit executor input. It contains metadata only.
The unchanged origin executor verifies its own bundles, live grants and originals
in its real Git tree. A current attestation requires a separate live current grant.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

from runtime import ROOT, PUBLIC, PRIVATE, authorize, bindings, checked_bindings, load, policy, private_path, require, sha, write, git_environment
from evidence import Store

ANCHOR = PUBLIC / 'pending-provenance.json'
LEGACY_KIND = 'pending-identity-revalidation@1'
KIND = 'identity-provenance-chain@2'


def origin_metadata():
    packet = load(ANCHOR)
    require(packet['formatVersion'] == 1 and packet['bundles'], 'Missing origin provenance')
    require(re.fullmatch('[0-9a-f]{40}', packet['originCommit']) and
            all(re.fullmatch('[0-9a-f]{64}', packet[k]) for k in ('originExecutorSha256', 'recoveryArchiveSha256')),
            'Invalid immutable origin address')
    subprocess.run(['git', '--no-replace-objects', 'merge-base', '--is-ancestor', packet['originCommit'], 'HEAD'], cwd=ROOT, env=git_environment(), check=True)
    originals = packet['originPendingRegistry']['identities']
    require(len({r['airportId'] for r in originals}) == len(originals) ==
            len({r['siteKey'] for r in originals}), 'Duplicate origin identity')
    for bundle in packet['bundles']:
        files = bundle['files']
        require(sha(files) == bundle['bundleSha256'] and
                files['receipt.json']['baselineCommit'] == packet['originCommit'], 'Detached origin bundle')
        for kind, binding in zip(('identity', 'kr-code'), files['receipt.json']['policies']):
            current = bindings(policy(kind))
            require(binding == {**current, 'executorSha256': packet['originExecutorSha256']},
                    'Origin Policy/Scope differs from the current rule')
    first = packet['bundles'][0]['files']['identities.json']['identities']
    require({r['airportId'] for r in first} == {r['airportId'] for r in originals}, 'Origin UUID set changed')
    for entry in originals:
        initial = next(r for r in first if r['airportId'] == entry['airportId'])
        require({k: v for k, v in entry.items() if k != 'revalidations'} == initial,
                'Origin credential differs from the original production bundle')
        for attestation in entry.get('revalidations', []):
            require(any(attestation in r.get('revalidations', []) for b in packet['bundles']
                        for r in b['files']['identities.json']['identities']
                        if r['airportId'] == entry['airportId']), 'Unproved historical attestation')
    return packet


def origin_for(entry, packet=None):
    packet = packet or origin_metadata()
    origin = next((r for r in packet['originPendingRegistry']['identities']
                   if r['airportId'] == entry['airportId']), None)
    require(origin is not None, 'Pending identity has no verified production origin; UUID allocation blocked')
    require({k: v for k, v in entry.items() if k != 'revalidations'} ==
            {k: v for k, v in origin.items() if k != 'revalidations'}, 'Original identity credential changed')
    history = origin.get('revalidations', [])
    require(entry.get('revalidations', [])[:len(history)] == history, 'Historical identity attestations changed')
    return origin


def ensure_preserved_ids(registry, candidates, packet):
    """A lost pending file must block, rather than make an old site look new."""
    from identity import site_key
    require(registry.get('formatVersion') == 1, 'Unknown pending registry format')
    first = packet['bundles'][0]['files']['candidates.json']
    for origin in packet['originPendingRegistry']['identities']:
        old = next(c for c in first if sha(c) == origin['candidateSha256'])
        if not any(c['candidateKey'] == old['candidateKey'] or site_key(c) == origin['siteKey'] for c in candidates):
            continue
        matches = [e for e in registry['identities'] if e['siteKey'] == origin['siteKey']]
        require(len(matches) == 1 and matches[0]['airportId'] == origin['airportId'],
                'Preserved pending UUID missing or replaced; restore its verified ledger, never remint')
        origin_for(matches[0], packet)


def extend_identity(first, second):
    """Merge a pending/published ledger only by extending an identical prefix."""
    require({k: v for k, v in first.items() if k != 'revalidations'} ==
            {k: v for k, v in second.items() if k != 'revalidations'}, 'Original identity credential changed')
    a, b = first.get('revalidations', []), second.get('revalidations', [])
    require(a[:len(b)] == b or b[:len(a)] == a, 'Divergent historical identity attestations')
    return deepcopy(second if len(b) > len(a) else first)


def verify_old(packet, store):
    """No cached receipt, test transport or new code executes as old authority."""
    archive = private_path(PRIVATE / 'provenance' / (packet['recoveryArchiveSha256'] + '.tar.gz'))
    with archive.open('rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == packet['recoveryArchiveSha256'],
                'Recovery archive changed')
    manifest = packet['bundles'][0]['files']['evidence-version.json']
    components = [c for s in manifest['sources'] for c in s.get('components', [s])]
    expected = {c['originalSha256']: c['originalBytes'] for c in components}
    require(all(c['originalBytes'] == expected[c['originalSha256']] for c in components), 'Inconsistent component sizes')
    found, checked_metadata, member_names = set(), set(), set()
    prefix = packet['archiveBundlePrefix']
    with tarfile.open(archive, 'r|gz') as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and '..' not in path.parts and
                    (member.isfile() or member.isdir()) and member.name not in member_names, 'Unsafe recovery member')
            member_names.add(member.name)
            if not member.isfile():
                continue
            if member.name == packet['archivePendingPath']:
                require(json.load(tar.extractfile(member)) == packet['originPendingRegistry'], 'Detached recovery ledger')
                checked_metadata.add('ledger')
            elif member.name.startswith(prefix) and member.name[len(prefix):] in packet['bundles'][0]['files']:
                name = member.name[len(prefix):]
                require(json.load(tar.extractfile(member)) == packet['bundles'][0]['files'][name], 'Changed recovery bundle')
                checked_metadata.add(name)
            elif member.name.startswith('work/rule-admission/cas/sha256/'):
                key = ''.join(path.parts[-2:])
                if key in expected:
                    require(member.size == expected[key] and
                            hashlib.file_digest(tar.extractfile(member), 'sha256').hexdigest() == key,
                            'Corrupt recovery original')
                    found.add(key)
    require(found == set(expected) and checked_metadata == {'ledger', *packet['bundles'][0]['files']},
            'Incomplete recovery archive')
    PRIVATE.mkdir(parents=True, exist_ok=True)
    env = git_environment()
    with tempfile.TemporaryDirectory(prefix='origin-replay-', dir=PRIVATE) as tmp:
        frozen = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', '--shared', '--no-checkout', str(ROOT), str(frozen)], env=env, check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--detach', packet['originCommit']], cwd=frozen, env=env, check=True)
        require(subprocess.check_output(['git', 'status', '--porcelain'], cwd=frozen, env=env, text=True).strip() == '',
                'Origin executor checkout is dirty')
        # Copy only hash-checked originals; the old Store enforces its own root.
        for key in expected:
            raw = store.read(key)
            require(len(raw) == expected[key], 'Current origin CAS size mismatch')
            target = frozen / 'work/rule-admission/cas/sha256' / key[:2] / key[2:]
            target.parent.mkdir(parents=True, exist_ok=True)
            with os.fdopen(os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as stream:
                stream.write(raw)
        for i, bundle in enumerate(packet['bundles']):
            for name, value in bundle['files'].items():
                write(frozen / 'work/origin-bundles' / str(i) / name, value)
        program = """import sys,json
sys.path.insert(0,'admission/v1')
import runtime as r
from release import validate
assert r.fingerprint()['executorSha256'] == sys.argv[1]
proofs=[validate(r.ROOT/'work/origin-bundles'/str(i)) for i in range(int(sys.argv[2]))]
assert all(p['productionValidationPassed'] and p['originalBytesReadHere'] for p in proofs)
print(json.dumps({'oldExecutorSha256':r.fingerprint()['executorSha256'],'bundlesVerified':len(proofs),
 'oldOwnerAuthorization':'live-github-api','originalBytesReadHere':True}))
"""
        return json.loads(subprocess.check_output(['python3', '-I', '-c', program,
            packet['originExecutorSha256'], str(len(packet['bundles']))], cwd=frozen, env=env, text=True))


def git(*args):
    return subprocess.check_output(['git', '--no-replace-objects', *args], cwd=ROOT,
                                   env=git_environment(), text=True)


def context(candidate_batch, p, grant, evidence, competition, decisions):
    """Metadata only. Every original remains addressed in the private CAS."""
    return {'executorCommit': git('rev-parse', 'HEAD').strip(), 'policy': deepcopy(p),
            'grant': deepcopy(grant), 'candidates': deepcopy(candidate_batch),
            'evidence': deepcopy(evidence), 'competition': deepcopy(competition),
            'decisions': deepcopy(decisions)}


def proof_fields(candidate, evidence, binding, grant):
    return {'candidateSha256': sha(candidate), 'evidenceVersionSha256': sha(evidence),
            'bindings': binding, 'authorizationSha256': sha(grant)}


def validate_context(ctx, binding, authorization_sha):
    require(set(ctx) == {'executorCommit', 'policy', 'grant', 'candidates', 'evidence', 'competition', 'decisions'},
            'Incomplete historical provenance context')
    require(re.fullmatch('[0-9a-f]{40}', ctx['executorCommit']) and
            ctx['grant']['bindings'] == binding and sha(ctx['grant']) == authorization_sha and
            binding['policyKey'] == ctx['policy']['policyKey'] and
            binding['policySha256'] == sha(ctx['policy']) and binding['scopeSha256'] == sha(ctx['policy']['scope']),
            'Historical authorization/context binding mismatch')
    git('merge-base', '--is-ancestor', ctx['executorCommit'], 'HEAD')
    require(len(ctx['candidates']) == len(ctx['decisions']) and all(
        d['candidateSha256'] == sha(c) and d['evidenceVersionSha256'] == sha(ctx['evidence']) and
        d['policyKey'] == binding['policyKey'] and c['competitionInventorySha256'] == sha(ctx['competition'])
        for c, d in zip(ctx['candidates'], ctx['decisions'])), 'Detached historical decisions')


def replay_context(ctx, store, *, originals=True):
    """Authenticate with the generation's own code and grant, never today's grant.

    No receipt substitutes for an original read. Offline callers still execute
    the old binding and live-comment checks but explicitly cannot issue proofs.
    """
    PRIVATE.mkdir(parents=True, exist_ok=True)
    env = git_environment()
    with tempfile.TemporaryDirectory(prefix='generation-replay-', dir=PRIVATE) as tmp:
        frozen = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', '--shared', '--no-checkout', str(ROOT), str(frozen)], env=env, check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--detach', ctx['executorCommit']], cwd=frozen, env=env, check=True)
        if originals:
            for entry in ctx['evidence']['sources']:
                for obj in entry.get('components', [entry]):
                    key = obj['originalSha256']
                    raw = store.read(key)
                    require(len(raw) == obj['originalBytes'], 'Historical original size mismatch')
                    target = frozen / 'work/rule-admission/cas/sha256' / key[:2] / key[2:]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        with os.fdopen(os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'wb') as stream:
                            stream.write(raw)
        write(frozen / 'work/context.json', ctx)
        program = """import sys,json
sys.path.insert(0,'admission/v1')
import runtime as r
c=r.load('work/context.json')
p=c['policy']
assert p==r.policy('identity')
r.authorize(p,{'formatVersion':1,'authorizations':[c['grant']]})
from batch import inventory
ledger={'formatVersion':1,'identities':[{'airportId':i['inventoryId'],
    'siteKey':i['siteKey'],'coordinates':i['coordinates']} for i in c['competition']
    if i['status'] in ('formal','pending') and i.get('siteKey')]}
assert inventory(r.load(r.ROOT/'data/airports.json'),ledger)==c['competition'], 'Historical competition differs from frozen baseline'
if sys.argv[1]=='originals':
    from evidence import Store,replay
    from identity import classify_batch
    store=Store()
    replay(c['evidence'],store)
    decisions=classify_batch(c['candidates'],p,c['evidence'],store,c['competition'])
    assert decisions==c['decisions'], 'Historical original replay differs'
else:
    decisions=c['decisions']
print(json.dumps(decisions))
"""
        return json.loads(subprocess.check_output(['python3', '-I', '-c', program,
            'originals' if originals else 'offline'], cwd=frozen, env=env, text=True))


def historical_context(previous, packet):
    """Recover pre-chain contexts and grants from retained bundles / Git history.

    Grant hashes are addresses, not authority. replay_context always authenticates
    the recovered record through that historical executor's real Owner reader.
    """
    from batch import inventory
    def retained_bundles():
        yield from packet['bundles']
        # Later published pre-chain bundles may have left the worktree. Read
        # history lazily so known origin contexts need no archive-wide scan.
        seen = set()
        for commit in git('log', '--format=%H', 'HEAD', '--', 'research/admissions').splitlines():
            for name in git('ls-tree', '-r', '--name-only', commit, 'research/admissions').splitlines():
                if not name.endswith('/rule-v1/receipt.json'):
                    continue
                oid = git('rev-parse', commit + ':' + name).strip()
                if oid in seen:
                    continue
                seen.add(oid)
                prefix = name[:-len('receipt.json')]
                names = ('receipt.json', 'candidates.json', 'evidence-version.json', 'baseline.json',
                         'baseline-identities.json', 'authorizations.json')
                files = {n: json.loads(git('show', commit + ':' + prefix + n)) for n in names}
                yield {'files': files, 'bundleSha256': sha(files)}
    for bundle in retained_bundles():
        files = bundle['files']
        if sha(files['evidence-version.json']) != previous['evidenceVersionSha256'] or not any(
                sha(c) == previous['candidateSha256'] for c in files['candidates.json']):
            continue
        grants = list(files['authorizations.json']['authorizations'])
        commits = [files['receipt.json']['baselineCommit'], packet['originCommit'], *git('log', '--format=%H', 'HEAD', '--',
            'research/admission/rule-v1/authorizations.json', 'research/admission/rule-v1/bindings.json').splitlines()]
        for commit in dict.fromkeys(commits):
            registry = json.loads(git('show', commit + ':research/admission/rule-v1/authorizations.json'))
            grants.extend(registry['authorizations'])
            frozen_bindings = json.loads(git('show', commit + ':research/admission/rule-v1/bindings.json'))
            grant = next((g for g in grants if sha(g) == previous['authorizationSha256'] and
                          g['bindings'] == previous['bindings']), None)
            if grant is None or frozen_bindings['policies'].get(grant['policyKey']) != previous['bindings']:
                continue
            historical_policy = json.loads(git('show', commit + ':research/admission/rule-v1/identity-policy.json'))
            return {'executorCommit': commit, 'policy': historical_policy, 'grant': grant,
                'candidates': files['candidates.json'], 'evidence': files['evidence-version.json'],
                'competition': inventory(files['baseline.json'], files['baseline-identities.json']),
                'decisions': files['receipt.json']['decisions']}
    raise ValueError('Missing historical provenance context/grant; restore retained bundles, never remint')


def matching_decision(entry, ctx, candidate_sha):
    matches = [(c, d) for c, d in zip(ctx['candidates'], ctx['decisions']) if sha(c) == candidate_sha]
    require(len(matches) == 1, 'Historical candidate missing or ambiguous')
    candidate, decision = matches[0]
    require(decision['classification'] == 'AUTO_ELIGIBLE' and decision['siteKey'] == entry['siteKey'] and
            decision['coordinates'] == entry['coordinates'], 'Historical physical identity revalidation blocked')
    return candidate, decision


def attestation(entry, candidate, decision, ctx):
    previous = entry.get('revalidations', [])
    return {**proof_fields(candidate, ctx['evidence'], ctx['grant']['bindings'], ctx['grant']),
        'kind': KIND, 'airportId': entry['airportId'], 'siteKey': entry['siteKey'],
        'previousProvenanceSha256': sha(previous[-1]) if previous else sha({k: v for k, v in entry.items() if k != 'revalidations'}),
        'generation': len(previous) + 1, 'context': deepcopy(ctx), 'decisionSha256': sha(decision)}


def legacy_expected(entry, previous, ctx, packet):
    candidate, decision = matching_decision(entry, ctx, previous['candidateSha256'])
    fields = proof_fields(candidate, ctx['evidence'], ctx['grant']['bindings'], ctx['grant'])
    if previous.get('kind') != LEGACY_KIND:
        return fields
    origin = origin_for(entry, packet)
    bundle = next((b for b in packet['bundles'] if b['bundleSha256'] == previous.get('originReviewBundleSha256')), None)
    require(bundle is not None and any(sha(c) == sha(candidate) for c in bundle['files']['candidates.json']) and
            sha(bundle['files']['evidence-version.json']) == sha(ctx['evidence']), 'Unknown historical revalidation context')
    return {**fields, 'originReviewBundleSha256': bundle['bundleSha256'], 'kind': LEGACY_KIND,
        'airportId': origin['airportId'], 'siteKey': origin['siteKey'], 'classification': decision['classification'],
        'decisionSha256': sha(decision), 'competitionInventorySha256': sha(ctx['competition']),
        'originCommit': packet['originCommit'], 'originExecutorSha256': packet['originExecutorSha256'],
        'originCredentialSha256': sha(origin), 'originBundleSha256': packet['bundles'][0]['bundleSha256'],
        'originArchiveSha256': packet['recoveryArchiveSha256'], 'originEnvelopeSha256': sha(packet)}


def revalidate_registry(registry, candidates, p, grants, evidence, store, competition, *, append=True, metadata_decisions=None):
    grant = authorize(p, grants)  # Every generation needs its own live current authorization.
    current = checked_bindings(p)
    packet = origin_metadata()
    ensure_preserved_ids(registry, candidates, packet)
    require(metadata_decisions is None or not append, 'Metadata-only provenance cannot issue attestations')
    from identity import classify_batch
    decisions = (classify_batch(candidates, p, evidence, store, competition)
                 if metadata_decisions is None else metadata_decisions)
    ctx = context(candidates, p, grant, evidence, competition, decisions)
    validate_context(ctx, current, sha(grant))
    output = deepcopy(registry)
    replayed = set()
    origins = {r['airportId'] for r in packet['originPendingRegistry']['identities']}
    if any(e['airportId'] in origins for e in registry['identities']) and metadata_decisions is None:
        verify_old(packet, store)  # Always replay the original credentials, including after formal admission.
    def verify_generation(historical, binding, grant_sha):
        validate_context(historical, binding, grant_sha)
        key = sha(historical)
        if key not in replayed:
            replayed.add(key)
            require(replay_context(historical, store, originals=metadata_decisions is None) == historical['decisions'],
                    'Historical replay differs from provenance')
    for entry in output['identities']:
        history = entry.get('revalidations', [])
        if entry['airportId'] in origins:
            origin = origin_for(entry, packet)
            inherited = len(origin.get('revalidations', []))
        else:
            root_context = entry.get('provenanceContext')
            require(root_context is not None, 'Identity has no verified production origin; UUID allocation blocked')
            verify_generation(root_context, entry['bindings'], entry['authorizationSha256'])
            candidate, decision = matching_decision(entry, root_context, entry['candidateSha256'])
            expected_root = {**proof_fields(candidate, root_context['evidence'], entry['bindings'], root_context['grant']),
                'siteKey': decision['siteKey'], 'airportId': entry['airportId'], 'coordinates': decision['coordinates'],
                'policyKey': root_context['policy']['policyKey'], 'provenanceContext': root_context,
                'sourceIds': sorted({o['sourceId'] for o in candidate['observations']} | {candidate['independent']['sourceId']})}
            require({k: v for k, v in entry.items() if k != 'revalidations'} == expected_root,
                    'Original identity credential changed')
            inherited = 0
        prefix = {**entry, 'revalidations': history[:inherited]}
        chain_started = False
        for previous in history[inherited:]:
            if previous.get('kind') == KIND:
                chain_started = True
                historical = previous['context']
                verify_generation(historical, previous['bindings'], previous['authorizationSha256'])
                candidate, decision = matching_decision(entry, historical, previous['candidateSha256'])
                require(previous == attestation(prefix, candidate, decision, historical), 'Foreign or changed provenance attestation')
            else:
                require(not chain_started, 'Unlinked provenance after chain generation')
                historical = historical_context(previous, packet)
                verify_generation(historical, previous['bindings'], previous['authorizationSha256'])
                require(previous == legacy_expected(entry, previous, historical, packet), 'Foreign or changed provenance attestation')
            prefix['revalidations'].append(previous)
        matches = [(c, d) for c, d in zip(candidates, decisions) if d['siteKey'] == entry['siteKey']]
        if not matches:
            require(any(i.get('inventoryId') == entry['airportId'] and i.get('status') == 'formal' for i in competition),
                    'Preserved pending identity candidate missing or ambiguous; allocation blocked')
            continue
        require(len(matches) == 1, 'Current identity candidate ambiguous')
        candidate, decision = matches[0]
        require(decision['classification'] == 'AUTO_ELIGIBLE' and decision['coordinates'] == entry['coordinates'],
                'Current pending physical identity revalidation blocked')
        fields = proof_fields(candidate, evidence, current, grant)
        latest = history[-1] if history else entry
        if all(latest.get(k) == v for k, v in fields.items()) and (
                latest.get('kind') == KIND or not history and entry.get('provenanceContext')):
            continue
        require(append, 'Missing current provenance revalidation attestation')
        entry.setdefault('revalidations', []).append(attestation(entry, candidate, decision, ctx))
    return output


def review(registry, evidence, store):
    """Read-only: prove old authority and new facts; issue no current credential."""
    from batch import inventory, discover
    from identity import classify_batch
    packet = origin_metadata()
    old = verify_old(packet, store)
    base = load(ROOT / 'data/airports.json')
    competition = inventory(base, registry)
    candidates = discover(competition)
    ensure_preserved_ids(registry, candidates, packet)
    decisions = classify_batch(candidates, policy('identity'), evidence, store, competition)
    for entry in registry['identities']:
        origin = origin_for(entry, packet)
        matched = [d for d in decisions if d['siteKey'] == origin['siteKey']]
        require(len(matched) == 1 and matched[0]['classification'] == 'AUTO_ELIGIBLE' and
                matched[0]['coordinates'] == origin['coordinates'], 'Current physical identity revalidation blocked')
    return {'mode': 'pre-authorization-read-only-provenance-review', 'oldProductionProof': old,
        'originEnvelopeSha256': sha(packet), 'recoveryArchiveSha256': packet['recoveryArchiveSha256'],
        'currentExecutorSha256': bindings(policy('identity'))['executorSha256'], 'decisions': decisions,
        'preservedPendingUUIDs': [e['airportId'] for e in registry['identities']],
        'newOwnerAuthorizationVerified': False, 'newAttestationsIssued': 0, 'formalIdentitiesAdded': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['review'])
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = private_path(args.output, new=True)
    result = review(load(args.registry), load(args.manifest), Store())
    write(output, result)
    print(json.dumps(result))
