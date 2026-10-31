"""A–F migration integration against the retained production credentials.

Requires the real private recovery archive, CAS and pending ledger. Missing inputs
fail explicitly; no empty-origin or original-replay mock is used. Later grants
and additional airports are isolated test fixtures, never production authority.
Run: python3 admission/v1/test_migration.py
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import provenance
from evidence import Store


IDS = ['apt_fce8985f-52c3-439b-a8e6-497028823582', 'apt_17ee7ea0-4997-46dd-a12e-35b33546835f']


def run_isolated(manifest=None):
    packet = provenance.origin_metadata()
    archive = r.PRIVATE / 'provenance' / (packet['recoveryArchiveSha256'] + '.tar.gz')
    ledger = r.PRIVATE / 'pending-identities.json'
    r.require(archive.is_file() and ledger.is_file(),
              'BLOCKED: restore the real private recovery archive, CAS and pending ledger; no migration was executed')
    before = {p: r.digest(p.read_bytes()) for p in (archive, ledger)}
    protected = r.load(r.PUBLIC / 'protected-baseline.json')
    protected_before = {p: r.digest((r.ROOT / p).read_bytes()) for p in protected}
    evidence = r.load(manifest) if manifest else packet['bundles'][1]['files']['evidence-version.json']
    store = Store()
    with tempfile.TemporaryDirectory(prefix='real-migration-', dir=r.ROOT / 'work') as tmp:
        root = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', '--shared', str(r.ROOT), str(root)],
                       env=r.git_environment(), check=True)
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                                        cwd=r.ROOT, env=r.git_environment()).decode().split('\0')
        for name in filter(None, names):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(r.ROOT / name, target)
        (root / 'node_modules').symlink_to(r.ROOT / 'node_modules', target_is_directory=True)
        for manifest in [evidence, *(b['files']['evidence-version.json'] for b in packet['bundles'])]:
            for source in manifest['sources']:
                for obj in source.get('components', [source]):
                    key = obj['originalSha256']
                    raw = store.read(key)
                    r.require(len(raw) == obj['originalBytes'], 'Private migration original size mismatch')
                    target = root / 'work/rule-admission/cas/sha256' / key[:2] / key[2:]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists(): target.write_bytes(raw)
                    target.chmod(0o600)
        target = root / archive.relative_to(r.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, target)
        shutil.copy2(ledger, root / ledger.relative_to(r.ROOT))
        r.write(root / 'work/migration-evidence.json', evidence)
        real_gh = shutil.which('gh')
        shim = root / 'work/migration-bin/gh'
        shim.parent.mkdir()
        # Only new isolated comment IDs are fixture responses. All historical
        # real comments are fetched by the original CLI and original executors.
        shim.write_text('#!' + sys.executable + '\n' + f'''import json,os,sys
from pathlib import Path
comments=json.loads(Path({str(root / 'work/migration-comments.json')!r}).read_text())
key=sys.argv[2] if len(sys.argv)>2 and sys.argv[1]=='api' else ''
if key in comments: print(json.dumps(comments[key]))
else: os.execv({real_gh!r},[{real_gh!r},*sys.argv[1:]])
''')
        shim.chmod(0o700)
        env = {**r.git_environment(), 'PATH': str(shim.parent) + os.pathsep + os.environ['PATH']}
        child = subprocess.run([sys.executable, '-I', 'admission/v1/test_migration.py', '--child'],
                               cwd=root, env=env, capture_output=True, text=True)
        r.require(child.returncode == 0, 'Real retained-credential migration failed:\n' + child.stderr[-9000:])
        result = r.load(root / 'work/migration-report.json')
    r.require(before == {p: r.digest(p.read_bytes()) for p in (archive, ledger)}, 'Migration modified parent private material')
    r.require(protected_before == {p: r.digest((r.ROOT / p).read_bytes()) for p in protected},
              'Migration modified protected production files')
    return {**result, 'protectedFilesUnchanged': len(protected_before)}


def child():
    import batch
    import evidence as ev
    import identity
    import korean
    import publish
    import release
    packet = provenance.origin_metadata()
    original = deepcopy(r.load(r.PRIVATE / 'pending-identities.json'))
    assert [e['airportId'] for e in original['identities']] == IDS
    for e in original['identities']: provenance.origin_for(e, packet)
    evidence = r.load('work/migration-evidence.json')
    store = Store()
    comments = {}

    def git(*args):
        return subprocess.check_output(['git', '--no-replace-objects', *args], cwd=r.ROOT,
                                       env=r.git_environment(), text=True).strip()

    for key, value in [('user.name', 'keepraw'), ('user.email', '49091395+keepraw@users.noreply.github.com'), ('user.useConfigOnly', 'true')]:
        git('config', '--local', key, value)
    for kind in ('GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT'):
        assert git('var', kind).startswith('keepraw <49091395+keepraw@users.noreply.github.com> ')

    def freeze(message):
        manifest = r.fingerprint()
        r.write(r.PUBLIC / 'bindings.json', {'manifest': manifest, 'policies': {
            r.policy(k)['policyKey']: r.bindings(r.policy(k)) for k in ('identity', 'kr-code')}})
        git('add', '--all')  # Include new public release metadata; work/ and CAS stay ignored.
        git('commit', '--quiet', '--allow-empty', '-m', message)
        assert git('log', '-1', '--format=%an <%ae>%n%cn <%ce>').splitlines() == [
            'keepraw <49091395+keepraw@users.noreply.github.com>'] * 2
        return git('rev-parse', 'HEAD')

    generation = 0
    def grants_for_generation():
        nonlocal generation
        generation += 1
        grants = []
        for i, kind in enumerate(('identity', 'kr-code')):
            p = r.policy(kind)
            number = str(900000000000 + generation * 2 + i)
            url = 'https://github.com/keepraw/airport-history/issues/27#issuecomment-' + number
            approval = {'html_url': url, 'body': r.authority_text(p), 'created_at': '2026-10-30T00:00:00Z',
                'updated_at': '2026-10-30T00:00:00Z', 'principal': {'login': 'keepraw', 'id': 49091395}, 'kind': 'github-owner'}
            comments['repos/keepraw/airport-history/issues/comments/' + number] = {
                **{k: approval[k] for k in ('html_url', 'body', 'created_at', 'updated_at')},
                'issue_url': 'https://api.github.com/repos/keepraw/airport-history/issues/27',
                'user': {'login': 'keepraw', 'id': 49091395, 'type': 'User'}}
            grants.append({'policyKey': p['policyKey'], 'bindings': r.checked_bindings(p), 'approval': approval})
        r.write('work/migration-comments.json', comments)
        return {'formatVersion': 1, 'authorizations': grants}

    def retained():
        registry = r.load(r.PRIVATE / 'pending-identities.json')
        assert [e['airportId'] for e in registry['identities'][:2]] == IDS
        for old, new in zip(original['identities'], registry['identities']):
            assert provenance.extend_identity(old, new) == new
        return registry

    def candidate_plan(bundle):
        output = r.ROOT / ('work/plan-' + bundle.name)
        result = publish.plan(bundle, output)
        assert result['humanMergeRequired'] and not result['autoMerge'] and not result['simulation']
        return output

    def merge(bundle, prepared):
        # Preserve the same metadata release archive and CI routing as a real
        # reviewed candidate merge, including its historical authorization file.
        for name, value in r.load(prepared / 'changes.json').items():
            r.write(r.ROOT / name, value)
        for name in ('ci.yml', 'kr-admission.yml', 'rule-admission.yml'):
            shutil.copy2(prepared / 'ci.yml', r.ROOT / '.github/workflows' / name)
        freeze('test: simulate a reviewed data merge')
        korean._REPLAY_CACHE.clear()

    freeze('test: freeze migration executor one')
    grants = grants_for_generation()
    stages = []
    # Only the published-main and open-PR transports are isolated. Real origin
    # metadata, verify_old, historical executors, comments and CAS replay remain.
    with patch.object(r.legacy, 'require_published', side_effect=lambda *args: git('rev-parse', 'HEAD')), \
            patch.object(release, 'pending_from_github', return_value=[]):
        first = r.ROOT / 'work/migration-first'
        release.prepare(evidence, store, grants, '0.10.1', first)
        assert release.validate(first)['productionValidationPassed']
        first_plan = candidate_plan(first)
        initial = retained()
        assert all(e['revalidations'][-1]['kind'] == provenance.KIND for e in initial['identities'])
        stages.append('A: original archive/executor/live Owner and new isolated grant verified; UUIDs retained')
        merge(first, first_plan)
        assert release.prepare(evidence, store, grants, '0.10.2', r.ROOT / 'work/migration-noop1')['status'] == 'NO_CHANGES'
        retained()
        stages.append('B: merged RKSI/RKSS repeat returns NO_CHANGES')

        # Add two geographically separate synthetic Korean sites. The production
        # classifier, original reader, batch competition and allocator all run.
        catalog = r.load(r.PUBLIC / 'candidate-catalog.json')
        template = deepcopy(catalog['candidates'][0])
        by_source = {s['sourceId']: s for s in evidence['sources']}
        for n, code in enumerate(('RKZZ', 'RKZY')):
            row = deepcopy(template)
            row.update(candidateKey='synthetic-migration-' + code, observedCode=code,
                       aipName='SYNTHETIC ' + code, name='Synthetic migration ' + code,
                       arpDms=('360000N 1300000E' if n == 0 else '350000N 1300000E'))
            support = row['independent']
            support.update(facilityKey='https://www.airport.kr/synthetic-test-only/' + code,
                sourceId='synthetic-operator-' + code, addressTokens=['Synthetic Street ' + code],
                aipAddressTokens=['Synthetic Street ' + code], siteNameToken=row['name'])
            raw = ('SYNTHETIC TEST ONLY ' + code + ' ' + row['aipName'] + ' ' + row['arpDms'] + ' ' +
                   row['name'] + ' Synthetic Street ' + code).encode()
            def add_source(sid, url, data):
                evidence['sources'].append({'sourceId': sid, 'url': url, 'finalUrl': url,
                    'observedAt': '2026-10-30T00:00:00+00:00', 'originalSha256': store.put(data),
                    'originalBytes': len(data), 'kind': 'reobtained-official-evidence'})
            add_source(support['sourceId'], support['facilityKey'], raw)
            for edition, old_sid in list(row['editionSources'].items()):
                sid = 'synthetic-' + code + '-' + edition.replace('/', '-')
                row['editionSources'][edition] = sid
                add_source(sid, by_source[old_sid]['url'].replace('RKSI', code), raw)
            row['riskSourceIds'] = list(row['editionSources'].values())
            add_source('synthetic-risk-' + code,
                'https://aim.koca.go.kr/synthetic-test?sch_airport=' + code + '&sch_from_date=2025-04-01&sch_to_date=2025-06-01',
                b'{"Total":0,"DATA":[]}')
            catalog['candidates'].append(row)
        r.write(r.PUBLIC / 'candidate-catalog.json', catalog)
        freeze('test: add synthetic candidate evidence metadata')
        third = r.ROOT / 'work/migration-next-batch'
        release.prepare(evidence, store, grants, '0.10.2', third)
        assert release.validate(third)['productionValidationPassed']
        next_plan = candidate_plan(third)
        next_registry = retained()
        assert len(next_registry['identities']) == 4
        assert len({e['airportId'] for e in next_registry['identities']}) == 4
        assert all(e['revalidations'][:len(old['revalidations'])] == old['revalidations']
                   for old, e in zip(initial['identities'], next_registry['identities']))
        stages.append('C: changed inventory, batch allocation, candidate validation and publisher plan passed')
        merge(third, next_plan)
        assert release.prepare(evidence, store, grants, '0.10.3', r.ROOT / 'work/migration-noop2')['status'] == 'NO_CHANGES'
        assert [e['airportId'] for e in retained()['identities']] == [e['airportId'] for e in next_registry['identities']]
        stages.append('D: second merge repeat returns NO_CHANGES; all UUIDs retained')
        prior = retained()
        source = next(s for s in evidence['sources'] if s['sourceId'] == 'synthetic-operator-RKZZ')
        raw = store.read(source['originalSha256']) + b' Updated evidence observation.'
        source.update(originalSha256=store.put(raw), originalBytes=len(raw), observedAt='2026-10-31T00:00:00+00:00')
        assert release.prepare(evidence, store, grants, '0.10.3', r.ROOT / 'work/migration-evidence')['status'] == 'NO_CHANGES'
        after = retained()
        assert all(len(e['revalidations']) == len(old.get('revalidations', [])) + 1 for old, e in zip(prior['identities'], after['identities']))
        stages.append('E: new original/evidence fully replayed, old attestations retained')
        for version in (2, 3):
            source_code = r.ROOT / 'admission/v1/provenance.py'
            source_code.write_text(source_code.read_text() + '\n# Isolated synthetic executor generation ' + str(version) + '\n')
            freeze('test: freeze independent executor ' + str(version))
            old_grants = grants
            grants = grants_for_generation()
            try:
                release.prepare(evidence, store, old_grants, '0.10.3', r.ROOT / ('work/rejected-' + str(version)))
            except ValueError as error:
                assert 'binding mismatch' in str(error)
            else:
                raise AssertionError('Previous grant authorized a new executor')
            assert release.prepare(evidence, store, grants, '0.10.3', r.ROOT / ('work/migration-executor-' + str(version)))['status'] == 'NO_CHANGES'
            retained()
        # Revoke a historical isolated comment. Today's grant cannot replace it.
        key = next(iter(comments))
        comments[key]['body'] += ' REVOKED IN ISOLATED TEST'
        r.write('work/migration-comments.json', comments)
        try:
            release.prepare(evidence, store, grants, '0.10.3', r.ROOT / 'work/revoked-history')
        except (ValueError, subprocess.CalledProcessError):
            pass
        else:
            raise AssertionError('Current grant concealed a revoked historical grant')
        stages.append('F: three linked executor generations; historical grant revocation blocks current grant')
    r.write(r.ROOT / 'work/migration-report.json', {'testOnly': True, 'productionSuccess': False,
        'realOriginalCredentialsReplayed': True, 'historicalOwnerTransport': 'live-github-api',
        'newGrantTransport': 'isolated-api-fixture', 'stages': stages, 'preservedUUIDs': IDS,
        'publicPullRequestsCreated': 0})


class RetainedMigrationTests(unittest.TestCase):
    def test_A_through_F_real_retained_credentials(self):
        result = run_isolated()
        self.assertEqual(6, len(result['stages']))
        self.assertEqual(IDS, result['preservedUUIDs'])


if __name__ == '__main__':
    if sys.argv[1:] == ['--child']:
        child()
    else:
        unittest.main(verbosity=2)
