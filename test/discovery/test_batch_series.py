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
# PR #6 merged review record (main 02d4f2396a1bec8ad5ee0c8b10c3a8eb30db5643) had SHA-256 4d0aa2fa...b6b6.
# PR #8/#9 deliberately changed dispositions via global-3/global-4 follow-ups; the original conclusions are kept in
# each event's dispositionHistory. Changing it again requires another documented follow-up and a new pin.
GLOBAL_1_ORIGINAL_SHA256 = '4d0aa2fa15e2d4a32a78e5061639b6643056f7f28c813b0a011a27b87eabb6b6'
GLOBAL_1_PR8_SHA256 = '4a3cf6124383d9adbba7f16691123461cbd9e5a535801f2253bc197349443e70'
GLOBAL_1_SHA256 = '4031acb6f1480583fb2b3ce1fc24eca9bde7fd823133e8e0974fe25001f69094'
ADMITTED_IN_GLOBAL_3 = {'global-1-rov', 'global-1-ynt', 'global-1-pnh'}
ADMITTED_IN_GLOBAL_4 = {'global-1-dakar', 'global-1-aap'}
GLOBAL_1_STATUSES = {
    'global-1-kti': 'insufficient_evidence', 'global-1-ynt': 'insufficient_evidence', 'global-1-rov': 'insufficient_evidence',
    'global-1-lyg': 'insufficient_evidence', 'global-1-ybp': 'insufficient_evidence', 'global-1-lzo': 'insufficient_evidence',
    'global-1-jng': 'insufficient_evidence', 'global-1-dakar': 'insufficient_evidence', 'global-1-pnh': 'insufficient_evidence',
    # Original PR #6 statuses; ADMITTED_IN_GLOBAL_3 events are now ready_to_admit.
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
        self.g3 = load('global-3.json')
        self.g4 = load('global-4.json')
        self.reviews = json.loads((ROOT / 'research/discovery/reviews.json').read_text())

    def records(self, g1=None, g2=None):
        return [('research/discovery/batches/global-1.json', g1 or self.g1),
                ('research/discovery/batches/global-2.json', g2 or self.g2),
                ('research/discovery/batches/global-3.json', self.g3),
                ('research/discovery/batches/global-4.json', self.g4)]

    def series(self, g1=None, g2=None, g3=None):
        return validate_batch_series([g1 or self.g1, g2 or self.g2, g3 or self.g3, self.g4])

    def test_reviewed_disposition_pin_and_original_conclusions_are_preserved(self):
        raw = (BATCHES / 'global-1.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), GLOBAL_1_SHA256)
        live = {e['eventGroupId']: e['status'] for e in self.g1['events']}
        original = {e['eventGroupId']: (e['dispositionHistory'][0]['status'] if 'dispositionHistory' in e else e['status'])
                    for e in self.g1['events']}
        self.assertEqual(original, GLOBAL_1_STATUSES)
        self.assertEqual({g for g in live if live[g] != GLOBAL_1_STATUSES[g]}, ADMITTED_IN_GLOBAL_3 | ADMITTED_IN_GLOBAL_4)
        self.assertEqual(self.g1['statusCounts'], {'excluded': 4, 'insufficient_evidence': 7, 'pending_review': 4, 'ready_to_admit': 5})
        self.assertEqual(self.g1['admission']['assignments'], 0)  # global-1 itself admitted nothing
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
        mapping = self.series()
        self.assertEqual(len(mapping), sum(len(e['candidateIds'] + e['relatedCandidateIds'])
                                           for b in (self.g1, self.g2) for e in b['events']))
        validate_review_overrides(self.reviews, self.records())

    def test_reusing_an_earlier_batch_candidate_is_rejected(self):
        for cid in ('cand_fd2a5e00b9b3f58536c0433e', 'cand_8ac1b12707d7c441ce708d32', 'cand_7fc9b08615e93efbdffdc2a8'):
            with self.subTest(candidate=cid):
                g2 = copy.deepcopy(self.g2)
                g2['events'][0]['relatedCandidateIds'].append(cid)
                with self.assertRaisesRegex(ValueError, 'Candidate maps to multiple batch events'):
                    self.series(g2=g2)
                with self.assertRaisesRegex(ValueError, 'Candidate maps to multiple batch events'):
                    validate_review_overrides(self.reviews, self.records(g2=g2))

    def test_duplicate_event_group_or_batch_id_across_batches_is_rejected(self):
        g2 = copy.deepcopy(self.g2)
        g2['events'][0]['eventGroupId'] = 'global-1-kti'
        with self.assertRaisesRegex(ValueError, 'Duplicate event group across batches'):
            self.series(g2=g2)
        g2 = copy.deepcopy(self.g2)
        g2['batchId'] = 'global-1'
        with self.assertRaisesRegex(ValueError, 'Duplicate batch ID'):
            self.series(g2=g2)

    def test_follow_ups_keep_global_one_as_sole_mapping(self):
        follow = {f['eventGroupId']: f for f in self.g2['followUps']}
        self.assertEqual(set(follow), {'global-1-kti', 'global-1-ynt', 'global-1-rov'})
        for f in follow.values():
            self.assertEqual(f['candidateIds'], [])
            self.assertFalse(f['dispositionChanged'])
            self.assertEqual(f['currentStatus'], GLOBAL_1_STATUSES[f['eventGroupId']])  # status at PR #7 time
            self.assertTrue(f['searches'] and f['negativeResults'] and f['remainingGaps'])
        g2 = copy.deepcopy(self.g2)
        g2['followUps'][0]['candidateIds'] = ['cand_fd2a5e00b9b3f58536c0433e']
        with self.assertRaisesRegex(ValueError, 'must not map candidates'):
            validate_batch(g2)

    def test_follow_up_must_target_an_earlier_event_with_matching_status(self):
        g2 = copy.deepcopy(self.g2)
        g2['followUps'][0]['eventGroupId'] = 'global-2-sgs'  # same-batch, not earlier
        with self.assertRaisesRegex(ValueError, 'references no earlier event'):
            self.series(g2=g2)
        g2 = copy.deepcopy(self.g2)
        g2['followUps'][0]['currentStatus'] = 'ready_to_admit'
        g2['followUps'][0]['dispositionChanged'] = True
        g2['followUps'][0]['changeReason'] = 'test'
        with self.assertRaisesRegex(ValueError, 'disagrees with owning event'):
            self.series(g2=g2)
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
        self.assertEqual([s['batchId'] for s in summaries], ['global-1', 'global-2', 'global-3', 'global-4'])
        self.assertNotIn('followUps', summaries[0])
        self.assertEqual([f['eventGroupId'] for f in summaries[1]['followUps']], ['global-1-kti', 'global-1-ynt', 'global-1-rov'])


class AdmissionFollowUpTest(BatchSeriesTest):
    def test_global_three_changes_dispositions_without_remapping(self):
        self.assertEqual(self.g3['events'], [])
        follow = {f['eventGroupId']: f for f in self.g3['followUps']}
        self.assertEqual(set(follow), ADMITTED_IN_GLOBAL_3)
        for f in follow.values():
            self.assertEqual((f['priorStatus'], f['currentStatus'], f['dispositionChanged']), ('insufficient_evidence', 'ready_to_admit', True))
            self.assertEqual(f['candidateIds'], [])
            self.assertTrue(f['changeReason'] and f['remainingGaps'] and f['expectedResolverBehaviour'])
            self.assertTrue(f['continuityInference']['usedForAdmission'])
        self.assertEqual(sum(len(f['admittedAssignmentIds']) for f in follow.values()), self.g3['admission']['assignments'])
        self.assertEqual(sum(len(f['admittedAirportIds']) for f in follow.values()), self.g3['admission']['airports'])
        for event in self.g1['events']:
            if event['eventGroupId'] in ADMITTED_IN_GLOBAL_3:
                self.assertEqual([h['recordedIn'] for h in event['dispositionHistory']], ['global-1', 'global-3'])
                self.assertEqual(event['admissionReview'], 'research/discovery/batches/global-3.json')

    def test_kratie_and_qiemo_remain_research_only(self):
        statuses = {e['eventGroupId']: e['status'] for e in self.g1['events'] + self.g2['events']}
        self.assertEqual(statuses['global-1-kti'], 'insufficient_evidence')
        self.assertEqual(statuses['global-2-iqm'], 'insufficient_evidence')

    def test_disposition_change_without_follow_up_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Follow-up status disagrees with owning event'):
            validate_batch_series([self.g1, self.g2])  # global-3 missing
        g1 = copy.deepcopy(self.g1)
        event = next(e for e in g1['events'] if e['eventGroupId'] == 'global-1-kti')
        event['status'] = 'ready_to_admit'
        g1['statusCounts']['insufficient_evidence'] -= 1
        g1['statusCounts']['ready_to_admit'] += 1
        with self.assertRaisesRegex(ValueError, '(disagrees with owning event|breaks the disposition chain): global-1-kti'):
            self.series(g1=g1)

    def test_broken_chain_and_unready_admission_are_rejected(self):
        g3 = copy.deepcopy(self.g3)
        g3['followUps'][0]['priorStatus'] = 'pending_review'
        with self.assertRaisesRegex(ValueError, 'breaks the disposition chain'):
            self.series(g3=g3)
        g3 = copy.deepcopy(self.g3)
        g3['followUps'][0]['currentStatus'] = 'insufficient_evidence'
        g3['followUps'][0]['dispositionChanged'] = False
        with self.assertRaisesRegex(ValueError, 'Unready follow-up promoted'):
            validate_batch(g3)


class GlobalFourAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.batches = [load(f'global-{n}.json') for n in range(1, 5)]
        self.g1, _, _, self.g4 = self.batches

    def test_screening_is_bounded_and_does_not_repeat_completed_admissions(self):
        screening = self.g4['screening']
        self.assertEqual(len(screening), 10)
        self.assertEqual(sum(s['selected'] for s in screening), 4)
        self.assertEqual(self.g4['events'], [])
        follow = {f['eventGroupId']: f for f in self.g4['followUps']}
        self.assertEqual(set(follow), {'global-1-dakar', 'global-1-aap', 'global-1-lyg', 'global-1-jng'})
        self.assertEqual({g for g, f in follow.items() if f['dispositionChanged']}, ADMITTED_IN_GLOBAL_4)
        self.assertTrue(all(f['candidateIds'] == [] for f in follow.values()))
        self.assertEqual(sum(len(f['admittedAirportIds']) for f in follow.values()), 4)
        self.assertEqual(sum(len(f['admittedAssignmentIds']) for f in follow.values()), 5)
        self.assertEqual(sum(len(f['admittedNameIds']) for f in follow.values()), 1)
        self.assertTrue(all(f['remainingGaps'] for f in follow.values()))

    def test_partial_admissions_preserve_original_claims_and_mapping_ownership(self):
        mapping = validate_batch_series(self.batches)
        for event in self.g1['events']:
            if event['eventGroupId'] not in ADMITTED_IN_GLOBAL_4:
                continue
            self.assertEqual([h['recordedIn'] for h in event['dispositionHistory']], ['global-1', 'global-4'])
            self.assertEqual(event['dispositionHistory'][0]['status'], 'insufficient_evidence')
            self.assertFalse(event['continuityInference']['usedForAdmission'])  # original review, retained
            self.assertTrue(event['claims'] and event['sourceIds'] and event['evidenceGaps'])
            self.assertEqual(event['admittedAssignmentIds'], [])  # admission belongs to follow-up
            for cid in event['candidateIds'] + event['relatedCandidateIds']:
                self.assertEqual(mapping[cid], event['eventGroupId'])
        with self.assertRaisesRegex(ValueError, 'disagrees with owning event'):
            validate_batch_series(self.batches[:-1])

    def test_admitted_ids_and_formal_source_links_exist(self):
        data = json.loads((ROOT / 'data/airports.json').read_text())
        formal_sources = {s['sourceId']: s for s in data['sources']}
        for source in self.g4['sources']:
            if source.get('formalSourceId'):
                self.assertIn(source['formalSourceId'], formal_sources)
                self.assertEqual(source['url'], formal_sources[source['formalSourceId']]['url'])
        for f in self.g4['followUps']:
            for field, key, id_key in [('admittedAirportIds', 'airports', 'airportId'),
                                      ('admittedAssignmentIds', 'assignments', 'assignmentId'),
                                      ('admittedNameIds', 'names', 'nameId')]:
                self.assertLessEqual(set(f[field]), {r[id_key] for r in data[key]})


if __name__ == '__main__':
    unittest.main()
