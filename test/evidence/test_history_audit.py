"""Real Git regressions: fingerprints, complete ancestry and disguised payloads."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('history_audit', ROOT/'scripts/evidence/history_audit.py')
ha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ha)
FIXTURE = b'Invented restricted full extraction for Git tests; no third-party work.'


class FingerprintTests(unittest.TestCase):
    def test_domain_encoding_and_normalization(self):
        oid = '0123456789abcdef0123456789abcdef01234567'
        expected = '7c9786cb33593d35432d43a5684516c8729356d454d958ce780f1a3403eca8d4'
        self.assertEqual(ha.fingerprint('blob', oid), expected)
        self.assertEqual(ha.fingerprint('blob', ' \t' + oid.upper() + '\r\n'), expected)
        self.assertNotEqual(ha.fingerprint('commit', oid), expected)
        self.assertEqual(len(expected), 64)

    def test_invalid_and_abbreviated_input_is_rejected(self):
        for value in ('a'*7, 'a'*39, 'a'*41, 'g'*40, 'Ａ'*40, '\u00a0'+'a'*40, None, b'a'*40):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ha.fingerprint('blob', value)
        with self.assertRaises(ValueError):
            ha.fingerprint('tree', 'a'*40)


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'keepraw')
        self.git('config', 'user.email', '49091395+keepraw@users.noreply.github.com')
        self.git('config', 'user.useConfigOnly', 'true')
        self.git('commit', '--allow-empty', '-qm', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        blob = self.git('hash-object', '-w', '--stdin', input=FIXTURE)
        self.audit = {'formatVersion': 2, 'base': self.base,
                      'restrictedCommitFingerprints': [],
                      'sources': [{'files': [{'gitBlobFingerprint': ha.fingerprint('blob', blob),
                                             'decompressedSha256': hashlib.sha256(FIXTURE).hexdigest()}]}]}

    def git(self, *args, input=None):
        return ha.git(self.root, *args, input=input).decode().strip()

    def commit(self, path, payload, message='fixture change'):
        p = self.root/path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(payload)
        self.git('add', '--', path)
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def test_clean_branch_passes_without_private_inventory(self):
        self.commit('notes.json', b'{"note":"Original research with a minimal citation."}')
        result = ha.verify(self.root, self.audit)
        self.assertEqual(result['reachablePRCommits'], 1)
        self.assertEqual(result['restrictedReachableBlobs'], 0)
        self.assertTrue(result['currentPRAncestryClean'])
        self.assertIsNone(result['remoteOldObjectsStillAccessible'])
        self.assertFalse(result['remoteAccessibilityCheckedByThisCommand'])

    def test_known_blob_reintroduced_is_rejected(self):
        self.commit('copied-original.bin', FIXTURE)
        with self.assertRaisesRegex(ValueError, 'full original/extraction'):
            ha.verify(self.root, self.audit)

    def test_known_blob_renamed_is_rejected(self):
        self.commit('innocent-looking/metadata.json', FIXTURE)
        with self.assertRaisesRegex(ValueError, 'full original/extraction'):
            ha.verify(self.root, self.audit)

    def test_deletion_only_in_worktree_does_not_clear_history(self):
        self.commit('copied-original.txt', FIXTURE)
        self.git('rm', 'copied-original.txt')
        self.git('commit', '-qm', 'delete current copy')
        self.assertFalse((self.root/'copied-original.txt').exists())
        with self.assertRaisesRegex(ValueError, 'full original/extraction'):
            ha.verify(self.root, self.audit)
        clean = self.git('commit-tree', self.git('rev-parse', 'HEAD^{tree}'), '-p', self.base, '-m', 'clean snapshot')
        self.assertEqual(ha.verify(self.root, self.audit, clean)['restrictedReachableBlobs'], 0)

    def test_restricted_commit_is_rejected_even_without_a_restricted_file(self):
        bad = self.commit('notes.txt', b'Invented permitted content.')
        self.audit['restrictedCommitFingerprints'] = [ha.fingerprint('commit', bad)]
        self.git('commit', '--allow-empty', '-qm', 'follow-up')
        with self.assertRaisesRegex(ValueError, 'Restricted-original commit remains an ancestor'):
            ha.verify(self.root, self.audit)

    def test_merge_parent_is_audited(self):
        clean = self.commit('notes.txt', b'Original note.')
        branch = self.git('branch', '--show-current')
        self.git('checkout', '-qb', 'side', self.base)
        self.commit('renamed.json', FIXTURE)
        self.git('checkout', '-q', branch)
        self.git('merge', '--no-ff', '-qm', 'merge fixture', 'side')
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), clean)
        with self.assertRaisesRegex(ValueError, 'full original/extraction'):
            ha.verify(self.root, self.audit)

    def test_retired_locator_exposure_commit_is_rejected(self):
        old = self.commit('notes.txt', b'Original note.')
        self.audit['locatorExposureCommitFingerprints'] = [ha.fingerprint('commit', old)]
        with self.assertRaisesRegex(ValueError, 'locator-exposure commit remains an ancestor'):
            ha.verify(self.root, self.audit)

    def test_shallow_clone_is_rejected(self):
        self.commit('notes.txt', b'Original note.')
        with tempfile.TemporaryDirectory() as folder:
            clone = Path(folder)/'shallow'
            subprocess.run(['git', 'clone', '-q', '--depth=1', self.root.as_uri(), str(clone)], check=True)
            with self.assertRaisesRegex(ValueError, 'Complete Git history'):
                ha.verify(clone, self.audit)

    def test_missing_parent_is_rejected(self):
        self.commit('notes.txt', b'Original note.')
        (self.root/'.git/objects'/self.base[:2]/self.base[2:]).unlink()
        with self.assertRaisesRegex(ValueError, 'Complete Git history'):
            ha.verify(self.root, self.audit)

    def test_missing_blob_is_rejected(self):
        self.commit('notes.txt', b'Original note.')
        blob = self.git('rev-parse', 'HEAD:notes.txt')
        (self.root/'.git/objects'/blob[:2]/blob[2:]).unlink()
        with self.assertRaisesRegex(ValueError, 'Complete Git history'):
            ha.verify(self.root, self.audit)

    def test_unrelated_main_is_rejected(self):
        self.commit('notes.txt', b'Original note.')
        self.audit['base'] = self.git('commit-tree', self.git('rev-parse', 'HEAD^{tree}'), '-m', 'unrelated root')
        with self.assertRaisesRegex(ValueError, 'main must remain an ancestor'):
            ha.verify(self.root, self.audit)

    def test_recompressed_full_text_is_rejected_by_content_hash(self):
        self.commit('renamed.json', gzip.compress(FIXTURE, mtime=123))
        with self.assertRaisesRegex(ValueError, 'full original/extraction content'):
            ha.verify(self.root, self.audit)

    def test_full_responses_disguised_as_json_or_archives_are_rejected(self):
        for payload in (b'%PDF-1.7 invented fixture', b'<html><body>Invented fixture</body></html>',
                        json.dumps({'response': '<html>Invented fixture</html>'}).encode()):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                ha.check_payload(payload, set(), set(), set())
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('ordinary.json', FIXTURE)
        with self.assertRaisesRegex(ValueError, 'full original/extraction content'):
            ha.check_payload(stream.getvalue(), set(), set(), {hashlib.sha256(FIXTURE).hexdigest()})

    def test_raw_locator_and_json_escaped_locator_are_rejected(self):
        blob = self.git('hash-object', '-w', '--stdin', input=FIXTURE)
        payloads = [blob.encode(), json.dumps({'locator': blob}).encode(),
                    ('{"locator":"' + ''.join('\\u%04x' % ord(c) for c in blob) + '"}').encode()]
        blobs = {ha.fingerprint('blob', blob)}
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, 'Direct restricted Git object locator'):
                ha.check_payload(payload, blobs, set(), set())

    def test_new_full_original_path_is_rejected(self):
        self.commit('research/evidence/transfers/inputs/invented.txt', b'New invented full response.')
        with self.assertRaisesRegex(ValueError, 'full original/extraction'):
            ha.verify(self.root, self.audit)


class PublicInventoryTests(unittest.TestCase):
    def test_locked_inventory_preserves_all_removed_pairs(self):
        a = json.loads(ha.AUDIT.read_text())
        blobs, commits, locators, _ = ha.inventory(a)
        self.assertEqual(len(a['sources']), 92)
        self.assertEqual(sum(len(s['files']) for s in a['sources']), 184)
        self.assertEqual(len(blobs), 184)
        self.assertEqual(len(commits), 3)
        self.assertEqual(len(locators), 2)
        # Pin the migrated membership, without publishing the original SHA-1s.
        self.assertEqual(hashlib.sha256('\n'.join(sorted(blobs)).encode()).hexdigest(),
                         '48da54ab65a83a6d49d7ae0070662e40b4939451d73031101b5411f545cd67f0')
        self.assertEqual(hashlib.sha256('\n'.join(sorted(commits)).encode()).hexdigest(),
                         '4f2e6856721652463938f52e7ae0788b047b2e86bf14e0c50f63957b17b43d7b')
        self.assertFalse(any(f['presentInCurrentTree'] for s in a['sources'] for f in s['files']))
        self.assertTrue(all(s['fullRedistributionPermission'] == 'not_explicitly_established' for s in a['sources']))
        self.assertTrue(a['residualRisk']['remoteOldObjectsStillAccessible'])
        ha.check_payload(ha.AUDIT.read_bytes(), blobs, commits | locators, set())
        serialized = ha.AUDIT.read_text()
        for legacy in ('gitBlobSha1', 'presentInCommits', 'forceLeaseExpected"', 'localBackup', 'sampledOldBlobSha1'):
            self.assertNotIn('"' + legacy, serialized)

    def test_actual_clean_branch_has_no_audited_ancestor_or_blob(self):
        result = ha.verify()
        self.assertEqual(result['restrictedAncestorCommits'], 0)
        self.assertEqual(result['locatorExposureAncestorCommits'], 0)
        self.assertEqual(result['restrictedReachableBlobs'], 0)
        self.assertTrue(result['remoteOldObjectsStillAccessible'])
        self.assertFalse(result['remoteAccessibilityCheckedByThisCommand'])

    def test_market_snapshot_and_transfer_provenance_use_commit_fingerprints(self):
        markets = json.loads((ROOT/'research/evidence/markets/generated/review-packets.json').read_text())
        transfers = json.loads((ROOT/'research/evidence/transfers/generated/review-packets.json').read_text())
        restricted = set(json.loads(ha.AUDIT.read_text())['restrictedCommitFingerprints'])
        expected = {p['batchId']: p['baseCommitFingerprint'] for p in markets}
        self.assertTrue(all(p['baseCommit'] is None for p in markets))
        self.assertTrue(all(p['baseCommitFingerprint'] in restricted for p in markets))
        for packet in transfers:
            if packet['batchId'] in expected:
                self.assertEqual(packet['originalSnapshotBaseCommitFingerprint'], expected[packet['batchId']])
                self.assertNotIn('originalSnapshotBaseCommit', packet)
                self.assertNotIn('baseCommitFingerprint', packet)
                self.assertEqual(packet['baseCommit'], json.loads(ha.AUDIT.read_text())['base'])


if __name__ == '__main__':
    unittest.main()
