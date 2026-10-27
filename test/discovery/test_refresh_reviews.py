import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/discovery'))
from core import write_json, write_jsonl
from refresh_reviews import refresh_reviews
from report import reuse_baselines
from review import batch_summaries


class RefreshReviewsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.discovery = self.root / 'research/discovery'
        self.out = self.discovery / 'generated'
        self.out.mkdir(parents=True)
        self.inputs = {
            'scripts/discovery/scan.py': b'# pinned scanner\n',
            'scripts/discovery/report.py': b'# pinned report generator\n',
            'research/discovery/sources.json': b'{"revision":"pinned"}\n',
            'data/airports.json': b'{"airports":[]}\n',
        }
        for name, raw in self.inputs.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        for name in ('batches/global-1.json', 'batches/global-2.json', 'batches/global-3.json', 'reviews.json'):
            path = self.discovery / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / 'research/discovery' / name).read_bytes())
        write_json(self.out / 'summary.json', {'sourceRevisionCandidates': 1000, 'reviewBatches': []})
        write_jsonl(self.out / 'fixture.candidates.a.jsonl.gz', [{'candidateId': 'cand_a123', 'time': {'eventDate': None}}])
        write_jsonl(self.out / 'verification-queue.jsonl.gz', [{'candidateId': 'cand_a123', 'status': 'pending_investigation'}])
        write_jsonl(self.out / 'fixture.versions.jsonl.gz', [{'commit': '1' * 40, 'afterBlob': '2' * 40}])
        self.seal_fixture()

    def seal_fixture(self):
        def digest(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        write_json(self.out / 'manifest.json', {
            'formatVersion': 1,
            'files': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)}
                      for p in self.out.iterdir() if p.name != 'manifest.json'},
            'inputs': {name: digest(self.root / name) for name in self.inputs},
            'reviewInputs': {str(p.relative_to(self.root)): digest(p) for p in
                             [self.discovery / 'reviews.json', self.discovery / 'batches/global-1.json',
                              self.discovery / 'batches/global-2.json',
                              self.discovery / 'batches/global-3.json']},
        })

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_tampered_summary_size_or_hash_is_rejected_before_writes(self):
        path = self.out / 'summary.json'
        original = path.read_bytes()
        for tampered in (original + b'\n', original.replace(b'1000', b'2000')):
            with self.subTest(size=len(tampered)):
                path.write_bytes(tampered)
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'Discovery artifact changed: summary.json'):
                    refresh_reviews(self.root)
                self.assertEqual(self.snapshot(), before)

    def test_every_non_review_input_is_checked_without_reregistering_hashes(self):
        # Includes scanner, report generator, source pins and formal database.
        for name, original in self.inputs.items():
            with self.subTest(input=name):
                path = self.root / name
                path.write_bytes(original + b' ')
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'Non-review input changed: ' + name):
                    refresh_reviews(self.root)
                self.assertEqual(self.snapshot(), before)
                path.write_bytes(original)

    def test_legal_review_edits_only_update_review_summary_and_manifest_fields(self):
        original_lock = json.loads((self.out / 'manifest.json').read_text())
        original_summary = json.loads((self.out / 'summary.json').read_text())
        batch_path = self.discovery / 'batches/global-1.json'
        batch = json.loads(batch_path.read_text())
        batch['admission']['reason'] += ' Follow-up documentation reviewed.'
        write_json(batch_path, batch)
        reviews_path = self.discovery / 'reviews.json'
        reviews = json.loads(reviews_path.read_text())
        reviews[next(iter(reviews))]['nextAction'] += ' Keep the original pinned observations.'
        write_json(reviews_path, reviews)
        before = self.snapshot()
        refresh_reviews(self.root)
        after = self.snapshot()
        self.assertEqual({name for name in before if before[name] != after[name]}, {
            'research/discovery/generated/summary.json', 'research/discovery/generated/manifest.json',
        })
        lock = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(lock['inputs'], original_lock['inputs'])
        for name in original_lock['files']:
            if name != 'summary.json':
                self.assertEqual(lock['files'][name], original_lock['files'][name])
        expected_lock = copy.deepcopy(original_lock)
        expected_lock['files']['summary.json'] = lock['files']['summary.json']
        expected_lock['reviewInputs'] = lock['reviewInputs']
        self.assertEqual(lock, expected_lock)
        for name, digest in lock['reviewInputs'].items():
            self.assertEqual(digest, hashlib.sha256((self.root / name).read_bytes()).hexdigest())
        summary = json.loads((self.out / 'summary.json').read_text())
        self.assertEqual(summary['reviewBatches'], batch_summaries(self.root))
        summary.pop('reviewBatches')
        original_summary.pop('reviewBatches')
        self.assertEqual(summary, original_summary)
        raw = (self.out / 'summary.json').read_bytes()
        self.assertEqual(lock['files']['summary.json'], {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        refresh_reviews(self.root)
        self.assertEqual(self.snapshot(), after)  # Deterministic repeated refresh.

    def test_other_artifact_corruption_or_invalid_review_cannot_modify_outputs(self):
        for path, replacement, error in [
            (self.out / 'fixture.candidates.a.jsonl.gz', b'corrupt', ValueError),
            (self.discovery / 'reviews.json', b'{invalid', json.JSONDecodeError),
        ]:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(replacement)
                before = self.snapshot()
                with self.assertRaises(error):
                    refresh_reviews(self.root)
                self.assertEqual(self.snapshot(), before)
                path.write_bytes(original)

    def assert_semantic_refresh_rejected(self, mutate, message):
        # Each mutation starts from valid JSON; hash refresh is allowed for reviews.
        reviews = json.loads((ROOT / 'research/discovery/reviews.json').read_text())
        mutate(reviews)
        write_json(self.discovery / 'reviews.json', reviews)
        before = self.snapshot()
        with patch('refresh_reviews.write_json', side_effect=AssertionError('Output write attempted')):
            with self.assertRaisesRegex(ValueError, message):
                refresh_reviews(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_status_mismatch_is_rejected_before_any_output_write(self):
        def mismatch(reviews):
            review = reviews[next(iter(reviews))]
            review['status'] = 'pending_review' if review['status'] != 'pending_review' else 'insufficient_evidence'
        self.assert_semantic_refresh_rejected(mismatch, 'Review status disagrees with batch')

    def test_event_group_mismatch_is_rejected_before_any_output_write(self):
        def mismatch(reviews):
            reviews[next(iter(reviews))]['eventGroupId'] = 'global-1-wrong-event'
        self.assert_semantic_refresh_rejected(mismatch, 'Review event group disagrees with batch')

    def test_evidence_path_mismatch_is_rejected_before_any_output_write(self):
        def mismatch(reviews):
            reviews[next(iter(reviews))]['evidenceReview'] = 'research/discovery/batches/wrong.json'
        self.assert_semantic_refresh_rejected(mismatch, 'Review evidence path disagrees with batch')

    def test_orphaned_and_missing_overrides_are_rejected_without_output_changes(self):
        def orphan(reviews):
            reviews['cand_orphan'] = copy.deepcopy(reviews[next(iter(reviews))])
        def missing(reviews):
            del reviews[next(iter(reviews))]
        for mutation, message in [(orphan, 'Orphaned candidate review overrides'),
                                  (missing, 'Missing candidate review mappings')]:
            with self.subTest(error=message):
                self.assert_semantic_refresh_rejected(mutation, message)

    def test_required_review_fields_are_validated_before_output_changes(self):
        cases = [('status', 'unknown', 'Invalid review status'),
                 ('nextAction', '', 'Missing review nextAction'),
                 ('nextAction', '   ', 'Missing review nextAction'),
                 ('evidenceGaps', [], 'Missing review evidenceGaps'),
                 ('evidenceGaps', ['   '], 'Missing review evidenceGaps'),
                 ('exclusionReason', '', 'Missing review exclusionReason')]
        for field, value, message in cases:
            with self.subTest(field=field, value=value):
                def invalidate(reviews):
                    review = (next(r for r in reviews.values() if r['status'] == 'excluded')
                              if field == 'exclusionReason' else reviews[next(iter(reviews))])
                    review[field] = value
                self.assert_semantic_refresh_rejected(invalidate, message)

    def test_candidate_cannot_map_to_events_in_multiple_batches(self):
        batch = json.loads((self.discovery / 'batches/global-1.json').read_text())
        batch['batchId'] = 'duplicate-batch'
        write_json(self.discovery / 'batches/duplicate.json', batch)
        self.assert_semantic_refresh_rejected(lambda reviews: None, 'Candidate maps to multiple batch events')

    def test_report_can_verify_reused_baselines_without_source_git_objects(self):
        version = {'commit': '1' * 40, 'afterBlob': '2' * 40,
                   'afterRecords': 1, 'observedAt': '2025-01-02T00:00:00Z'}
        config = {'sources': [{'id': 'fixture', 'revision': '3' * 40, 'path': 'airports.csv',
                               'localRepository': 'work/not-downloaded.git'}]}
        write_json(self.out / 'fixture.coverage.json',
                   {'sourceId': 'fixture', 'revision': '3' * 40, 'path': 'airports.csv'})
        write_jsonl(self.out / 'fixture.versions.jsonl.gz', [version])
        write_json(self.out / 'year-country-coverage.json',
                   [{'sourceId': 'fixture', 'observationYear': '2025',
                     'representativeVersion': version, 'recordsByCountry': {'CN': 1}}])
        baseline = {'repository': 'https://example.invalid/Keepraw-Fly', 'revision': '4' * 40, 'sha256': 'a' * 64}
        write_json(self.discovery / 'keepraw-fly-baseline.json', baseline)
        self.inputs['research/discovery/keepraw-fly-baseline.json'] = b''
        comparison = {**baseline, 'sharedIataCodes': 1}
        write_json(self.out / 'keepraw-fly-comparison.json', comparison)
        self.seal_fixture()
        before = self.snapshot()
        with patch('report.ROOT', self.root), patch('report.git', side_effect=AssertionError('Source Git access forbidden')):
            self.assertEqual(reuse_baselines(config, self.out), comparison)
            config['sources'][0]['revision'] = '5' * 40
            with self.assertRaisesRegex(ValueError, 'Stale snapshot source pin'):
                reuse_baselines(config, self.out)
        self.assertEqual(self.snapshot(), before)
