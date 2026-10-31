"""Security boundaries, general batches, evidence versioning and real E2E tests."""
from copy import deepcopy
import datetime as dt
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as r
import identity as identity
import evidence as evidence
import batch as batch
import release as release
import rehearse as rehearsal


def reader(url, text):
    return {'html_url': url, 'body': text, 'created_at': '2026-10-30T00:00:00Z',
            'updated_at': '2026-10-30T00:00:00Z', 'principal': {'login': 'isolated-tests', 'id': 0}, 'kind': 'isolated-test-authority'}


class RuleEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (r.ROOT / 'work').mkdir(exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=r.ROOT / 'work')
        cls.root = Path(cls.tmp.name)
        cls.packet = rehearsal.fixture(cls.root)
        cls.store = evidence.Store(cls.root / 'work/rule-admission/cas')
        cls.base = r.load(r.ROOT / 'test/curated-0.10.0.json')
        cls.registry = {'formatVersion': 1, 'identities': []}
        cls.inventory = batch.inventory(cls.base, cls.registry)
        cls.candidates = batch.discover(cls.inventory)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.ip, self.cp = r.policy('identity'), r.policy('kr-code')
        self.grants = {'formatVersion': 1, 'authorizations': [
            {'policyKey': p['policyKey'], 'bindings': r.checked_bindings(p),
             'approval': reader('test-fixture://rule/' + p['policyKey'], r.authority_text(p))}
            for p in (self.ip, self.cp)]}
        self.reader = patch.object(r.legacy, 'read_owner_comment', side_effect=reader)
        self.reader.start()
        self.risk = patch.object(identity, 'risk_screen', return_value=[])
        self.risk.start()
        self.addCleanup(self.reader.stop)
        self.addCleanup(self.risk.stop)

    def classify(self, candidate=None, inventory=None, packet=None, policy=None):
        return identity.classify(candidate or self.candidates[0], policy or self.ip,
            packet or self.packet, self.store, inventory if inventory is not None else self.inventory)

    def allocate(self, candidates=None, registry=None, grants=None):
        return identity.allocate(candidates or self.candidates, self.ip,
            grants if grants is not None else self.grants, self.packet, self.store, self.inventory,
            registry if registry is not None else self.registry)

    def test_real_candidate_shapes_have_no_name_allowlist_and_three_states(self):
        self.assertIsNone(self.ip['scope']['airportAllowlist'])
        self.assertNotIn('RKSI', r.canonical(self.ip).decode())
        self.assertEqual([identity.AUTO] * 2, [self.classify(c)['classification'] for c in self.candidates])
        self.assertEqual({'AUTO_ELIGIBLE', 'MANUAL_REVIEW', 'INSUFFICIENT_EVIDENCE'}, {identity.AUTO, identity.MANUAL, identity.INSUFFICIENT})

    def test_missing_identity_grant_mints_no_uuid(self):
        with patch.object(identity.uuid, 'uuid4') as generate, self.assertRaisesRegex(ValueError, 'Owner rule'):
            self.allocate(grants={'formatVersion': 1, 'authorizations': []})
        generate.assert_not_called()

    def test_indian_or_legacy_korean_grant_never_authorizes_identity(self):
        for key in ('official-aip-bounded-icao@1.0.0', 'kr-molit-bounded-icao@1.0.0'):
            grants = deepcopy(self.grants)
            grants['authorizations'][0]['policyKey'] = key
            with self.assertRaisesRegex(ValueError, 'Owner rule'):
                self.allocate(grants=grants)

    def test_missing_code_grant_stops_combined_pipeline_before_uuid(self):
        grants = deepcopy(self.grants)
        grants['authorizations'] = grants['authorizations'][:1]
        with patch.object(identity.uuid, 'uuid4') as generate, self.assertRaisesRegex(ValueError, 'Owner rule'):
            release.prepare(self.packet, self.store, grants, '0.10.1', self.root / 'must-not-exist')
        generate.assert_not_called()
        self.assertFalse((self.root / 'must-not-exist').exists())

    def test_policy_scope_and_executor_mutation_invalidates_grant(self):
        for field in ('policy', 'scope', 'executor'):
            p = deepcopy(self.ip)
            if field == 'policy': p['rules']['maximumObservationGapDays'] += 1
            elif field == 'scope': p['scope']['countries'].append('JP')
            with self.subTest(field=field):
                if field == 'executor':
                    altered = r.fingerprint()
                    altered['executorSha256'] = '0' * 64
                    with patch.object(r, 'fingerprint', return_value=altered), self.assertRaises(ValueError):
                        r.authorize(p, self.grants)
                else:
                    with self.assertRaises(ValueError): r.authorize(p, self.grants)

    def test_missing_original_and_mutated_original_are_fail_closed(self):
        packet = deepcopy(self.packet)
        packet['sources'] = [s for s in packet['sources'] if s['sourceId'] != self.candidates[0]['observations'][0]['sourceId']]
        self.assertEqual(identity.INSUFFICIENT, self.classify(packet=packet)['classification'])
        entry = next(s for s in self.packet['sources'] if s['sourceId'] == self.candidates[0]['observations'][0]['sourceId'])
        path = self.store.path(entry['originalSha256'])
        raw = path.read_bytes()
        try:
            path.write_bytes(raw + b'changed')
            self.assertEqual(identity.INSUFFICIENT, self.classify()['classification'])
        finally:
            path.write_bytes(raw)

    def test_duplicate_run_reuses_uuid_and_distinct_airports_remain_distinct(self):
        first = self.allocate()
        second = self.allocate(registry=first['registry'])
        self.assertEqual(2, len(first['registry']['identities']))
        self.assertEqual([r['airportId'] for r in first['registry']['identities']], [r['airportId'] for r in second['registry']['identities']])
        self.assertEqual(2, len({r['airportId'] for r in second['registry']['identities']}))

    def test_same_code_at_different_sites_is_manual_and_not_merged(self):
        row = deepcopy(self.candidates[1])
        row['observedCode'] = self.candidates[0]['observedCode']
        with patch.object(identity.uuid, 'uuid4') as generate:
            result = self.allocate([self.candidates[0], row])
        self.assertEqual([identity.MANUAL] * 2, [r['classification'] for r in result['decisions']])
        self.assertFalse(result['registry']['identities'])
        generate.assert_not_called()

    def test_relocation_and_competing_formal_pending_historical_sites_are_manual(self):
        item = deepcopy(self.candidates[0])
        item['observations'][1]['arpDms'] = '372747N 1262621E'
        self.assertEqual(identity.MANUAL, self.classify(item)['classification'])
        for status in ('formal', 'pending', 'historical'):
            item = deepcopy(self.candidates[0])
            competition = [*self.inventory, {'inventoryId': 'synthetic-competing-site', 'coordinates': identity.arp(item['observations'][0]['arpDms']), 'siteKey': None, 'codes': [], 'status': status}]
            item['competitionInventorySha256'] = r.sha(competition)
            self.assertEqual(identity.MANUAL, self.classify(item, competition)['classification'])

    def test_unknown_or_excessive_observation_gap_is_insufficient(self):
        item = deepcopy(self.candidates[0])
        item['observations'][1]['effectiveUtc'] = '2025-06-14T16:00:00+00:00'
        self.assertEqual(identity.INSUFFICIENT, self.classify(item)['classification'])

    def test_index_omission_cannot_hide_intermediate_revision(self):
        item = deepcopy(self.candidates[0])
        item['editionControl']['expectedIntermediateEditions'] = []
        item['editionControl']['intermediateEditions'] = []
        self.assertEqual(identity.INSUFFICIENT, self.classify(item)['classification'])

    def test_same_upstream_is_not_independent(self):
        p = deepcopy(self.ip)
        p['independentSourceProfiles'][0]['upstreamFamilies'].append('KR-MOLIT-AIP')
        self.assertEqual(identity.INSUFFICIENT, self.classify(policy=p)['classification'])

    def test_noaa_or_name_code_match_cannot_replace_operator_site_source(self):
        item = deepcopy(self.candidates[0])
        item['independent']['sourceId'] = 'noaa-isd'
        self.assertEqual(identity.INSUFFICIENT, self.classify(item)['classification'])

    def test_exception_queue_deduplicates_daily_task_and_keeps_revisions(self):
        result = self.classify(packet={'sources': []})
        queue = identity.queue([result])
        self.assertEqual(queue, identity.queue([result], queue))
        changed = {**result, 'evidenceVersionSha256': 'new-observation'}
        updated = identity.queue([changed], queue)
        self.assertEqual(1, len(updated))
        self.assertEqual(2, len(updated[0]['revisions']))

    def test_evidence_versions_and_content_addresses_are_append_only(self):
        key = self.store.put(b'synthetic-byte-version-one')
        second = self.store.put(b'synthetic-byte-version-two')
        self.assertNotEqual(key, second)
        self.assertEqual(b'synthetic-byte-version-one', self.store.read(key))
        first_key, first = evidence.save_version({'snapshot': 1}, self.root / 'versions')
        next_key, second_path = evidence.save_version({'snapshot': 2, 'parent': first_key}, self.root / 'versions')
        self.assertNotEqual(first_key, next_key)
        self.assertEqual({'snapshot': 1}, r.load(first))
        self.assertTrue(second_path.exists())

    def test_unknown_policy_and_test_transport_reject_in_production_reader(self):
        with self.assertRaisesRegex(ValueError, 'default deny'): r.policy('unknown')
        self.reader.stop()
        with self.assertRaisesRegex(ValueError, 'issue-comment URL'): r.authorize(self.ip, self.grants)

    def test_synthetic_evidence_version_rejected_by_production_original_replay(self):
        with self.assertRaisesRegex(ValueError, 'Synthetic originals'):
            evidence.replay(self.packet, self.store)

    def test_pending_github_batch_registry_is_reused_across_workers(self):
        ledger = self.allocate()['registry']
        prs = [{'head': {'ref': 'data/rule-admission-synthetic-test', 'sha': 'a' * 40,
                         'repo': {'full_name': 'keepraw/airport-history'}}},
               {'head': {'ref': 'unrelated-branch', 'sha': 'b' * 40, 'repo': {'full_name': 'keepraw/airport-history'}}}]
        encoded = {'encoding': 'base64', 'type': 'file', 'content': base64.b64encode(r.canonical(ledger)).decode()}
        with patch.object(r.legacy, 'github', side_effect=[prs, encoded]) as api:
            recovered = release.pending_from_github()
        self.assertEqual(ledger['identities'], recovered)
        self.assertEqual(2, api.call_count)

    def test_adding_unrelated_country_file_does_not_change_executor(self):
        before = r.fingerprint()
        path = self.root / 'third-country.py'
        path.write_text('synthetic country module, outside the explicit manifest')
        self.assertEqual(before, r.fingerprint())

    def test_general_synthetic_batch_is_not_two_airport_allowlist(self):
        # Eight qualified synthetic candidates use the exact predicates. Only
        # the external-source provider supplies synthetic named-site text.
        candidates = []
        originals = identity.original
        def provide(sid, packet, store, hosts):
            if sid.startswith('synthetic-'):
                n = int(sid.split('-')[-1])
                return f'ZZ{n:02d} Synthetic Airfield {n} 360000N {120+n:03d}0000E Street {n} Seoul', {'url': f'https://www.airport.kr/synthetic-{n}'}
            return originals(sid, packet, store, hosts)
        for n in range(8):
            item = deepcopy(self.candidates[0])
            item.update(candidateKey=f'synthetic-candidate-{n}', observedCode=f'ZZ{n:02d}')
            for observation in item['observations']:
                observation.update(sourceId=f'synthetic-aip-{n}', aipName=f'Synthetic Airfield {n}', arpDms=f'360000N {120+n:03d}0000E')
            item['independent'] = {'facilityKey': f'https://www.airport.kr/synthetic-{n}', 'sourceId': f'synthetic-operator-{n}',
                                  'addressTokens': [f'Street {n}'], 'aipAddressTokens': [f'Street {n}', 'Seoul'], 'siteNameToken': f'Synthetic Airfield {n}'}
            candidates.append(item)
        with patch.object(identity, 'original', side_effect=provide):
            result = self.allocate(candidates)
        self.assertEqual(8, len(result['accepted']))
        self.assertEqual(8, len({r['airportId'] for r in result['registry']['identities']}))

    def test_full_disposable_identity_code_bundle_and_real_resolver_pipeline(self):
        report = rehearsal.rehearse()
        self.assertEqual(54, report['conditionalResolved'])
        self.assertEqual(37736, report['formalRegressionQueries'])
        self.assertTrue(report['productionRejectedTestAuthority'])
        self.assertTrue(report['repeatBatchReusesIds'])
        self.assertFalse(report['originalBytesReadHere'])
        self.assertFalse(report['productionSuccess'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
