import copy
import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
from pipeline import (BASE, OUT, build, validate, load_locked, parse_bts, parse_faa,
                      match_observation, candidate_index, load_reference, finish)
from common import digest, read_jsonl
from admissions import validate_admission
spec = importlib.util.spec_from_file_location('evidence_fetch', ROOT / 'scripts/evidence/fetch.py')
evidence_fetch = importlib.util.module_from_spec(spec)
sys.modules['evidence_fetch'] = evidence_fetch
spec.loader.exec_module(evidence_fetch)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {s['sourceId']: (s, raw) for s, raw in load_locked()}

    def test_real_bts_namespace_and_dates_are_not_iata_or_event_dates(self):
        observations = list(parse_bts(*self.sources['bts-master-coordinate']))
        self.assertEqual(len(observations), 20295)
        self.assertEqual(len({o['observationId'] for o in observations}), 20295)
        den = next(o for o in observations if o['authorityRecordId'] == '1129202')
        self.assertEqual(den['attributeInterval']['from'], '1993-09-01')
        self.assertEqual(den['codes'], [{'scheme': 'USDOT', 'code': 'DEN'}])
        self.assertIsNone(den['eventDate'])
        self.assertIsNone(den['historicalObservationDate'])
        self.assertIsNone(den['publicationDate'])
        self.assertFalse(den['historicallyVerified'])

    def test_mirrored_original_has_the_same_observation_identity(self):
        source, raw = self.sources['bts-master-coordinate']
        mirrored = {**source, 'sourceId': 'mirror', 'retrievalUrl': 'https://example.org/mirror',
                    'accessedAt': '2026-10-29T00:00:00+00:00'}
        self.assertEqual(next(parse_bts(source, raw))['observationId'], next(parse_bts(mirrored, raw))['observationId'])

    def test_faa_uses_named_subject_not_tower_runway_or_planned_closure(self):
        source, raw = self.sources['faa-fr-2016-13551']
        rows = list(parse_faa(source, raw, ['Davis Airport', 'Capital Region International Airport']))
        closed = [o for o in rows if o['kind'] == 'closure_statement']
        self.assertTrue(closed)
        self.assertEqual(closed[0]['name'], 'Davis Airport')
        self.assertEqual(closed[0]['reportedEventBounds'], {'earliest': '2000-01-01', 'latest': '2000-12-31', 'precision': 'year'})
        self.assertEqual(source['documentEffectiveDate'], '2016-09-15')
        self.assertIsNone(closed[0]['eventDate'])
        for sid, names in [('faa-fr-2025-09856', ['Phillips Army Airfield']),
                           ('faa-fr-2022-22901', ['Hickory Regional Airport']),
                           ('faa-fr-2026-20859', ['Indianapolis Downtown Heliport'])]:
            self.assertFalse(any(o['kind'] == 'closure_statement' for o in parse_faa(*self.sources[sid], names)))

    def test_location_binding_and_directory_correction_context(self):
        rows = list(parse_faa(*self.sources['faa-fr-2016-13551'], ['Davis Airport', 'Capital Region International Airport']))
        self.assertTrue(any(o['coordinates'] for o in rows if o['name'] == 'Capital Region International Airport'))
        self.assertFalse(any(o['coordinates'] for o in rows if o['name'] == 'Davis Airport'))
        self.assertTrue(any('directory_update_context_not_relocation' in o['qualityFlags'] for o in rows))

    def test_matching_retains_many_groups_conflicts_and_ambiguity(self):
        records = load_reference()
        index = candidate_index(records)
        row = next(o for o in parse_bts(*self.sources['bts-master-coordinate']) if o['authorityRecordId'] == '1037205')
        links = match_observation(row, index, records)
        self.assertGreater(len(links), 1)
        self.assertTrue(all(not a['historicallyVerified'] for a in links))
        wrong = {**row, 'country': 'CN'}
        self.assertTrue(all(a['status'] == 'conflict' for a in match_observation(wrong, index, records)))
        absent_position = {**row, 'coordinates': None}
        self.assertTrue(any(a['status'] == 'ambiguous' for a in match_observation(absent_position, index, records)))
        self.assertEqual(match_observation({**row, 'name': 'Unindexed', 'codes': []}, index, records), [])

    def test_hash_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
            directory = Path(tmp)
            source = copy.deepcopy(self.sources['bts-master-coordinate'][0])
            source['inputPath'] = 'mutated.gz'
            (directory / 'mutated.gz').write_bytes(gzip.compress(b'not the original'))
            (directory / 'source-lock.json').write_text(json.dumps({'sources': [source]}))
            with self.assertRaisesRegex(ValueError, 'Changed pinned input'):
                list(load_locked(directory))

    def test_recovery_reconstructs_both_original_and_compressed_hashes(self):
        originals = {source['retrievalUrl']: raw for source, raw in self.sources.values()}
        bts_raw = self.sources['bts-master-coordinate'][1]
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp, \
                patch('evidence_fetch.bts', return_value=(bts_raw, 'unused-transport-hash')), \
                patch('evidence_fetch.get', side_effect=lambda url: (originals[url], url)):
            evidence_fetch.recover(Path(tmp))
            for source, _ in self.sources.values():
                self.assertEqual(digest(Path(tmp) / source['inputPath']), source['inputSha256'])

    def test_all_evidence_retained_and_prepared_packets_cannot_admit(self):
        validate()
        batches = list(read_jsonl(OUT / 'review-packets.jsonl.gz'))
        self.assertTrue(batches)
        self.assertTrue(all(b['preparationOnly'] for b in batches))
        self.assertTrue(all(e['status'] == 'pending_review' and not e['admittedAssignmentIds']
                            for b in batches for e in b['events']))
        self.assertTrue(all('reviewer' not in b for b in batches))
        base = json.loads((ROOT / 'data/airports.json').read_text())
        proposed = {**base, 'dataVersion': '0.8.0'}
        with self.assertRaisesRegex(ValueError, 'Prepared packets'):
            validate_admission(base, proposed, batches, [])

    def test_full_offline_rebuild_is_byte_identical_without_network(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp, patch('urllib.request.urlopen', side_effect=AssertionError('Offline build accessed network')):
            output = Path(tmp)
            build(output)
            self.assertEqual({p.name: digest(p) for p in OUT.iterdir()}, {p.name: digest(p) for p in output.iterdir()})


if __name__ == '__main__':
    unittest.main()
