"""Isolated credential-transition unit tests; no production credential is emitted."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import provenance as p
import identity
from batch import inventory
from evidence import Store


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.packet = p.origin_metadata()
        self.registry = deepcopy(self.packet['originPendingRegistry'])
        files = self.packet['bundles'][1]['files']
        self.candidates, self.evidence = files['candidates.json'], files['evidence-version.json']
        self.decisions = files['receipt.json']['decisions']
        self.competition = inventory(files['baseline.json'], files['baseline-identities.json'])
        self.policy = r.policy('identity')
        # An explicit unit-only binding, never a computed/final production binding.
        # This lets transition logic run before production bindings are frozen.
        fixture_binding = {**r.bindings(self.policy), 'executorSha256': 'f' * 64}
        for module in (r, p, identity):
            patched = patch.object(module, 'checked_bindings', return_value=fixture_binding)
            patched.start(); self.addCleanup(patched.stop)
        self.approval = {'html_url': 'test-fixture://provenance/current', 'body': r.authority_text(self.policy),
                         'principal': {'login': 'isolated-provenance-test', 'id': 0},
                         'kind': 'isolated-test-authority', 'created_at': '2026-10-30T00:00:00Z',
                         'updated_at': '2026-10-30T00:00:00Z'}
        self.grants = {'formatVersion': 1, 'authorizations': [{'policyKey': self.policy['policyKey'],
            'bindings': r.checked_bindings(self.policy), 'approval': self.approval}]}
        self.reader = patch.object(r.legacy, 'read_owner_comment', return_value=self.approval)
        self.reader.start(); self.addCleanup(self.reader.stop)
        self.old = patch.object(p, 'verify_old', return_value={'testOnly': True})
        self.old_call = self.old.start(); self.addCleanup(self.old.stop)
        self.classifier = patch.object(identity, 'classify_batch', return_value=deepcopy(self.decisions))
        self.classify_call = self.classifier.start(); self.addCleanup(self.classifier.stop)

    def run_transition(self, registry=None, **kwargs):
        return p.revalidate_registry(registry or self.registry, self.candidates, self.policy,
            self.grants, self.evidence, None, self.competition, **kwargs)

    def test_current_attestation_preserves_all_original_fields_and_is_idempotent(self):
        before = r.canonical(self.registry)
        result = self.run_transition()
        for original, renewed in zip(self.registry['identities'], result['identities']):
            self.assertEqual(original, {**renewed, 'revalidations': renewed['revalidations'][:-1]})
            proof = renewed['revalidations'][-1]
            self.assertEqual(p.KIND, proof['kind'])
            self.assertEqual(r.checked_bindings(self.policy), proof['bindings'])
            self.assertEqual(r.sha(self.grants['authorizations'][0]), proof['authorizationSha256'])
        self.assertEqual(result, self.run_transition(result))
        self.assertEqual(result, self.run_transition(result, append=False))
        self.assertEqual(before, r.canonical(self.registry))

    def test_old_grants_cannot_issue_new_attestation(self):
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            p.revalidate_registry(self.registry, self.candidates, self.policy,
                self.packet['bundles'][0]['files']['authorizations.json'], self.evidence, None, self.competition)
        self.old_call.assert_not_called()

    def test_old_origin_failure_blocks_before_uuid_allocation(self):
        self.old_call.side_effect = ValueError('Old live Owner grant or original failed')
        with patch.object(identity.uuid, 'uuid4') as generate, self.assertRaises(ValueError):
            identity.allocate(self.candidates, self.policy, self.grants, self.evidence, None,
                              self.competition, self.registry)
        generate.assert_not_called()
        self.classify_call.assert_called()

    def test_uuid_binding_original_hash_and_history_tampering_reject(self):
        for field in ('airportId', 'siteKey', 'coordinates', 'authorizationSha256', 'evidenceVersionSha256', 'bindings', 'revalidations'):
            registry = deepcopy(self.registry)
            registry['identities'][0][field] = [] if field == 'revalidations' else {'tampered': True} if field in ('coordinates', 'bindings') else 'tampered'
            with self.subTest(field=field), self.assertRaises((ValueError, KeyError, TypeError)):
                self.run_transition(registry)

    def test_manual_missing_or_changed_current_site_is_blocked(self):
        for field, value in [('classification', 'MANUAL_REVIEW'), ('classification', 'INSUFFICIENT_EVIDENCE'),
                             ('siteKey', 'different-site'), ('coordinates', {'latitude': 0, 'longitude': 0})]:
            decisions = deepcopy(self.decisions); decisions[0][field] = value
            self.classify_call.return_value = decisions
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.run_transition()

    def test_missing_candidate_never_remints_the_retained_uuid(self):
        with patch.object(identity.uuid, 'uuid4') as generate, self.assertRaises(ValueError):
            p.revalidate_registry(self.registry, self.candidates[1:], self.policy, self.grants,
                                  self.evidence, None, self.competition)
        generate.assert_not_called()

    def test_lost_pending_ledger_never_makes_known_sites_new(self):
        with patch.object(identity.uuid, 'uuid4') as generate, self.assertRaisesRegex(ValueError, 'never remint'):
            identity.allocate(self.candidates, self.policy, self.grants, self.evidence, None,
                              self.competition, {'formatVersion': 1, 'identities': []})
        generate.assert_not_called()

    def test_missing_or_forged_current_attestation_rejects_offline_metadata(self):
        with self.assertRaisesRegex(ValueError, 'Missing current provenance'):
            self.run_transition(append=False, metadata_decisions=self.decisions)
        result = self.run_transition()
        result['identities'][0]['revalidations'][-1]['originArchiveSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'changed provenance'):
            self.run_transition(result, append=False, metadata_decisions=self.decisions)
        with self.assertRaisesRegex(ValueError, 'cannot issue'):
            self.run_transition(metadata_decisions=self.decisions)

    def test_changed_origin_envelope_is_detected(self):
        packet = deepcopy(self.packet); packet['bundles'][0]['files']['receipt.json']['testOnly'] = True
        original_load = p.load
        with patch.object(p, 'load', side_effect=lambda path: packet if path == p.ANCHOR else original_load(path)):
            with self.assertRaisesRegex(ValueError, 'Detached origin bundle'):
                p.origin_metadata()

    def test_review_issues_no_current_attestation_or_formal_identity(self):
        before = r.canonical(self.registry)
        report = p.review(self.registry, self.evidence, None)
        self.assertEqual(0, report['newAttestationsIssued'])
        self.assertEqual(0, report['formalIdentitiesAdded'])
        self.assertFalse(report['newOwnerAuthorizationVerified'])
        self.assertEqual(before, r.canonical(self.registry))


class RecoveryBoundaryTests(unittest.TestCase):
    def setUp(self):
        r.PRIVATE.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=r.PRIVATE)
        self.addCleanup(self.tmp.cleanup)
        self.private = Path(self.tmp.name)

    def test_missing_or_changed_archive_cannot_use_an_offline_receipt(self):
        packet = p.origin_metadata()
        with patch.object(p, 'PRIVATE', self.private), self.assertRaises(FileNotFoundError):
            p.verify_old(packet, Store())
        path = self.private / 'provenance' / (packet['recoveryArchiveSha256'] + '.tar.gz')
        path.parent.mkdir(); path.write_bytes(b'changed archive')
        with patch.object(p, 'PRIVATE', self.private), self.assertRaisesRegex(ValueError, 'archive changed'):
            p.verify_old(packet, Store())

    def test_corrupt_component_rejects_even_with_matching_whole_archive_digest(self):
        key = hashlib.sha256(b'original').hexdigest()
        manifest = {'sources': [{'originalSha256': key, 'originalBytes': 8}]}
        packet = {'bundles': [{'files': {'evidence-version.json': manifest}}],
                  'originPendingRegistry': {'identities': []}, 'archiveBundlePrefix': 'bundle/',
                  'archivePendingPath': 'pending.json'}
        path = self.private / 'fixture.tar.gz'
        with tarfile.open(path, 'w:gz') as tar:
            for name, raw in [('pending.json', b'{"identities":[]}'), ('bundle/evidence-version.json', json.dumps(manifest).encode()),
                              ('work/rule-admission/cas/sha256/' + key[:2] + '/' + key[2:], b'mutated!')]:
                member = tarfile.TarInfo(name); member.size = len(raw); tar.addfile(member, io.BytesIO(raw))
        packet['recoveryArchiveSha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        dest = self.private / 'provenance' / (packet['recoveryArchiveSha256'] + '.tar.gz')
        dest.parent.mkdir(); path.rename(dest)
        with patch.object(p, 'PRIVATE', self.private), self.assertRaisesRegex(ValueError, 'Corrupt recovery original'):
            p.verify_old(packet, Store())


if __name__ == '__main__':
    unittest.main(verbosity=2)
