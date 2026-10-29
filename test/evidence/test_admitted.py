"""Exercise the real seven-record admission and reject unauthorized changes."""
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
import admitted


class ApprovedAdmissionTests(unittest.TestCase):
    def fixture(self):
        root = admitted.REVIEW
        return [admitted.load(ROOT / 'test/curated-0.8.0.json'), admitted.load(root / 'approval.json'),
                admitted.load(root / 'dossier.json'), admitted.load(root / 'source-review.json'),
                [admitted.load(p) for p in sorted((root / 'batches').glob('*.json'))]]

    def test_actual_seven_record_admission(self):
        self.assertEqual(admitted.validate_records(*self.fixture()),
                         {'airports': 4, 'assignments': 3, 'names': 0, 'sources': 7})

    def test_unapproved_or_unreviewed_changes_are_rejected(self):
        for change in ('reviewer', 'decision', 'bounds', 'source', 'timezone', 'extra', 'old_record'):
            data, approval, dossier, sources, batches = self.fixture()
            if change == 'reviewer': dossier[0]['reviewer'] = ''
            elif change == 'decision': dossier[0]['decision'] = 'pending'
            elif change == 'bounds': data['assignments'][-3]['validTo']['earliest'] = '2010-05-22'
            elif change == 'source': data['sources'][-1]['verificationStatus'] = 'pending'
            elif change == 'timezone': data['airports'][-1]['timezone'].update(value='America/Chicago', status='reference')
            elif change == 'extra':
                proposal = admitted.load(ROOT / 'research/evidence/direct/generated/proposed-data.json')
                data['assignments'].append(next(a for a in proposal['assignments'] if a['assignmentId'] == 'proposal-icao-xwa'))
            else: data['airports'][0]['coordinates']['note'] += ' changed'
            with self.subTest(change=change), self.assertRaises(ValueError):
                admitted.validate_records(data, approval, dossier, sources, batches)

    def test_replay_cannot_substitute_a_caller_supplied_base(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
            fake = Path(tmp) / 'caller-base.json'
            fake.write_bytes(admitted.research_baseline_path().read_bytes())
            output = Path(tmp) / 'must-not-exist.json'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/evidence/review.py'), 'validate',
                                     '--base-dataset', str(fake), '--batches', str(admitted.REVIEW / 'batches'),
                                     '--dataset', str(ROOT / 'test/curated-0.8.0.json'),
                                     '--dossier', str(admitted.REVIEW / 'dossier.json'), '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('immutable reviewed baseline', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
