"""Real Git-index regressions for the versioned publisher's copyright audit."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish
import runtime


class CandidateRightsTests(unittest.TestCase):
    def setUp(self):
        (runtime.ROOT / 'work').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=runtime.ROOT / 'work')
        self.addCleanup(self.tmp.cleanup)
        self.checkout = Path(self.tmp.name) / 'candidate'
        subprocess.run(['git', 'clone', '--quiet', '--shared', str(runtime.ROOT),
                        str(self.checkout)], check=True)
        for name in ('data/airports.json', 'package.json'):
            path = self.checkout / name
            value = json.loads(path.read_text())
            value['dataVersion' if name.startswith('data/') else 'version'] = '0.11.0'
            path.write_text(json.dumps(value, indent=2) + '\n')
        subprocess.run(['git', 'add', 'data/airports.json', 'package.json'],
                       cwd=self.checkout, check=True)

    def test_versioned_candidate_passes_and_its_actual_staged_files_are_counted(self):
        result = publish.audit_candidate_rights(self.checkout)
        self.assertEqual(result['koreaStagedFilesChecked'], 2)
        self.assertEqual(result['restrictedReachableBlobs'], 0)
        self.assertFalse(result['koreanFullResponsesOrExtractionsPublished'])
        self.assertEqual(json.loads((self.checkout / 'data/airports.json').read_text())['dataVersion'], '0.11.0')

    def test_full_original_in_candidate_index_is_rejected(self):
        path = self.checkout / 'full-response.html'
        path.write_text('<!doctype html><html><body>Full response fixture</body></html>')
        subprocess.run(['git', 'add', path.name], cwd=self.checkout, check=True)
        with self.assertRaises(subprocess.CalledProcessError):
            publish.audit_candidate_rights(self.checkout)

    def test_private_path_in_candidate_index_is_rejected(self):
        path = self.checkout / 'work/private-original.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text('{"fixture":true}\n')
        subprocess.run(['git', 'add', '--force', str(path.relative_to(self.checkout))],
                       cwd=self.checkout, check=True)
        with self.assertRaises(subprocess.CalledProcessError):
            publish.audit_candidate_rights(self.checkout)

    def test_old_authorization_binding_rejects_the_changed_publisher(self):
        with self.assertRaisesRegex(ValueError, 'Executor changed'):
            runtime.checked_bindings(runtime.policy('identity'))
        with self.assertRaisesRegex(ValueError, 'Executor changed'):
            runtime.checked_bindings(runtime.policy('kr-code'))


if __name__ == '__main__':
    unittest.main()
