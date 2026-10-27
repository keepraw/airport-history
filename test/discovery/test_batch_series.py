"""Cross-batch review semantics: unique mappings, preserved earlier batches, follow-ups without remapping."""
import copy
import hashlib
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/discovery'))
from review import batch_summaries, validate_batch, validate_batch_series, validate_review_overrides

BATCHES = ROOT / 'research/discovery/batches'
# PR #6 merged review record (main 02d4f2396a1bec8ad5ee0c8b10c3a8eb30db5643). Changing it requires a
# documented disposition change in a follow-up and a deliberate update of this pin.
GLOBAL_1_SHA256 = '4d0aa2fa15e2d4a32a78e5061639b6643056f7f28c813b0a011a27b87eabb6b6'
GLOBAL_1_STATUSES = {
    'global-1-kti': 'insufficient_evidence', 'global-1-ynt': 'insufficient_evidence', 'global-1-rov': 'insufficient_evidence',
    'global-1-lyg': 'insufficient_evidence', 'global-1-ybp': 'insufficient_evidence', 'global-1-lzo': 'insufficient_evidence',
    'global-1-jng': 'insufficient_evidence', 'global-1-dakar': 'insufficient_evidence', 'global-1-pnh': 'insufficient_evidence',
    'global-1-aap': 'insufficient_evidence', 'global-1-cdt': 'excluded', 'global-1-dni': 'pending_review',
    'global-1-ngn': 'excluded', 'global-1-wch': 'pending_review', 'global-1-bve': 'excluded', 'global-1-knn': 'pending_review',
    'global-1-utr': 'pending_review', 'global-1-hds': 'excluded', 'global-1-lmh': 'insufficient_evidence',
    'global-1-swn': 'insufficient_evidence',
}
GLOBAL_2_CANDIDATES = {
    'global-2-sgs': 'cand_07f311536256078e1803e39f', 'global-2-dqm': 'cand_5ebbfdbcea7f1b2aa138be41',
    'global-2-cat': 'cand_cb20612a6a4f6d8542872ae1', 'global-2-iqm': 'cand_dbe848d5c843e4ffc5270e26',
}


def load(name):
    return json.loads((BATCHES / name).read_text())


