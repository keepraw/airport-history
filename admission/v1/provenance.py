"""Revalidate the preserved, unmerged production identities without reminting IDs.

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

from runtime import ROOT, PUBLIC, PRIVATE, authorize, bindings, checked_bindings, load, policy, private_path, require, sha, write
from evidence import Store

ANCHOR = PUBLIC / 'pending-provenance.json'
KIND = 'pending-identity-revalidation@1'


def origin_metadata():
    packet = load(ANCHOR)
    require(packet['formatVersion'] == 1 and packet['bundles'], 'Missing origin provenance')
    require(re.fullmatch('[0-9a-f]{40}', packet['originCommit']) and
            all(re.fullmatch('[0-9a-f]{64}', packet[k]) for k in ('originExecutorSha256', 'recoveryArchiveSha256')),
            'Invalid immutable origin address')
    subprocess.run(['git', '--no-replace-objects', 'merge-base', '--is-ancestor', packet['originCommit'], 'HEAD'], cwd=ROOT, check=True)
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
    context_keys = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY',
                    'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_SHALLOW_FILE', 'GIT_NAMESPACE', 'GIT_REPLACE_REF_BASE',
                    'GIT_CONFIG_COUNT', 'GIT_CONFIG_PARAMETERS'}
    env = {k: v for k, v in os.environ.items() if k not in context_keys}
    env['GIT_NO_REPLACE_OBJECTS'] = '1'
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


def transition_context(candidate, evidence, competition_sha, packet):
    from batch import inventory
    for bundle in packet['bundles']:
        files = bundle['files']
        if (any(sha(c) == sha(candidate) for c in files['candidates.json']) and
                sha(files['evidence-version.json']) == sha(evidence) and
                sha(inventory(files['baseline.json'], files['baseline-identities.json'])) == competition_sha):
            return bundle
    raise ValueError('Origin transition context changed; preserve the UUID and revalidate the evidence')


def expected_attestation(entry, candidate, decision, p, grant, evidence, competition_sha, packet):
    origin = origin_for(entry, packet)
    old_candidate = next(c for c in packet['bundles'][0]['files']['candidates.json']
                         if sha(c) == origin['candidateSha256'])
    require(decision['classification'] == 'AUTO_ELIGIBLE', 'Pending identity is no longer AUTO_ELIGIBLE')
    require(candidate['candidateKey'] == old_candidate['candidateKey'] and
            decision['siteKey'] == origin['siteKey'] and decision['coordinates'] == origin['coordinates'],
            'Pending identity candidate/site/ARP changed; no replacement UUID may be minted')
    context = transition_context(candidate, evidence, competition_sha, packet)
    return {'originReviewBundleSha256': context['bundleSha256'], 'kind': KIND, 'airportId': origin['airportId'], 'siteKey': origin['siteKey'],
        'candidateSha256': sha(candidate), 'evidenceVersionSha256': sha(evidence),
        'bindings': checked_bindings(p), 'authorizationSha256': sha(grant),
        'classification': decision['classification'], 'decisionSha256': sha(decision),
        'competitionInventorySha256': competition_sha,
        'originCommit': packet['originCommit'], 'originExecutorSha256': packet['originExecutorSha256'],
        'originCredentialSha256': sha(origin), 'originBundleSha256': packet['bundles'][0]['bundleSha256'],
        'originArchiveSha256': packet['recoveryArchiveSha256'], 'originEnvelopeSha256': sha(packet)}


def revalidate_registry(registry, candidates, p, grants, evidence, store, competition, *, append=True, metadata_decisions=None):
    grant = authorize(p, grants)  # A new attestation always requires live current authority.
    current = checked_bindings(p)
    packet = origin_metadata()
    ensure_preserved_ids(registry, candidates, packet)
    legacy = [e for e in registry['identities'] if e['bindings'] != current or e['authorizationSha256'] != sha(grant)]
    if not legacy:
        return deepcopy(registry)
    if metadata_decisions is None:
        verify_old(packet, store)
        from identity import classify_batch
        decisions = classify_batch(candidates, p, evidence, store, competition)
    else:
        require(not append, 'Metadata-only provenance cannot issue attestations')
        require(len(candidates) == len(metadata_decisions), 'Incomplete offline identity decisions')
        decisions = metadata_decisions
    require(len(decisions) == len(candidates) and all(
        d['candidateSha256'] == sha(c) and d['evidenceVersionSha256'] == sha(evidence) and
        d['policyKey'] == p['policyKey'] for c, d in zip(candidates, decisions)), 'Detached current identity decisions')
    output = deepcopy(registry)
    for entry in output['identities']:
        if entry['bindings'] == current and entry['authorizationSha256'] == sha(grant):
            continue
        origin = origin_for(entry, packet)
        old_candidate = next(c for c in packet['bundles'][0]['files']['candidates.json'] if sha(c) == origin['candidateSha256'])
        matches = [(c, d) for c, d in zip(candidates, decisions) if c['candidateKey'] == old_candidate['candidateKey']]
        require(len(matches) == 1, 'Preserved pending identity candidate missing or ambiguous; allocation blocked')
        candidate, decision = matches[0]
        require(decision['classification'] == 'AUTO_ELIGIBLE' and
                decision['siteKey'] == origin['siteKey'] and decision['coordinates'] == origin['coordinates'],
                'Current pending physical identity revalidation blocked')
        original_history = origin.get('revalidations', [])
        rich = []
        current_proof = {'candidateSha256': sha(candidate), 'evidenceVersionSha256': sha(evidence),
                         'bindings': current, 'authorizationSha256': sha(grant)}
        for previous in entry.get('revalidations', [])[len(original_history):]:
            if previous.get('kind') != KIND:
                require(previous == current_proof, 'Foreign or changed provenance attestation')
                continue
            context = next((b for b in packet['bundles'] if b['bundleSha256'] == previous.get('originReviewBundleSha256')), None)
            require(context is not None, 'Unknown historical revalidation context')
            files = context['files']
            historical = next((c for c in files['candidates.json'] if sha(c) == previous.get('candidateSha256')), None)
            require(historical is not None, 'Historical revalidation candidate changed')
            from batch import inventory
            historical_inventory = inventory(files['baseline.json'], files['baseline-identities.json'])
            if metadata_decisions is None:
                from identity import classify_batch
                old_decisions = classify_batch(files['candidates.json'], p, files['evidence-version.json'], store, historical_inventory)
            else:
                old_decisions = files['receipt.json']['decisions']
            historical_decision = next(d for d in old_decisions if d['candidateSha256'] == sha(historical))
            expected = expected_attestation(entry, historical, historical_decision, p, grant,
                files['evidence-version.json'], sha(historical_inventory), packet)
            require(previous == expected, 'Foreign or changed provenance attestation')
            rich.append(previous)
        require(len(rich) <= 1, 'Duplicate current provenance credential')
        if not rich:
            require(append, 'Missing current provenance revalidation attestation')
            entry.setdefault('revalidations', []).append(expected_attestation(
                entry, candidate, decision, p, grant, evidence, sha(competition), packet))
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
