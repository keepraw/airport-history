"""Negative admission regressions against the real China bundle."""
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('project_admission', ROOT / 'scripts/evidence/project_admission.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class ChinaAdmission(unittest.TestCase):
    def setUp(self):
        b = ROOT / 'research/admissions/0.11.0'
        self.base = a.load(ROOT / 'test/curated-0.10.0.json')
        self.data = a.load(b / 'proposed-data.json')
        self.batches = [a.load(p) for p in sorted((b / 'batches').glob('*.json'))]
        self.dossier = a.load(b / 'dossier.json')
        self.sources = a.load(b / 'source-reviews.json')
    def run_gate(self):
        return a.validate(self.base, self.data, self.batches, self.dossier,
                          a.receipt(self.data, self.batches, self.dossier, self.sources), self.sources)
    def test_real_admission(self):
        self.assertEqual(self.run_gate(), dict(airports=6, assignments=0, names=0, sources=5))
    def test_published_record_mutation(self):
        self.data['airports'][0]['name']['value'] = 'Changed'
        with self.assertRaisesRegex(ValueError, 'permanent records'): self.run_gate()
    def test_code_interval_rejected_even_with_fresh_receipt(self):
        x = copy.deepcopy(self.data['assignments'][0]); x['assignmentId'] = 'unapproved'; self.data['assignments'].append(x)
        with self.assertRaisesRegex(ValueError, 'Only physical identity'): self.run_gate()
    def test_wrong_original_hash(self):
        self.sources[0]['originalSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'source review hash'): self.run_gate()
    def test_inactive_aip_family(self):
        self.sources[0]['policyFamily'] = 'CN-CAAC-AIP'
        with self.assertRaisesRegex(ValueError, 'inactive source'): self.run_gate()
    def test_missing_execution_evidence(self):
        self.dossier[0]['supplementalEvidence'] = []
        with self.assertRaisesRegex(ValueError, 'execution corroboration'): self.run_gate()
    def test_coordinate_substitution(self):
        self.data['airports'][37]['coordinates']['value']['latitude'] += 1
        self.dossier[0]['approvedRecord'] = copy.deepcopy(self.data['airports'][37])
        with self.assertRaisesRegex(ValueError, 'coordinate substitution'): self.run_gate()
    def test_fake_human_review(self):
        self.dossier[0]['reviewer'] = 'keepraw'
        with self.assertRaisesRegex(ValueError, 'machine claim decision'): self.run_gate()

if __name__ == '__main__': unittest.main()
