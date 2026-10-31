"""Release and live rule-registry integrity; offline receipts are not raw replay."""
import json
import subprocess

from runtime import ROOT, PUBLIC, authorize, bindings, checked_bindings, digest, fingerprint, legacy, load, policy, require


def registered_authorizations(registry):
    require(isinstance(registry, dict) and set(registry) == {'formatVersion', 'authorizations'} and
            registry['formatVersion'] == 1 and isinstance(registry['authorizations'], list), 'Invalid rule registry')
    grants = registry['authorizations']
    if not grants:
        return 0  # Preserve validation of the earlier, legitimately inactive release.
    expected = {policy(kind)['policyKey'] for kind in ('identity', 'kr-code')}
    require(len(grants) == 2 and all(isinstance(g, dict) for g in grants) and
            {g.get('policyKey') for g in grants} == expected, 'Expected exactly both independent rule grants')
    for kind in ('identity', 'kr-code'):
        authorize(policy(kind), registry)  # Always fetch the real Owner comments; no offline authority fallback.
    return len(grants)


def verify():
    protected = load(PUBLIC / 'protected-baseline.json')
    require(len(protected) == 923, 'Incomplete PR25 baseline inventory')
    for name, expected in protected.items():
        require(digest((ROOT / name).read_bytes()) == expected, 'Protected PR25 file changed: ' + name)
    require(legacy.checked_bindings(legacy.policy())['executorSha256'] ==
            '3222018573f8204dbed40df839cc64dd1e69e29b490d3fbb2b225bac3f473a6a', 'Legacy Korean executor changed')
    import policy_executor
    require(policy_executor.fingerprint()['executorSha256'] ==
            '2415279526ff8c0eaf9ee1b3ee5afca8bde26e95bfac2c98930212f9f7992a3f', 'Indian executor changed')
    for kind in ('identity', 'kr-code'):
        checked_bindings(policy(kind))
    index = load(PUBLIC / 'evidence-version-index.json')
    for key in index['versions']:
        from runtime import sha
        require(sha(load(PUBLIC / 'evidence-versions' / (key + '.json'))) == key, 'Evidence metadata version changed')
    recovery = load(PUBLIC / 'original-recovery-v2.json')
    require(recovery['evidenceVersionSha256'] == index['currentVersionSha256'] and
            recovery['factBlockersResolvedAmongTwelve'] == 12 and recovery['oldExactBytesRestoredAmongTwelve'] == 0,
            'Detached recovery report')
    proof = load(PUBLIC / 'verification.json')
    # This retained receipt describes the old isolated executor, not this repair.
    # Current grants are still independently checked live below.
    from provenance import origin_metadata
    origin = origin_metadata()
    historical = json.loads(subprocess.check_output(['git', 'show', origin['originCommit'] +
        ':research/admission/rule-v1/verification.json'], cwd=ROOT, text=True))
    require(proof == historical and proof['bindings'] == origin['bundles'][0]['files']['receipt.json']['policies'] and
            proof['liveIsolation']['testOnly'] and not proof['liveIsolation']['productionSuccess'] and
            proof['liveIsolation']['originalBytesReadHere'] and proof['liveIsolation']['conditionalResolved'] == 54 and
            proof['liveIsolation']['productionRejectedTestAuthority'], 'Detached/overstated isolation receipt')
    grant_count = registered_authorizations(load(PUBLIC / 'authorizations.json'))
    require(load(PUBLIC / 'identities.json') == {'formatVersion': 1, 'identities': []}, 'Registration release contains admitted identities')
    current = load(ROOT / 'data/airports.json')
    require(current['dataVersion'] == '0.10.0' and current['schemaVersion'] == '3.0.0' and
            [len(current[k]) for k in ('airports', 'assignments', 'sources', 'names')] == [37, 52, 101, 3], 'Formal release changed')
    return {'protectedFilesUnchanged': len(protected), 'legacyExecutorsUnchanged': True,
            'realNewIdentities': 0, 'realNewAuthorizations': grant_count, 'formalNewResolved': 0,
            'newManifestFiles': len(fingerprint()['files']),
            'historicalIsolationExecutorSha256': origin['originExecutorSha256'],
            'currentExecutorSha256': fingerprint()['executorSha256'],
            'authorizationVerification': 'live-github-api' if grant_count else 'no-grants',
            'production': 'rules-authorized-data-unpublished' if grant_count else 'inactive'}


if __name__ == '__main__':
    print(json.dumps(verify()))
