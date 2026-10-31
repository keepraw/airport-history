"""Real Git-index regressions for the versioned publisher's copyright audit."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish
import runtime
import release_ci


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

    def stage_notam_fixture(self):
        raw = b'{"Total":1,"DATA":[{"FULL_TEXT":"synthetic full response fixture"}]}'
        metadata = self.checkout / 'research/admissions/0.11.0/rule-v1/evidence-version.json'
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(json.dumps({'sources': [{'originalSha256': hashlib.sha256(raw).hexdigest()}]}))
        response = self.checkout / 'response.json'
        response.write_bytes(raw)
        subprocess.run(['git', 'add', str(metadata.relative_to(self.checkout)), response.name], cwd=self.checkout, check=True)
        return metadata, response

    def test_new_notam_original_hash_is_checked_from_index_metadata(self):
        _, response = self.stage_notam_fixture()
        response.write_text('{"innocentWorkingTree":true}')
        with self.assertRaisesRegex(ValueError, 'Restricted full original'):
            publish.audit_candidate_rights(self.checkout)

    def test_removed_version_metadata_and_response_remain_audited_in_history(self):
        metadata, response = self.stage_notam_fixture()
        for key, value in [('user.name', 'keepraw'), ('user.email', '49091395+keepraw@users.noreply.github.com'), ('user.useConfigOnly', 'true')]:
            subprocess.run(['git', 'config', '--local', key, value], cwd=self.checkout, check=True)
        subprocess.run(['git', 'commit', '--quiet', '-m', 'test: add synthetic response'], cwd=self.checkout, check=True)
        subprocess.run(['git', 'rm', '--quiet', str(metadata.relative_to(self.checkout)), response.name], cwd=self.checkout, check=True)
        subprocess.run(['git', 'commit', '--quiet', '-m', 'test: remove synthetic response'], cwd=self.checkout, check=True)
        with self.assertRaisesRegex(ValueError, 'Restricted full original'):
            publish.audit_candidate_rights(self.checkout)

    def test_foreign_environment_index_cannot_hide_real_staged_html(self):
        path = self.checkout / 'staged.html'
        path.write_text('<html><body>synthetic response</body></html>')
        subprocess.run(['git', 'add', path.name], cwd=self.checkout, check=True)
        with patch.dict(os.environ, {'GIT_INDEX_FILE': str(runtime.ROOT / '.git/index')}):
            with self.assertRaises(subprocess.CalledProcessError):
                publish.audit_candidate_rights(self.checkout)

    def test_staged_symlink_is_rejected(self):
        path = self.checkout / 'original-link'
        path.symlink_to('work/private-original')
        subprocess.run(['git', 'add', path.name], cwd=self.checkout, check=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            publish.audit_candidate_rights(self.checkout)

    def test_versioned_ci_rejects_full_response_before_frozen_legacy_checks(self):
        bundle = self.checkout / 'research/admissions/0.11.0/rule-v1'
        bundle.mkdir(parents=True)
        data = json.loads((self.checkout / 'data/airports.json').read_text())
        (bundle / 'proposed-data.json').write_text(json.dumps(data))
        (bundle / 'receipt.json').write_text(json.dumps({'baselineCommit': '86b094df59f7654ffd1511bc16186f8a4cc35c9d'}))
        path = self.checkout / 'full-response.html'
        path.write_text('<html><body>synthetic full response</body></html>')
        subprocess.run(['git', 'add', path.name], cwd=self.checkout, check=True)
        original_run = subprocess.run
        def reject_legacy_first(args, *a, **kwargs):
            if args[0] == 'pnpm':
                raise AssertionError('Candidate copyright was not checked before legacy tests')
            return original_run(args, *a, **kwargs)
        offline = {'originalBytesReadHere': False, 'productionValidationPassed': False}
        with patch.object(release_ci, 'ROOT', self.checkout), patch.object(release_ci, 'validate', return_value=offline), \
                patch.object(subprocess, 'run', side_effect=reject_legacy_first), self.assertRaises(subprocess.CalledProcessError):
            release_ci.main()

    def test_old_authorization_binding_rejects_the_changed_publisher(self):
        # Read the actual pre-repair binding, so this regression remains valid
        # after a separately approved executor is registered in a later change.
        old = json.loads(subprocess.check_output([
            'git', 'show', '86b094df59f7654ffd1511bc16186f8a4cc35c9d:'
            'research/admission/rule-v1/bindings.json'], cwd=runtime.ROOT, text=True))
        original_load = runtime.load
        def frozen_binding(path):
            return old if Path(path) == runtime.PUBLIC / 'bindings.json' else original_load(path)
        with patch.object(runtime, 'load', side_effect=frozen_binding):
            for kind in ('identity', 'kr-code'):
                with self.assertRaisesRegex(ValueError, 'Executor changed'):
                    runtime.checked_bindings(runtime.policy(kind))


if __name__ == '__main__':
    unittest.main()
