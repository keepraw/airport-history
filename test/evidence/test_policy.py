"""Hard predicates and authorization boundary, using real locked candidates.

Authorized fixtures are in-memory test grants, never repository authorizations.
Independent private-original replay is a separate explicit acquisition check.
"""
from copy import deepcopy
import hashlib
import json
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
from admissions import validate_admission


class PolicyTests(unittest.TestCase):
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

    def test_policy_schema_and_hash_fail_closed(self):
        for mutation in ('hash', 'version', 'status', 'threshold', 'unknown', 'unsafe'):
            p = deepcopy(self.inputs[0])
            if mutation == 'hash': p['policySha256'] = '0'*64
            elif mutation == 'version': p['engineVersion'] = 'future'
            elif mutation == 'status': p['status'] = 'auto-approved'
            elif mutation == 'threshold': p['parameters']['minimumObservations'] = 1
            elif mutation == 'unknown': p['confidence'] = .99
            else: p['parameters']['unknownOuterBoundsRequired'] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): engine.validate_policy(p)
        p = deepcopy(self.inputs[0]); p['status'] = 'disabled'
        engine.validate_policy(p)
        with self.assertRaises(ValueError): gate.authorization(p)

    def test_draft_cannot_emit_admission_and_cannot_impersonate_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proposal'
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
            context = gate.receipt(self.decisions, data, batches, dossier, grant)
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
            context = gate.receipt(ds, data, batches, dossier, grant, mode='batch', batch_sha=batch['batchSha256'])
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
        with patch.object(engine, 'digest', return_value='0'*64):
            with self.assertRaises(ValueError): engine.replay_originals()


if __name__ == '__main__': unittest.main()
