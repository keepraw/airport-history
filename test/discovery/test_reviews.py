import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/discovery'))
from core import apply_review, read_candidates, write_candidates
from review import validate_batch


class ReviewTest(unittest.TestCase):
    def test_override_retains_observation_and_does_not_promote_evidence(self):
        original = {'candidateId': 'cand_a123', 'changes': {'iata': ['ROV', 'RVI']},
                    'time': {'eventDate': None},
                    'evidence': {'evidenceType': 'indirect', 'verificationStatus': 'pending'},
                    'review': {'status': 'pending_investigation', 'evidenceGaps': ['Unreviewed']}}
        saved = copy.deepcopy(original)
        reviews = {'cand_a123': {'status': 'insufficient_evidence', 'evidenceGaps': ['Need code notice']}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_candidates(out, 'fixture', [original])
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            reviewed = list(read_candidates(out, 'fixture', reviews))[0]
            self.assertEqual(reviewed['review']['status'], 'insufficient_evidence')
            self.assertEqual(reviewed['time'], saved['time'])
            self.assertEqual(reviewed['evidence'], saved['evidence'])
            self.assertEqual(list(read_candidates(out, 'fixture'))[0], saved)
            self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})
        self.assertEqual(original, saved)

    def test_ranked_queue_status_and_review_remain_consistent(self):
        original = {'candidateId': 'cand_a123', 'status': 'pending_investigation', 'priorityScore': 130}
        result = apply_review(original, {'cand_a123': {'status': 'excluded', 'exclusionReason': 'Marker correction'}})
        self.assertEqual(result['status'], result['review']['status'])
        self.assertEqual(result['priorityScore'], 130)
        self.assertEqual(original['status'], 'pending_investigation')

    def setUp(self):
        self.batch = json.loads((ROOT / 'research/discovery/batches/global-1.json').read_text())

    def test_actual_batch_retains_all_twenty_groups_and_three_duplicate_aliases(self):
        validate_batch(self.batch)
        events = self.batch['events']
        self.assertEqual(len(events), 20)
        self.assertEqual(sum(len(e['relatedCandidateIds']) for e in events), 3)
        self.assertEqual(self.batch['admission']['assignments'], 0)
        self.assertTrue(all(not e['continuityInference']['usedForAdmission'] for e in events))

    def test_batch_limit_and_duplicate_event_are_rejected(self):
        self.batch['events'].append(copy.deepcopy(self.batch['events'][0]))
        with self.assertRaisesRegex(ValueError, 'at most 20'):
            validate_batch(self.batch)

    def test_unready_event_cannot_acquire_formal_assignment(self):
        self.batch['events'][0]['admittedAssignmentIds'] = ['iata-kti-guessed']
        with self.assertRaisesRegex(ValueError, 'Unready event promoted'):
            validate_batch(self.batch)

    def test_missing_claim_source_and_unexplained_exclusion_are_rejected(self):
        self.batch['events'][0]['claims']['iata']['sourceIds'] = ['missing']
        with self.assertRaisesRegex(ValueError, 'Dangling claim source'):
            validate_batch(self.batch)
        self.setUp()
        event = next(e for e in self.batch['events'] if e['status'] == 'excluded')
        event['exclusionReason'] = None
        with self.assertRaisesRegex(ValueError, 'Missing exclusion reason'):
            validate_batch(self.batch)
