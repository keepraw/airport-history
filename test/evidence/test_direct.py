import copy
import gzip
import importlib.util
import json
import socket
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
spec = importlib.util.spec_from_file_location('direct_evidence', ROOT / 'scripts/evidence/direct.py')
direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(direct)


class DirectEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assessment = json.loads((direct.BASE / 'assessments.json').read_text())
        cls.facts = {f['factId']: f for f in cls.assessment['facts']}
        cls.loaded = direct.locked_sources()

    def test_every_judgment_has_an_exact_original_page_and_scope(self):
        for fact in self.facts.values():
            citation = direct.locate(fact, self.loaded[fact['sourceId']][1])
            self.assertGreaterEqual(citation['extractedPage'], 1)
            self.assertTrue(citation['anchor'])
            self.assertTrue(fact['conclusion'])
        broken = {**self.facts['pfn-code'], 'anchor': 'This fabricated allocation never occurred'}
        with self.assertRaisesRegex(ValueError, 'Missing or misbound'):
            direct.locate(broken, self.loaded['faa-2009'][1])

    def test_icao_requires_an_airport_row_and_explicit_jurisdiction_rule(self):
        fact, rule = self.facts['pfn-code'], self.facts['icao-rule-2009']
        self.assertEqual(direct.international_indicator(fact, rule), 'KPFN')
        for wrong in [{**fact, 'jurisdiction': 'Alaska'}, {**fact, 'kind': 'GPS'},
                      {**fact, 'anchor': 'PANAMA CITY VORTAC PFN'},
                      {**fact, 'faaIdentifier': '1A2'},
                      {**fact, 'faaIdentifier': 'SGU'}]:
            with self.assertRaisesRegex(ValueError, 'explicit contiguous-US'):
                direct.international_indicator(wrong, rule)
        with self.assertRaises(ValueError):
            direct.international_indicator(fact, {**rule, 'kind': 'directory_update_context'})

    def test_physical_coordinates_bind_only_the_adjacent_named_subject(self):
        fact = self.facts['sgu-old-location']
        self.assertAlmostEqual(direct.coordinates(fact)['latitude'], 37 + 5 / 60 + 26 / 3600)
        wrong = {**fact, 'subject': 'Unrelated Hospital Heliport'}
        with self.assertRaises(ValueError):
            direct.locate(wrong, self.loaded[fact['sourceId']][1])
        with self.assertRaisesRegex(ValueError, 'Invalid DMS'):
            direct.coordinates({**fact, 'anchor': 'lat. 37°65\'26"N., long. 113°35\'35"W.'})

    def test_actual_dates_service_dates_and_publication_typos_stay_separate(self):
        self.assertEqual(self.facts['sgu-decommission']['date'], '2011-01-15')
        self.assertEqual(self.facts['sgu-taf-start']['date'], '2011-01-12')
        self.assertEqual(self.facts['sgu-taf-restore']['date'], '2011-12-15')
        self.assertIsNone(self.loaded['nws-sgu-open'][0]['publicationDate'])
        self.assertEqual(self.facts['panama-actual']['precision'], 'month')
        self.assertEqual(self.facts['sgu-sample']['kind'], 'rejected_sample')
        self.assertFalse(any(a['code'] == 'KDXZ' for a in self.assessment['assignments']))

    def test_source_repetitions_and_context_are_not_confirmed_code_conflicts(self):
        self.assertEqual(self.facts['williston-list-correction']['kind'], 'directory_update_context')
        self.assertEqual(self.facts['williston-new-first-coordinate']['kind'], 'directory_coordinate_revision')
        self.assertEqual(self.facts['cleveland-earlier-closure']['kind'], 'unresolved_chronology')
        self.assertEqual(len({s['originalPublicationKey'] for s, _ in self.loaded.values()}), 16)
        metrics = json.loads((direct.OUT / 'metrics.json').read_text())
        self.assertEqual(metrics['confirmedHistoricalCodeConflicts'], 0)
        self.assertEqual(metrics['formalHistoricalCoverageIncrease'], 0)

    def test_original_mutation_and_escaping_paths_fail_closed(self):
        source = copy.deepcopy(self.loaded['nws-panama'][0])
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
            directory = Path(tmp)
            source['inputPath'] = 'changed.gz'
            (directory / 'changed.gz').write_bytes(gzip.compress(b'changed original'))
            direct.write_json(directory / 'source-lock.json', {'sources': [source]})
            with self.assertRaisesRegex(ValueError, 'Changed pinned input'):
                direct.locked_sources(directory)
            source['inputPath'] = '../escape.gz'
            direct.write_json(directory / 'source-lock.json', {'sources': [source]})
            with self.assertRaisesRegex(ValueError, 'escapes'):
                direct.locked_sources(directory)

    def test_changed_online_recovery_cannot_replace_a_locked_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp, patch.object(
                direct, 'get', return_value=(b'changed upstream', 'https://www.faa.gov/changed')):
            with self.assertRaisesRegex(ValueError, 'Upstream original changed'):
                direct.acquire(Path(tmp), recover=True)
            self.assertFalse((Path(tmp) / 'source-lock.json').exists())

    def test_unique_existing_review_ownership_and_no_invented_candidate(self):
        direct.validate()
        pending = json.loads((direct.OUT / 'proposed-data.json').read_text())
        base = json.loads(direct.research_baseline_path().read_text())
        batches = list(direct.read_jsonl(direct.OUT / 'review-packets.jsonl.gz'))
        dossier = json.loads((direct.OUT / 'dossier.json').read_text())
        self.assertEqual(len(pending['airports']) - len(base['airports']), 6)
        self.assertEqual(len(pending['assignments']) - len(base['assignments']), 6)
        self.assertEqual(len(dossier), 12)
        self.assertTrue(all(d['reviewer'] is None and d['decision'] == 'pending' for d in dossier))
        with self.assertRaisesRegex(ValueError, 'Prepared packets'):
            direct.validate_admission(base, pending, batches, dossier)
        blocked = json.loads((direct.OUT / 'blocked-record-drafts.json').read_text())
        self.assertEqual(len(blocked['airports']), 2)
        self.assertTrue(set(a['airportId'] for a in blocked['airports']).isdisjoint(a['airportId'] for a in pending['airports']))

    def test_complete_offline_rebuild_is_byte_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp, \
                patch.object(socket, 'create_connection', side_effect=AssertionError('network disabled')), \
                patch.object(direct, 'get', side_effect=AssertionError('network disabled')):
            output = Path(tmp)
            direct.build(output)
            direct.validate(output)
            for path in direct.OUT.iterdir():
                self.assertEqual(path.read_bytes(), (output / path.name).read_bytes(), path.name)

    def test_build_consumes_an_explicit_new_snapshot_and_traces_its_originals(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
            snapshot = Path(tmp) / 'new-snapshot'
            snapshot.mkdir()
            for directory in ('inputs', 'texts'):
                shutil.copytree(direct.BASE / directory, snapshot / directory)
            lock = json.loads((direct.BASE / 'source-lock.json').read_text())
            lock['sources'][0]['accessedAt'] = '2026-10-28T14:01:00+00:00'
            direct.write_json(snapshot / 'source-lock.json', lock)
            output = Path(tmp) / 'proposal'
            with patch.object(direct, 'get', side_effect=AssertionError('network disabled')):
                direct.build(output, snapshot)
                direct.validate(output)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['sourceDirectory'], str(snapshot.relative_to(ROOT)))
            observations = list(direct.read_jsonl(output / 'observations.jsonl.gz'))
            self.assertTrue(any(o['observedAt'] == '2026-10-28T14:01:00+00:00' for o in observations))
            self.assertIn(str(snapshot.relative_to(ROOT)) + '/inputs/', (output / 'evidence-index.md').read_text())


if __name__ == '__main__':
    unittest.main()
