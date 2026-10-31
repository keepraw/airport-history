"""Build/validate public engineering receipts, without manufacturing approvals."""
import argparse
import collections
import hashlib
import json

from kr_adapter import ROOT, DIRECTORY, policy, bindings, checked_bindings, fingerprint, load, write, require
from kr_evidence import evaluate
from kr_rehearsal import rehearse


def protected():
    frozen = load(DIRECTORY / 'protected-baseline.json')
    for name, digest in frozen.items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, 'Protected baseline changed: ' + name)
    return len(frozen)


def status():
    measurement = load(DIRECTORY / 'verification.json')
    require(measurement['bindings'] == checked_bindings(policy()), 'Stale rehearsal executor')
    recovery = load(DIRECTORY / 'original-recovery.json')
    missing = [s['sourceId'] for s in recovery['sources'] if s['state'] != 'exact-original']
    blockers = ['identity_approval_and_formal_admission_pending', 'real_owner_policy_authorization_pending']
    if missing:
        blockers.append('exact_original_replay_blocked')
    return {'formatVersion': 1, 'policyKey': policy()['policyKey'],
        'engineering': 'implemented_offline_verified_original_replay_blocked' if missing else 'offline_verified',
        'engineeringReady': False,  # Full raw-evidence success has not been demonstrated in this release.
        'identityApproval': 'pending', 'policyAuthorization': 'pending', 'production': 'inactive',
        'realKoreanAuthorizations': len(load(DIRECTORY / 'authorizations.json')['authorizations']),
        'formallyAdmittedKoreanIdentities': len(load(DIRECTORY / 'identities.json')['identities']),
        'formalNewResolved': 0, 'dataVersion': '0.10.0', 'schemaVersion': '3.0.0',
        'formalRegressionQueries': measurement['formalRegressionQueries'],
        'conditionalResolved': measurement['conditionalResolved'], 'originalReplayBlockedSources': missing,
        'candidateQueries': [{**q, 'isolationStatus': q['status'], 'productionStatus': 'blocked',
                             'productionBlockers': blockers} for q in measurement['outcomes']],
        'bindings': measurement['bindings'], 'identityBatchSha256': policy()['identityBatchSha256'],
        'safeIdentityApprovalEntry': 'prepare-identities', 'safePolicyAuthorizationEntry': 'record-policy',
        'formalPromotionIntegration': 'separate future identity/data admission PR and versioned formal replay required',
        'offlineReplayIsNotFreshAcquisition': True}


def validate():
    count = protected()
    p = policy()
    checked_bindings(p)
    result = evaluate(p)
    receipt = load(DIRECTORY / 'verification.json')
    require(receipt['conditionalResolved'] == sum(result['daysPerAirport'] for _ in result['candidates']) and
            receipt['formalRegressionQueries'] == 37736 and receipt['formalChangedAnswers'] == 0 and
            receipt['formalNewResolved'] == 0 and receipt['productionRejectedTestAuthority'] and
            receipt['originalBytesReadHere'] is False, 'Invalid offline engineering receipt')
    require(load(DIRECTORY / 'authorizations.json') == {'formatVersion': 1, 'authorizations': []} and
            load(DIRECTORY / 'identities.json') == {'formatVersion': 1, 'identities': []},
            'This inactive release cannot contain grants or admitted identities')
    require(load(DIRECTORY / 'status.json') == status(), 'Stale production readiness status')
    return {'protectedFiles': count, 'offlineRehearsalResolved': receipt['conditionalResolved'],
            'formalNewResolved': 0, 'engineeringReady': False, 'production': 'inactive'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'validate', 'originals'])
    args = parser.parse_args()
    (ROOT / 'work').mkdir(exist_ok=True)
    if args.command == 'build':
        write(DIRECTORY / 'bindings.json', {**bindings(policy()), 'manifest': fingerprint()})
        receipt = {**rehearse(), 'bindings': checked_bindings(policy())}
        write(DIRECTORY / 'verification.json', receipt)
        write(DIRECTORY / 'status.json', status())
        print(json.dumps(validate(), sort_keys=True))
    elif args.command == 'originals':
        print(json.dumps(evaluate(policy(), originals=True), sort_keys=True))
    else:
        print(json.dumps(validate(), sort_keys=True))
