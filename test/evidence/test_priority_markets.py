"""Real-market corpus decisions and independent fail-closed mutation checks."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/evidence'))
import priority_markets as pm


class PriorityMarketResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Semantic tests also run in the existing disposable AAI lifecycle clone,
        # where that harness intentionally replaces grants/receipts. The separate
        # priority-market CLI/CI step checks all 301 real baseline hashes.
        cls.sources, cls.cases, cls.policies = pm.verify(baseline=False)
        cls.samples = {s['sampleId']: s for s in pm.load(pm.BASE / 'samples.json')['samples']}

    def evaluate(self, sample_id, *, sample=None, sources=None):
        return pm.evaluate(sample or self.samples[sample_id], sources or self.sources, self.policies)

    def test_entire_real_positive_and_negative_corpus(self):
        results = pm.decisions(self.sources, self.policies)
        self.assertEqual(22, len(results['decisions']))
        self.assertTrue(all(not r['productionEligible'] and r['authorization'] is None for r in results['decisions']))

    def test_korean_utc_edges_exclude_both_partial_local_dates(self):
        for key in ['kr-rksi-pair', 'kr-rkss-pair']:
            result = self.evaluate(key)
            self.assertEqual({'from':'2025-04-18','toExclusive':'2025-05-15','wholeLocalDates':27}, result['proposedWindow'])
            self.assertEqual(1, result['independentIssuers'])
            self.assertIn('intervening_amendment_and_notam_screening_pending', result['reasons'])

    def test_duplicate_originals_cannot_masquerade_as_two_observations(self):
        sources = copy.deepcopy(self.sources)
        a, b = 'kr-rksi-2025-04-16', 'kr-rksi-2025-05-14'
        sources[b]['originalSha256'] = sources[a]['originalSha256']
        result = self.evaluate('kr-rksi-pair', sources=sources)
        self.assertEqual('hold', result['status'])
        self.assertIn('two_components_are_not_two_editions', result['reasons'])

    def test_different_pages_in_one_edition_are_not_two_editions(self):
        sources = copy.deepcopy(self.sources)
        sources['kr-rksi-2025-05-14']['originalPublicationKey'] = sources['kr-rksi-2025-04-16']['originalPublicationKey']
        self.assertEqual('hold', self.evaluate('kr-rksi-pair', sources=sources)['status'])

    def test_arp_change_blocks_interpolation(self):
        sources = copy.deepcopy(self.sources)
        span = sources['kr-rksi-2025-05-14']['spans'][1]
        span['quote'] = span['quote'].replace('372745N', '373325N')
        result = self.evaluate('kr-rksi-pair', sources=sources)
        self.assertEqual('hold', result['status'])
        self.assertIn('code_name_or_physical_arp_mismatch', result['reasons'])

    def test_original_host_is_bound_to_market(self):
        sources = copy.deepcopy(self.sources)
        sources['kr-rksi-2025-04-16']['url'] = 'https://example.com/uncontrolled-mirror'
        self.assertEqual('hold', self.evaluate('kr-rksi-pair', sources=sources)['status'])

    def test_missing_issue_publication_anchor_blocks_window(self):
        sources = copy.deepcopy(self.sources)
        sources['kr-history']['spans'] = []
        self.assertEqual('hold', self.evaluate('kr-rksi-pair', sources=sources)['status'])

    def test_namespace_and_source_scope_cannot_expand(self):
        sample = copy.deepcopy(self.samples['kr-rksi-pair'])
        sample.update(namespace='IATA', code='ICN')
        self.assertEqual('hold', self.evaluate('', sample=sample)['status'])
        self.assertEqual('hold', self.evaluate('kr-mixed-physical-sites')['status'])

    def test_real_stale_and_future_chinese_material_never_sets_dates(self):
        self.assertEqual('association_only', self.evaluate('cn-lzo-old-association')['status'])
        for key in ['cn-lzo-capture-as-validity', 'cn-future-meteorology', 'cn-city-only-old-met', 'cn-zha-unlocated']:
            self.assertEqual('hold', self.evaluate(key)['status'])

    def test_real_closure_and_foreign_namespace_counterexamples(self):
        for key in ['uk-closure-interpolation','us-faa-to-iata','jp-opening-as-allocation',
                    'es-page-revision-as-window','de-service-stop-as-withdrawal',
                    'kr-rksi-long-gap','kr-rkss-long-gap']:
            self.assertEqual('hold', self.evaluate(key)['status'])


if __name__ == '__main__':
    unittest.main()
