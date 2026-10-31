"""Inactive release integrity; never upgrades an offline receipt to raw replay."""
import json

from runtime import ROOT, PUBLIC, bindings, checked_bindings, digest, fingerprint, legacy, load, policy, require


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
    require(proof['bindings'] == [checked_bindings(policy(k)) for k in ('identity', 'kr-code')] and
            proof['liveIsolation']['testOnly'] and not proof['liveIsolation']['productionSuccess'] and
            proof['liveIsolation']['originalBytesReadHere'] and proof['liveIsolation']['conditionalResolved'] == 54 and
            proof['liveIsolation']['productionRejectedTestAuthority'], 'Detached/overstated isolation receipt')
    require(load(PUBLIC / 'authorizations.json') == {'formatVersion': 1, 'authorizations': []} and
            load(PUBLIC / 'identities.json') == {'formatVersion': 1, 'identities': []}, 'Inactive release contains real IDs or authority')
    current = load(ROOT / 'data/airports.json')
    require(current['dataVersion'] == '0.10.0' and current['schemaVersion'] == '3.0.0' and
            [len(current[k]) for k in ('airports', 'assignments', 'sources', 'names')] == [37, 52, 101, 3], 'Formal release changed')
    return {'protectedFilesUnchanged': len(protected), 'legacyExecutorsUnchanged': True,
            'realNewIdentities': 0, 'realNewAuthorizations': 0, 'formalNewResolved': 0,
            'newManifestFiles': len(fingerprint()['files']), 'production': 'inactive'}


if __name__ == '__main__':
    print(json.dumps(verify()))