class BatchSeriesTest(unittest.TestCase):
    def setUp(self):
        self.g1 = load('global-1.json')
        self.g2 = load('global-2.json')
        self.reviews = json.loads((ROOT / 'research/discovery/reviews.json').read_text())

    def records(self, g1=None, g2=None):
        return [('research/discovery/batches/global-1.json', g1 or self.g1),
                ('research/discovery/batches/global-2.json', g2 or self.g2)]

    def test_previous_batch_record_is_preserved_byte_for_byte(self):
        raw = (BATCHES / 'global-1.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), GLOBAL_1_SHA256)
        self.assertEqual({e['eventGroupId']: e['status'] for e in self.g1['events']}, GLOBAL_1_STATUSES)
        self.assertEqual(self.g1['statusCounts'], {'excluded': 4, 'insufficient_evidence': 12, 'pending_review': 4, 'ready_to_admit': 0})
        for cid, override in self.reviews.items():
            if override['eventGroupId'].startswith('global-1-'):
                self.assertEqual(override['evidenceReview'], 'research/discovery/batches/global-1.json')
        self.assertEqual(sum(o['evidenceReview'].endswith('global-1.json') for o in self.reviews.values()), 21)

    def test_second_batch_reviews_exactly_the_recorded_next_leads(self):
        validate_batch(self.g2)
        self.assertEqual({e['eventGroupId']: e['candidateIds'][0] for e in self.g2['events']}, GLOBAL_2_CANDIDATES)
        self.assertEqual(set(GLOBAL_2_CANDIDATES.values()), {lead['candidateId'] for lead in self.g1['nextBatch']})
        self.assertEqual(self.g2['statusCounts'], dict(Counter(e['status'] for e in self.g2['events']), pending_review=0, ready_to_admit=0))
        self.assertEqual(self.g2['admission']['assignments'], 0)
        self.assertTrue(all(not e['continuityInference']['usedForAdmission'] for e in self.g2['events']))
        for event in self.g2['events']:
            self.assertEqual(event['sourceObservation']['candidateId'], event['candidateIds'][0])

    def test_every_candidate_maps_to_at_most_one_event_across_batches(self):
        mapping = validate_batch_series([self.g1, self.g2])
        self.assertEqual(len(mapping), sum(len(e['candidateIds'] + e['relatedCandidateIds'])
                                           for b in (self.g1, self.g2) for e in b['events']))
        validate_review_overrides(self.reviews, self.records())

    def test_reusing_an_earlier_batch_candidate_is_rejected(self):
        for cid in ('cand_fd2a5e00b9b3f58536c0433e', 'cand_8ac1b12707d7c441ce708d32', 'cand_7fc9b08615e93efbdffdc2a8'):
            with self.subTest(candidate=cid):
                g2 = copy.deepcopy(self.g2)
                g2['events'][0]['relatedCandidateIds'].append(cid)
                with self.assertRaisesRegex(ValueError, 'Candidate maps to multiple batch events'):
                    validate_batch_series([self.g1, g2])
                with self.assertRaisesRegex(ValueError, 'Candidate maps to multiple batch events'):
                    validate_review_overrides(self.reviews, self.records(g2=g2))

    def test_duplicate_event_group_or_batch_id_across_batches_is_rejected(self):
        g2 = copy.deepcopy(self.g2)
        g2['events'][0]['eventGroupId'] = 'global-1-kti'
        with self.assertRaisesRegex(ValueError, 'Duplicate event group across batches'):
            validate_batch_series([self.g1, g2])
        g2 = copy.deepcopy(self.g2)
        g2['batchId'] = 'global-1'
        with self.assertRaisesRegex(ValueError, 'Duplicate batch ID'):
            validate_batch_series([self.g1, g2])

    def test_follow_ups_keep_global_one_as_sole_mapping(self):
        follow = {f['eventGroupId']: f for f in self.g2['followUps']}
        self.assertEqual(set(follow), {'global-1-kti', 'global-1-ynt', 'global-1-rov'})
        for f in follow.values():
            self.assertEqual(f['candidateIds'], [])
            self.assertFalse(f['dispositionChanged'])
            self.assertEqual(f['currentStatus'], GLOBAL_1_STATUSES[f['eventGroupId']])
            self.assertTrue(f['searches'] and f['negativeResults'] and f['remainingGaps'])
        g2 = copy.deepcopy(self.g2)
        g2['followUps'][0]['candidateIds'] = ['cand_fd2a5e00b9b3f58536c0433e']
        with self.assertRaisesRegex(ValueError, 'must not map candidates'):
            validate_batch(g2)

    def test_follow_up_must_target_an_earlier_event_with_matching_status(self):
        g2 = copy.deepcopy(self.g2)
        g2['followUps'][0]['eventGroupId'] = 'global-2-sgs'  # same-batch, not earlier
        with self.assertRaisesRegex(ValueError, 'references no earlier event'):
            validate_batch_series([self.g1, g2])
        g2 = copy.deepcopy(self.g2)
        g2['followUps'][0]['currentStatus'] = 'ready_to_admit'
        g2['followUps'][0]['dispositionChanged'] = True
        g2['followUps'][0]['changeReason'] = 'test'
        with self.assertRaisesRegex(ValueError, 'disagrees with owning event'):
            validate_batch_series([self.g1, g2])
        g2 = copy.deepcopy(self.g2)
        g2['followUps'][0]['dispositionChanged'] = True
        with self.assertRaisesRegex(ValueError, 'flag disagrees'):
            validate_batch(g2)

    def test_batch_ceiling_is_enforced_per_batch(self):
        g2 = copy.deepcopy(self.g2)
        extra = copy.deepcopy(g2['events'][0])
        extra['eventGroupId'] = 'global-2-extra'
        extra['candidateIds'] = ['cand_c16c53f63535b6ce914aeff9']
        extra['relatedCandidateIds'] = []
        g2['events'].append(extra)
        g2['selection']['eventCount'] = 5
        g2['statusCounts']['insufficient_evidence'] += 1
        with self.assertRaisesRegex(ValueError, 'at most 4 events'):
            validate_batch(g2)
        g2['selection']['maximumEvents'] = 21
        with self.assertRaisesRegex(ValueError, 'Wrong batch ceiling'):
            validate_batch(g2)

    def test_unready_second_batch_event_cannot_acquire_formal_data(self):
        g2 = copy.deepcopy(self.g2)
        g2['events'][3]['admittedAssignmentIds'] = ['iata-iqm-yudu-guessed']
        with self.assertRaisesRegex(ValueError, 'Unready event promoted'):
            validate_batch(g2)

    def test_summary_lists_batches_in_numeric_order_with_follow_ups(self):
        summaries = batch_summaries(ROOT)
        self.assertEqual([s['batchId'] for s in summaries], ['global-1', 'global-2'])
        self.assertNotIn('followUps', summaries[0])
        self.assertEqual([f['eventGroupId'] for f in summaries[1]['followUps']], ['global-1-kti', 'global-1-ynt', 'global-1-rov'])


if __name__ == '__main__':
    unittest.main()
