import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'research/evidence/global-batch-5/tools'))
import global_batch_5 as batch  # noqa: E402


class GlobalBatchFiveTests(unittest.TestCase):
    def test_offline_validation_and_resolver_replay(self):
        subprocess.run(['python3', 'research/evidence/global-batch-5/tools/global_batch_5.py', 'validate'], cwd=ROOT, check=True)

    def test_research_layer_never_admits(self):
        data = json.loads((batch.BASE / 'batch.json').read_text())
        for event in data['events']:
            self.assertEqual(event['formalAdmission'], {'airports': [], 'assignments': [], 'names': []})
        self.assertLessEqual(len(data['events']), 12)

    def test_dates_keep_event_kinds_separate(self):
        for event in json.loads((batch.BASE / 'batch.json').read_text())['events']:
            self.assertEqual(set(event['dates']), batch.DATE_KEYS)

    def test_no_original_bytes_committed(self):
        committed = subprocess.check_output(['git', 'ls-files', 'research/evidence/global-batch-5'], cwd=ROOT, text=True).split()
        self.assertTrue(all(name.endswith(('.json', '.md')) or '/tools/' in name for name in committed))
        lock = json.loads((batch.BASE / 'source-lock.json').read_text())['sources']
        for entry in lock.values():
            self.assertNotIn('text', entry)


if __name__ == '__main__':
    unittest.main()
