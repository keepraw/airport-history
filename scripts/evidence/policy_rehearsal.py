"""Real VEHO/VASD/VOKN end-to-end exercise in a disposable, uncommitted clone.

Only the authority and original-verification dependencies are test adapters.
Decision evaluation, activation validation, admission CLI, schema, resolver and
full candidate pnpm check execute normally. Production rejects the test grant.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from policy_review import ROOT, DIRECTORY, inputs, load, digest, require, write_json, sha
from policy_executor import fingerprint

TEST_AUTHORITY = {'principal': {'login': 'policy-rehearsal', 'githubUserId': 0},
    'sourcePattern': r'test-fixture://policy-rehearsal/\d+',
    'kind': 'isolated-test-authority', 'recorder': 'isolated-rehearsal'}


def rehearsal(*, live=False, full=True):
    require(os.environ.get('AIRPORT_POLICY_REHEARSAL_ACTIVE') != '1', 'Nested rehearsal is forbidden')
    paths = ['data/airports.json', 'research/policy/policy.json',
             'research/policy/authorizations.json', 'research/policy/batch-authorizations.json']
    before = {p: digest(ROOT / p) for p in paths}
    _, lock, *_ = inputs()
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='isolated-policy-', dir=ROOT / 'work') as tmp:
        root = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', '--shared', str(ROOT), str(root)], check=True)
        # Include reviewed working edits during local development, never ignored originals/secrets.
        files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
        for raw in files.split(b'\0'):
            if not raw: continue
            p = Path(raw.decode())
            require(not (ROOT / p).is_symlink(), 'No symlinked input in rehearsal')
            (root / p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / p, root / p)
        # Start the disposable test lifecycle independently of the real owner grant.
        # Only this temporary clone receives a draft and an empty test registry.
        test_policy = load(root / 'research/policy/policy.json')
        test_policy['status'] = 'draft'
        write_json(root / 'research/policy/policy.json', test_policy)
        write_json(root / 'research/policy/authorizations.json', {'formatVersion': 1, 'authorizations': []})
        write_json(root / 'research/policy/batch-authorizations.json', {'formatVersion': 1, 'authorizations': []})
        subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', lock['baseline']['baseCommit']], cwd=root, check=True)
        (root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        private = root / 'work'; private.mkdir(exist_ok=True)
        if live:
            from policy_originals import required_sources
            from policy_review import evaluate
            selected = [d for d in evaluate() if d['sample'] == 'unpublished' and d['risk'] == 'low']
            for s in required_sources(selected):
                path = Path(s['privateOriginalPath'])
                require((ROOT / path).resolve().is_relative_to(ROOT / 'work'), 'Unsafe private original')
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / path, root / path)
        bootstrap = private / 'test-authority'; bootstrap.mkdir()
        bootstrap_code = '''import os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
assert os.environ.get('AIRPORT_POLICY_REHEARSAL_ACTIVE') == '1'
sys.path.insert(0, str(root / 'scripts/evidence'))
import policy_gate as gate
from policy_review import load, DIRECTORY
gate.AUTHORITY = AUTHORITY
def test_comment(url):
    assert url == 'test-fixture://policy-rehearsal/1'
    p = load(DIRECTORY / 'policy.json')
    day = load(DIRECTORY / 'input-lock.json')['reviewedOn']
    return {'html_url': url, 'user': {'login': 'policy-rehearsal', 'id': 0},
            'body': gate.grant_text(p), 'created_at': day + 'T00:00:00Z'}
gate.read_owner_comment = test_comment
if os.environ.get('AIRPORT_POLICY_REHEARSAL_ORIGINALS') == 'offline':
    def recorded_originals(decisions):
        from policy_originals import validate_offline
        record = load(DIRECTORY / 'verification/low.json')
        validate_offline(record, decisions)
        print('TEST ADAPTER: offline receipt replay; this CI process did not acquire original bytes.')
        return record
    gate.verify_originals = recorded_originals
'''.replace('gate.AUTHORITY = AUTHORITY', 'gate.AUTHORITY = ' + repr(TEST_AUTHORITY))
        (bootstrap / 'sitecustomize.py').write_text(bootstrap_code)
        env = {**os.environ, 'PYTHONPATH': str(bootstrap), 'AIRPORT_POLICY_REHEARSAL_ACTIVE': '1',
               'AIRPORT_POLICY_REHEARSAL_ORIGINALS': 'live' if live else 'offline'}
        log = private / 'rehearsal.log'
        def run(args, *, test_env=True, success=True):
            with log.open('a') as stream:
                result = subprocess.run(args, cwd=root, env=env if test_env else os.environ,
                    stdout=stream, stderr=subprocess.STDOUT)
            if success and result.returncode:
                print(log.read_text()[-14000:])
                raise ValueError('Isolated rehearsal stage failed: ' + ' '.join(args))
            return result.returncode
        run(['python3', 'scripts/evidence/policy_review.py', 'activate',
             '--authorization-url', 'test-fixture://policy-rehearsal/1'])
        grant = load(root / 'research/policy/authorizations.json')['authorizations'][0]
        require(grant['authorizedBy'] == TEST_AUTHORITY['principal'] and grant['authorityKind'] == 'isolated-test-authority',
                'Rehearsal must never impersonate an owner grant')
        run(['python3', 'scripts/evidence/policy_review.py', 'admit', '--output', 'work/admission-bundle'])
        require(run(['python3', 'scripts/evidence/policy_review.py', 'admit', '--output', 'work/production-must-reject'],
                    test_env=False, success=False) != 0 and 'Invalid owner policy authorization' in log.read_text(),
                'Production accepted a test-authority grant')
        require(not (private / 'production-must-reject').exists(), 'Rejected test grant emitted production files')
        candidate = load(private / 'admission-bundle/proposed-data.json')
        baseline = load(root / lock['baseline']['path'])
        additions = candidate['assignments'][len(baseline['assignments']):]
        require({a['code'] for a in additions} == {'VEHO', 'VASD', 'VOKN'} and len(additions) == 3,
                'Rehearsal selection expanded')
        write_json(root / 'data/airports.json', candidate)
        package = load(root / 'package.json'); package['version'] = candidate['dataVersion']
        write_json(root / 'package.json', package)
        bundle = root / 'research/admissions' / candidate['dataVersion']
        shutil.copytree(private / 'admission-bundle', bundle)
        run(['python3', 'scripts/evidence/policy_formal.py'])
        run(['pnpm', 'policy:build'])
        if full: run(['pnpm', 'check'])
        coverage = load(root / 'research/policy/generated/coverage.json')
        require(coverage['candidateFileSha256'] == digest(root / 'data/airports.json'),
                'Resolver measured different bytes from the formal candidate')
        proof = load(bundle / 'original-verification.json')
        result = {'formatVersion': 1, 'testOnly': True, 'authority': TEST_AUTHORITY['principal'],
            'productionRejectedTestGrant': True, 'policySha256': load(root / 'research/policy/policy.json')['policySha256'],
            'executorSha256': fingerprint()['executorSha256'], 'baseline': lock['baseline'],
            'candidateVersion': candidate['dataVersion'], 'candidateSha256': digest(root / 'data/airports.json'),
            'codes': sorted(a['code'] for a in additions), 'addedAirports': len(candidate['airports'])-len(baseline['airports']),
            'addedAssignments': len(additions), 'addedSources': len(candidate['sources'])-len(baseline['sources']),
            'originalVerificationSha256': sha(proof), 'originalSourceCount': len(proof['sources']),
            'originalBytesRecheckedHere': live, 'offlineReceiptReplay': not live,
            'originalAdmissionCliPassed': True, 'fullCandidatePnpmCheckPassed': full,
            'resolverTransitions': coverage['transitions'], 'changedPublishedResolved': coverage['changedPublishedResolved'],
            'newConflicts': coverage['newConflicts'], 'removedConflicts': coverage['removedConflicts']}
    require(before == {p: digest(ROOT / p) for p in paths}, 'Rehearsal changed real formal data or authority registries')
    result['realFormalAndAuthorizationFilesUnchanged'] = True
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-originals', action='store_true', help='Privately replay actual cached originals in the isolated clone')
    parser.add_argument('--skip-full-check', action='store_true', help='Development smoke run only; report explicitly says full check was skipped')
    parser.add_argument('--output', type=Path, default=ROOT / 'work/policy-rehearsal.json')
    args = parser.parse_args()
    require(args.output.resolve().is_relative_to(ROOT / 'work') or
            args.output.resolve() == DIRECTORY / 'generated/rehearsal-live.json', 'Rehearsal report output is restricted')
    result = rehearsal(live=args.live_originals, full=not args.skip_full_check)
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
