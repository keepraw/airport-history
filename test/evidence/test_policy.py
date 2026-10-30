"""Hard predicates and authorization boundary, using real locked candidates.

Authorized fixtures are in-memory test grants, never repository authorizations.
Independent private-original replay is a separate explicit acquisition check.
"""
from copy import deepcopy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
sys.path.insert(0, str(ROOT / 'scripts/reference'))
import policy_review as engine
import policy_gate as gate
import policy_executor as executor
import policy_originals as originals
import policy_report as report
from policy_originals import validate_offline
from admissions import validate_admission


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.saved_authority, self.saved_reader = gate.AUTHORITY, gate.read_owner_comment
        gate.AUTHORITY, gate.read_owner_comment = gate.PRODUCTION_AUTHORITY, gate.PRODUCTION_COMMENT_READER

    def tearDown(self):
        gate.AUTHORITY, gate.read_owner_comment = self.saved_authority, self.saved_reader

    @classmethod
    def setUpClass(cls):
        cls.inputs = engine.inputs()
        cls.decisions = engine.evaluate()

    def fixture(self):
        p, _, _, records, airports, _, sources, rivals = deepcopy(self.inputs)
        a = next(a for a in records.values() if a['code'] == 'VOKN')
        obs = engine.observations(a, sources)
        return a, airports[a['airportId']], obs, rivals[(a['scheme'], a['code'])], {
            'totalMatches': 1, 'possibleLocationCount': 1}, p, {'scopeScreened': True}

    def test_real_candidates_and_known_regressions(self):
        unpublished = [d for d in self.decisions if d['sample'] == 'unpublished']
        self.assertEqual(len(unpublished), 43)
        self.assertEqual({d['code'] for d in unpublished if d['risk'] == 'low'}, {'VEHO', 'VASD', 'VOKN'})
        self.assertEqual({d['code'] for d in unpublished if d['risk'] == 'medium'}, {'VOGA', 'VEDG'})
        for d in self.decisions:
            if d['code'] in {'LEMI', 'RMU', 'MJV', 'TAG', 'LYG', 'YBP'}:
                self.assertEqual(d['risk'], 'high')
            self.assertIsNone(d['reviewer'])
            self.assertIsNone(d['authorizationSource'])
        positive = [d for d in self.decisions if d['sample'] == 'published-positive']
        self.assertEqual(len(positive), 6)
        self.assertEqual(sum(d['risk'] == 'medium' for d in positive), 5)
        self.assertEqual(next(d for d in positive if d['code'] == 'LELC')['risk'], 'insufficient')

    def test_report_rebuild_after_draft_to_authorized_preserves_exact_grant(self):
        paths = [engine.DIRECTORY / name for name in
                 ('policy.json', 'authorizations.json', 'batch-authorizations.json')]
        before = {p: p.read_bytes() for p in paths}
        registered = engine.load(paths[1])
        self.assertEqual(len(registered['authorizations']), 1)
        real_load = report.load
        rendered = {}
        for status in ('draft', 'authorized'):
            policy = deepcopy(self.inputs[0]); policy['status'] = status
            registry = registered if status == 'authorized' else {'formatVersion': 1, 'authorizations': []}
            staged_load = lambda p: registry if p == paths[1] else real_load(p)
            with patch.object(report, 'inputs', return_value=(policy, *self.inputs[1:])), \
                 patch.object(report, 'load', side_effect=staged_load), \
                 patch.object(gate, 'load', side_effect=staged_load), \
                 patch.object(gate, 'AUTHORITY', self.saved_authority):
                rendered[status] = report.artifacts()
            text, _ = rendered[status]
            self.assertIn(f'当前状态 `{status}`', text)
            self.assertIn(f"有效 owner 政策授权 {len(registry['authorizations'])} 条，批次授权登记 0 条", text)
            self.assertEqual(rendered[status][1]['status'],
                             'authorized' if status == 'authorized' else 'proposed_not_authorized')
        authorized_text, _ = rendered['authorized']
        self.assertIn(registered['authorizations'][0]['authorizationSource'], authorized_text)
        self.assertNotIn('真实 policy.json 仍为 draft', authorized_text)
        self.assertNotIn('没有新增政策或批次授权', authorized_text)
        for key in ('authorizationText', 'policySha256', 'scopeSha256', 'executor'):
            self.assertEqual(rendered['draft'][1][key], rendered['authorized'][1][key])
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            shutil.copytree(engine.DIRECTORY / 'generated', directory / 'generated')
            with patch.object(report, 'DIRECTORY', directory):
                with patch.object(report, 'artifacts', return_value=rendered['draft']):
                    report.main('build'); report.main('validate')
                with patch.object(report, 'artifacts', return_value=rendered['authorized']):
                    with self.assertRaisesRegex(ValueError, 'Stale policy report/proposal'):
                        report.main('validate')
                    report.main('build'); report.main('validate')
                    first = {p.name: p.read_bytes() for p in (directory / 'generated').iterdir()}
                    report.main('build'); report.main('validate')
                    self.assertEqual(first, {p.name: p.read_bytes() for p in (directory / 'generated').iterdir()})
        self.assertEqual(before, {p: p.read_bytes() for p in paths})

    def test_report_authorized_state_requires_a_valid_unique_registry(self):
        policy = deepcopy(self.inputs[0]); policy['status'] = 'authorized'
        registry_path = engine.DIRECTORY / 'authorizations.json'
        registered = engine.load(registry_path)
        real_load = report.load
        for mutation in ('missing', 'duplicate', 'principal', 'text', 'executor'):
            registry = deepcopy(registered)
            if mutation == 'missing': registry['authorizations'] = []
            elif mutation == 'duplicate': registry['authorizations'] *= 2
            elif mutation == 'principal': registry['authorizations'][0]['authorizedBy']['githubUserId'] = -1
            elif mutation == 'text': registry['authorizations'][0]['authorizationText'] += ' broaden scope'
            else: registry['authorizations'][0]['executorSha256'] = '0'*64
            staged_load = lambda p: registry if p == registry_path else real_load(p)
            with self.subTest(mutation=mutation), \
                 patch.object(report, 'load', side_effect=staged_load), \
                 patch.object(gate, 'load', side_effect=staged_load), \
                 patch.object(gate, 'AUTHORITY', self.saved_authority), \
                 self.assertRaises(ValueError):
                report.lifecycle_state(policy)

    def test_report_counts_only_policy_bundle_facts_present_in_formal_data(self):
        policy = deepcopy(self.inputs[0]); policy['status'] = 'authorized'
        base = self.inputs[2]
        candidate = engine.proposed_dataset(self.decisions, verified=True)
        added = candidate['assignments'][-1]
        dossier = [{'recordId': added['assignmentId'], 'reviewMode': 'policy', 'reviewer': None}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / 'research/admissions' / candidate['dataVersion']
            engine.write_json(bundle / 'proposed-data.json', candidate)
            engine.write_json(bundle / 'dossier.json', dossier)
            receipt = {'policyId': policy['policyId'], 'policyVersion': policy['policyVersion'],
                       'reviewMode': 'policy', 'datasetSha256': engine.sha(candidate),
                       'dossierSha256': engine.sha(dossier)}
            engine.write_json(bundle / 'policy-receipt.json', receipt)
            with patch.object(report, 'ROOT', root), patch.object(gate, 'AUTHORITY', self.saved_authority):
                engine.write_json(root / 'data/airports.json', base)
                self.assertEqual(report.lifecycle_state(policy)[3], [])
                engine.write_json(root / 'data/airports.json', candidate)
                self.assertEqual(report.lifecycle_state(policy)[3], [candidate['dataVersion']])
                altered = deepcopy(candidate); altered['assignments'][-1]['note'] += ' changed'
                engine.write_json(root / 'data/airports.json', altered)
                self.assertEqual(report.lifecycle_state(policy)[3], [])
                receipt['dossierSha256'] = '0'*64
                engine.write_json(bundle / 'policy-receipt.json', receipt)
                with self.assertRaisesRegex(ValueError, 'Invalid recorded policy admission bundle'):
                    report.lifecycle_state(policy)

    def test_exact_local_window_and_boundary_limits(self):
        f = self.fixture()
        r = engine.classify(*f)
        self.assertEqual(r['risk'], 'low')
        self.assertEqual(r['window'], ['2026-04-17', '2026-07-09'])
        f[5]['parameters']['maximumGapDays'] = 84
        f[5]['parameters']['maximumWindowDays'] = 83
        self.assertEqual(engine.classify(*f)['risk'], 'low')
        f[5]['parameters']['maximumGapDays'] = 83
        self.assertEqual(engine.classify(*f)['risk'], 'medium')

    def test_mandatory_escalations_and_missing_conflict_screen(self):
        for key in self.inputs[0]['mandatoryEscalation']:
            f = self.fixture(); f[-1][key] = True
            self.assertEqual(engine.classify(*f)['risk'], 'high', key)
        f = self.fixture(); f[-1].clear()
        self.assertIn('unknown_conflict', engine.classify(*f)['reasons'])
        f = self.fixture(); f[3].add('different-physical-site')
        self.assertEqual(engine.classify(*f)['risk'], 'high')
        f = self.fixture(); f[4]['possibleLocationCount'] = 2
        self.assertEqual(engine.classify(*f)['risk'], 'high')

    def test_originals_issuers_and_identity(self):
        f = self.fixture()
        self.assertEqual(engine.classify(*f)['publisherCount'], 1)
        f[2][1]['originalSha256'] = f[2][0]['originalSha256']
        self.assertEqual(engine.classify(*f)['risk'], 'medium')
        for key in ('publicationDate', 'editionAnchorSourceId', 'originalVerified'):
            f = self.fixture(); f[2][0][key] = None
            self.assertNotEqual(engine.classify(*f)['risk'], 'low')
        f = self.fixture(); f[1]['coordinates']['value']['latitude'] += .01
        self.assertEqual(engine.classify(*f)['risk'], 'high')
        f = self.fixture(); f[2][0]['spans'][0]['quote'] = 'Airport opened on 16 April 2026'
        self.assertNotEqual(engine.classify(*f)['risk'], 'low')

    def test_same_edition_alias_cannot_hide_different_originals(self):
        obs = self.fixture()[2]
        alias = deepcopy(obs[0]); alias['sourceId'] += '-alias'
        self.assertEqual(len(engine.deduplicate_observations([*obs, alias])), 2)
        alias['originalSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'Conflicting originals'):
            engine.deduplicate_observations([*obs, alias])

    def test_policy_schema_and_hash_fail_closed(self):
        for mutation in ('hash', 'version', 'status', 'threshold', 'unknown', 'unsafe'):
            p = deepcopy(self.inputs[0])
            if mutation == 'hash': p['policySha256'] = '0'*64
            elif mutation == 'version': p['engineVersion'] = 'future'
            elif mutation == 'status': p['status'] = 'auto-approved'
            elif mutation == 'threshold': p['parameters']['minimumObservations'] = 1
            elif mutation == 'unknown': p['confidence'] = .99
            else: p['parameters']['unknownOuterBoundsRequired'] = False
            if mutation != 'hash': p['policySha256'] = engine.policy_hash(p)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): engine.validate_policy(p)
        p = deepcopy(self.inputs[0]); p['status'] = 'disabled'
        engine.validate_policy(p)
        with self.assertRaises(ValueError): gate.authorization(p)

    def test_draft_cannot_emit_admission_and_cannot_impersonate_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proposal'
            draft = deepcopy(self.inputs[0]); draft['status'] = 'draft'
            with patch.object(gate, 'inputs', return_value=(draft, *self.inputs[1:])):
                with self.assertRaisesRegex(ValueError, 'not authorized'): gate.admit(output)
            self.assertFalse(output.exists())
        data = engine.proposed_dataset(self.decisions, verified=True)
        batches, dossier = gate.packet(self.decisions, data)
        with self.assertRaisesRegex(ValueError, 'valid policy authorization'):
            validate_admission(self.inputs[2], data, batches, dossier)
        dossier[0]['reviewer'] = 'keepraw'
        with self.assertRaises(ValueError): validate_admission(self.inputs[2], data, batches, dossier)

    def test_authorization_and_exact_receipt_through_original_gate(self):
        policy = deepcopy(self.inputs[0]); policy['status'] = 'authorized'
        text = gate.grant_text(policy)
        grant = {'policyId': policy['policyId'], 'policyVersion': policy['policyVersion'],
            'executorSha256': executor.fingerprint()['executorSha256'], 'authorityKind': 'github-owner',
            'policySha256': policy['policySha256'], 'scopeSha256': engine.sha(policy['scope']),
            'state': 'authorized', 'authorizedBy': {'login': 'keepraw', 'githubUserId': 49091395},
            'authorizationText': text, 'authorizationTextSha256': hashlib.sha256(text.encode()).hexdigest(),
            'authorizationSource': 'https://github.com/keepraw/airport-history/issues/1#issuecomment-1',
            'approvedOn': '2026-10-29', 'recordedBy': 'policy-activation-cli'}
        real_load = gate.load
        with patch.object(gate, 'load', side_effect=lambda p: {'formatVersion': 1, 'authorizations': [grant]}
                          if p.name == 'authorizations.json' else real_load(p)):
            self.assertEqual(gate.authorization(policy), grant)
            for key, value in [('githubUserId', 123), ('login', 'Codex')]:
                old = grant['authorizedBy'][key]; grant['authorizedBy'][key] = value
                with self.assertRaises(ValueError): gate.authorization(policy)
                grant['authorizedBy'][key] = old
            data = engine.proposed_dataset(self.decisions, verified=True)
            batches, dossier = gate.packet(self.decisions, data)
            proof = engine.load(engine.DIRECTORY / 'verification/low.json')
            context = gate.receipt(self.decisions, data, batches, dossier, grant, original_verification=proof)
            with patch.object(gate, 'inputs', return_value=(policy, *self.inputs[1:])), patch.object(gate, 'replay_originals'):
                self.assertEqual(validate_admission(self.inputs[2], data, batches, dossier, policy_context=context),
                                 {'airports': 3, 'assignments': 3, 'names': 0, 'sources': 6})
                for what in ('receipt', 'window', 'source', 'existing', 'extra', 'reviewer'):
                    d, c, ds = deepcopy(data), deepcopy(context), deepcopy(dossier)
                    if what == 'receipt': c['policySha256'] = '0'*64
                    elif what == 'window': d['assignments'][-1]['validFrom']['latest'] = '2026-04-16'
                    elif what == 'source': d['sources'][-1]['verificationStatus'] = 'pending'
                    elif what == 'existing': d['airports'][0]['name']['value'] += ' changed'
                    elif what == 'extra': d['assignments'].append(deepcopy(d['assignments'][-1]))
                    else: ds[0]['reviewer'] = 'keepraw'
                    with self.subTest(what=what), self.assertRaises(ValueError):
                        validate_admission(self.inputs[2], d, batches, ds, policy_context=c)

    def test_fixed_batches_and_idempotent_outputs(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            engine.build(Path(a)); engine.build(Path(b))
            self.assertEqual({p.name: p.read_bytes() for p in Path(a).glob('*.json')},
                             {p.name: p.read_bytes() for p in Path(b).glob('*.json')})
            batches = engine.load(Path(a) / 'medium-batches.json')
            self.assertEqual(len(batches), 1)
            batch = batches[0]; expected = batch.pop('batchSha256')
            self.assertEqual(engine.sha(batch), expected)
            batch['records'].append(deepcopy(batch['records'][0]))
            self.assertNotEqual(engine.sha(batch), expected)

    def test_fixed_medium_batch_acceptance_uses_exact_owner_grant(self):
        batch = engine.fixed_batches(self.decisions, 'medium')[0]
        with self.assertRaises(ValueError): gate.batch_authorization(batch)
        text = gate.batch_grant_text(batch)
        grant = {'state': 'authorized', 'batchSha256': batch['batchSha256'],
                 'executorSha256': executor.fingerprint()['executorSha256'], 'authorityKind': 'github-owner',
                 'authorizedBy': {'login': 'keepraw', 'githubUserId': 49091395},
                 'authorizationText': text, 'authorizationTextSha256': hashlib.sha256(text.encode()).hexdigest(),
                 'authorizationSource': 'https://github.com/keepraw/airport-history/issues/1#issuecomment-1',
                 'approvedOn': '2026-10-30', 'recordedBy': 'policy-activation-cli'}
        real_load = gate.load
        with patch.object(gate, 'load', side_effect=lambda p: {'formatVersion': 1, 'authorizations': [grant]}
                          if p.name == 'batch-authorizations.json' else real_load(p)):
            self.assertEqual(gate.batch_authorization(batch), grant)
            ds = batch['records']
            data = engine.proposed_dataset(ds, verified=True, risks=('medium',), reviewed_on=grant['approvedOn'])
            batches, dossier = gate.packet(ds, data, mode='batch', reviewed_on=grant['approvedOn'])
            proof = engine.load(engine.DIRECTORY / 'verification/medium.json')
            context = gate.receipt(ds, data, batches, dossier, grant, mode='batch', batch_sha=batch['batchSha256'], original_verification=proof)
            with patch.object(gate, 'replay_originals'):
                self.assertEqual(validate_admission(self.inputs[2], data, batches, dossier, policy_context=context),
                                 {'airports': 2, 'assignments': 2, 'names': 0, 'sources': 4})
                changed = deepcopy(context); changed['batchSha256'] = '0'*64
                with self.assertRaises(ValueError):
                    validate_admission(self.inputs[2], data, batches, dossier, policy_context=changed)
            enlarged = deepcopy(batch); enlarged['records'].append(deepcopy(batch['records'][0]))
            enlarged['batchSha256'] = engine.sha({k: v for k, v in enlarged.items() if k != 'batchSha256'})
            with self.assertRaises(ValueError): gate.batch_authorization(enlarged)

    def test_activation_requires_remote_exact_owner_and_no_writes_on_rejection(self):
        policy = self.inputs[0]
        draft = deepcopy(policy); draft['status'] = 'draft'
        self.enterContext(patch.object(gate, 'inputs', return_value=(draft, *self.inputs[1:])))
        real_load = gate.load
        self.enterContext(patch.object(gate, 'load', side_effect=lambda p:
            {'formatVersion': 1, 'authorizations': []} if p.name == 'authorizations.json' else real_load(p)))
        url = 'https://github.com/keepraw/airport-history/issues/1#issuecomment-1'
        comment = {'html_url': url, 'user': {'login': 'keepraw', 'id': 49091395},
                   'body': gate.grant_text(policy), 'created_at': '2026-10-29T00:00:00Z'}
        for mutation in ('actor', 'text', 'url'):
            c = deepcopy(comment)
            if mutation == 'actor': c['user']['id'] = 1
            elif mutation == 'text': c['body'] += ' broaden scope'
            else: c['html_url'] = url.replace('/issues/1', '/issues/2')
            with patch.object(gate.subprocess, 'check_output', return_value=json.dumps(c)), patch.object(gate, 'write_json') as write:
                with self.assertRaises(ValueError): gate.activate(url)
                write.assert_not_called()
        with patch.object(gate.subprocess, 'check_output', return_value=json.dumps(comment)) as remote, patch.object(gate, 'write_json') as write:
            gate.activate(url)
            self.assertEqual(write.call_count, 2)
            self.assertEqual(remote.call_args.args[0], ['gh', 'api', 'repos/keepraw/airport-history/issues/comments/1'])

    def test_detached_source_hash_and_missing_original_are_rejected(self):
        source = engine.load(engine.DIRECTORY / 'source-lock.json')['sources'][0]
        with self.assertRaisesRegex(ValueError, 'Changed pinned input'):
            engine.pinned('research/policy/' + source['excerptPath'], '0'*64)
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
            corrupt = Path(tmp) / 'changed-original.html'; corrupt.write_bytes(b'corrupted original')
            altered = {**source, 'privateOriginalPath': str(corrupt.relative_to(ROOT))}
            with patch.object(originals, 'required_sources', return_value=[altered]):
                with self.assertRaisesRegex(ValueError, 'Original replay hash mismatch'):
                    originals.verify_originals([])

    def test_candidate_cannot_declare_itself_the_published_baseline(self):
        old = deepcopy(self.inputs[1]['baseline'])
        engine.validate_baseline(old)
        current_candidate = engine.proposed_dataset(self.decisions, verified=True)
        old.update(dataVersion=current_candidate['dataVersion'],
                   path=f"test/curated-{current_candidate['dataVersion']}.json", sha256=engine.sha(current_candidate))
        with self.assertRaisesRegex(ValueError, 'Baseline differs from published commit'):
            engine.validate_baseline(old)

    def test_executor_bytes_change_requires_new_authorization(self):
        grant = {'executorSha256': executor.fingerprint()['executorSha256']}
        executor.require_binding(grant)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for p in executor.FILES:
                target = root / p; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / p).read_bytes())
            # Same policy JSON/version; changed decision implementation must still invalidate the grant.
            target = root / 'scripts/evidence/policy_review.py'
            target.write_text(target.read_text().replace("risk = 'high' if high", "risk = 'low' if high"))
            with patch.object(executor, 'ROOT', root):
                self.assertNotEqual(executor.fingerprint()['executorSha256'], grant['executorSha256'])
                with self.assertRaisesRegex(ValueError, 'new explicit authorization'): executor.require_binding(grant)
        with self.assertRaises(ValueError): executor.require_binding({})

    def test_offline_receipt_replay_is_explicit_and_bound_to_all_inputs(self):
        selected = [d for d in self.decisions if d['sample'] == 'unpublished' and d['risk'] == 'low']
        proof = engine.load(engine.DIRECTORY / 'verification/low.json')
        result = validate_offline(proof, selected)
        self.assertFalse(result['originalBytesObtainedHere'])
        for key in ('executorSha256', 'inputSha256', 'baselineSha256'):
            changed = deepcopy(proof); changed[key] = '0'*64
            with self.assertRaises(ValueError): validate_offline(changed, selected)
        changed = deepcopy(proof); changed['sources'].pop()
        with self.assertRaises(ValueError): validate_offline(changed, selected)
        with self.assertRaises(ValueError): validate_offline(None, selected)


if __name__ == '__main__': unittest.main()
