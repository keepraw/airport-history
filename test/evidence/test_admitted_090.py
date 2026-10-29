"""Actual admission and negative scope/review regressions, using the production gate."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
import admitted_090 as admission


class Admission090Tests(unittest.TestCase):
    def fixture(self):
        review = admission.REVIEW
        return [admission.load(ROOT / 'data/airports.json'), admission.load(review / 'approval.json'),
                admission.load(review / 'dossier.json'), admission.load(review / 'source-review.json'),
                [admission.load(p) for p in sorted((review / 'batches').glob('*.json'))]]

    def test_actual_thirteen_owner_approved_records(self):
        self.assertEqual(admission.validate_records(*self.fixture()), {'airports': 7, 'assignments': 6, 'names': 0, 'sources': 18})

    def test_rejects_unauthorized_or_unreviewed_edits(self):
        for change in ('reviewer', 'pending', 'window', 'physical', 'source', 'provenance', 'old', 'deferred', 'event', 'approval'):
            data, approval, dossier, sources, batches = self.fixture()
            if change == 'reviewer': dossier[0]['reviewer'] = ''
            elif change == 'pending': dossier[-1]['decision'] = 'pending'
            elif change == 'window': data['assignments'][-1]['validFrom']['latest'] = '2019-08-02'
            elif change == 'physical': data['airports'][-2]['timezone'].update(status='reference', value='Europe/Madrid')
            elif change == 'source': data['sources'][-1]['verificationStatus'] = 'pending'
            elif change == 'provenance': sources[0]['editionEffectiveDate'] = '2025-01-01'
            elif change == 'old': data['airports'][0]['name']['value'] += ' changed'
            elif change == 'deferred':
                pending = admission.load(ROOT / 'research/evidence/markets/generated/proposed-data.json')
                data['assignments'].append(next(a for a in pending['assignments'] if a['code'] == 'LEMI'))
            elif change == 'event': batches[0]['events'][-1]['admittedAssignmentIds'] = []
            else: approval['approvedAssignments'][-1]['exactAuthorization']['validTo']['earliest'] = '2026-10-30'
            with self.subTest(change=change), self.assertRaises(ValueError):
                admission.validate_records(data, approval, dossier, sources, batches)


if __name__ == '__main__':
    unittest.main()
