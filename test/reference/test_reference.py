import csv
import gzip
import json
import random
import sys
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/reference'))
from common import OUTPUT, DISCOVERY, digest, read_jsonl, stable_id
from build import build, make_record, add_transition, enrich_timezones
from timezones import load_catalog
from query import lookup
from triage import classify, match_reference, build as build_triage, OUT as TRIAGE
from validate import main as validate_reference
from admissions import packets, validate_admission
from review import validate_batch_series


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / 'work').mkdir(exist_ok=True)
        cls.curated = json.loads((ROOT / 'data/airports.json').read_text())
        cls.lock = json.loads((ROOT / 'reference/source-lock.json').read_text())

    def test_complete_pinned_population_and_historical_only(self):
        validate_reference()

    def test_full_rebuild_byte_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            out = Path(temp)
            build(out)
            expected = {p.name: digest(p) for p in OUTPUT.iterdir() if p.is_file()}
            self.assertEqual({p.name: digest(p) for p in out.iterdir()}, expected)

    def test_full_triage_rebuild_byte_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            out = Path(temp)
            build_triage(out)
            self.assertEqual({p.name: digest(p) for p in out.iterdir()},
                             {p.name: digest(p) for p in TRIAGE.iterdir() if p.is_file()})

    def test_ids_stable_across_full_population_input_reordering(self):
        with gzip.open(ROOT / 'reference/inputs/ourairports.csv.gz', 'rt', newline='') as stream:
            rows = list(csv.DictReader(stream))
        def ids(values):
            result = {}
            for r in values:
                record = make_record(r, True, self.lock, [])
                result[r['id']] = (record['referenceId'], [p['locationId'] for p in record['locations']])
            return result
        expected = ids(rows)
        random.Random(42).shuffle(rows)
        self.assertEqual(ids(rows), expected)

    def test_source_identity_does_not_merge_repurposed_physical_airports(self):
        # The reviewed Pranoto external row previously described Temindung, 16 km away.
        result = lookup(source_id='26763')
        self.assertEqual(result['status'], 'ambiguous_reference')
        record = result['candidates'][0]
        self.assertGreater(len(record['locations']), 1)
        self.assertEqual(record['curatedAirportIds'], ['apt_80ab4c35-b89f-40af-a368-bc71b3716d5a'])
        self.assertTrue(all(not p['curatedAirportIds'] for p in record['locations'] if p['kind'] == 'unresolved_transition_location'))
        with gzip.open(ROOT / 'reference/inputs/ourairports.csv.gz', 'rt', newline='') as stream:
            row = next(r for r in csv.DictReader(stream) if r['id'] == '26763')
        row['latitude_deg'], row['longitude_deg'] = '-0.4845309854', '117.1569976807'
        mismatched = make_record(row, True, self.lock, self.curated['airports'])
        self.assertFalse(mismatched['curatedAirportIds'])
        self.assertIn('curated_external_id_location_mismatch', mismatched['flags'])

    def test_worldwide_active_closed_codeless_and_historical_names(self):
        jfk = lookup(code='JFK')
        self.assertGreater(jfk['totalMatches'], 0)
        self.assertFalse(jfk['historicallyVerified'])
        self.assertNotEqual(jfk['status'], 'resolved')
        self.assertTrue(all(not r['curatedAirportIds'] for r in jfk['candidates']))
        old = lookup(source_id='12148')
        self.assertEqual(old['totalMatches'], 1)
        record = old['candidates'][0]
        self.assertFalse(record['presentAtSnapshot'])
        self.assertEqual(record['facilityType'], 'closed')
        self.assertIsNone(record['identifiers']['IATA'])
        self.assertIsNone(record['identifiers']['ICAO'])
        self.assertGreater(lookup(name='Temindung', country='ID')['totalMatches'], 0)

    def test_typed_codes_reuse_pagination_and_filters(self):
        icao = lookup(code='KJFK', scheme='ICAO')
        self.assertGreater(icao['totalMatches'], 0)
        with self.assertRaises(ValueError):
            lookup(code='KJFK', scheme='IATA')
        for row in icao['candidates']:
            self.assertTrue(row['identifiers']['ICAO'] == 'KJFK' or any(h['scheme'] == 'ICAO' and h['code'] == 'KJFK' for h in row['historicalIdentifiers']))
        self.assertEqual(lookup(code='LON')['status'], 'not_found')
        reused = lookup(code='KTI', limit=1)
        self.assertEqual(reused['status'], 'ambiguous_reference')
        self.assertGreater(reused['totalMatches'], 1)
        self.assertEqual(reused['returnedMatches'], 1)
        second = lookup(code='KTI', limit=1, offset=1)
        self.assertNotEqual(reused['candidates'][0]['referenceId'], second['candidates'][0]['referenceId'])
        self.assertEqual(lookup(code='JFK', country='CN')['totalMatches'], 0)
        self.assertEqual(lookup(source_id='999999999999')['totalMatches'], 0)

    def test_incomplete_transition_coordinates_never_filled_from_today(self):
        row = {'id': '1', 'name': 'Example', 'type': 'small_airport', 'latitude_deg': '10', 'longitude_deg': '20', 'iso_country': 'US'}
        record = make_record(row, True, self.lock, [])
        candidate = {'candidateId': 'cand_' + 'a' * 24, 'distanceKm': 500, 'changes': {'lat': ['0', '10']},
                     'observations': [{'observedAt': '2020-01-01T00:00:00Z', 'commit': 'a' * 40, 'beforeBlob': 'b' * 40, 'afterBlob': 'c' * 40}]}
        add_transition(record, candidate)
        self.assertEqual(len(record['locations']), 1)
        self.assertIn('incomplete_historical_location', record['flags'])

    def test_timezone_enrichment_uses_pinned_names_without_host_tzdb(self):
        # America/Coyhaique first appeared in tzdb 2025b. Host packages can be older.
        from unittest.mock import patch
        row = {'id': '1', 'name': 'Example', 'type': 'small_airport', 'latitude_deg': '-45.6',
               'longitude_deg': '-72.1', 'iso_country': 'CL', 'icao_code': 'SCCY'}
        record = make_record(row, True, self.lock, [])
        entry = {'sourceEntityId': 'SCCY', 'presentAtTarget': True,
                 'reference': {'row': {'country': 'CL', 'lat': '-45.6', 'lon': '-72.1', 'tz': 'America/Coyhaique'}}}
        with patch('zoneinfo.ZoneInfo', side_effect=RuntimeError('Host tzdb must not be consulted')):
            enrich_timezones({'1': record}, [entry], {'revision': 'a' * 40}, load_catalog())
        self.assertEqual(record['timezone'], 'America/Coyhaique')
        entry['reference']['row']['tz'] = 'Invalid/Unlisted'
        record = make_record(row, True, self.lock, [])
        enrich_timezones({'1': record}, [entry], {'revision': 'a' * 40}, load_catalog())
        self.assertIsNone(record['timezone'])
        self.assertIn('invalid_timezone', record['flags'])

    def test_bounded_memory_lookup_runtime_smoke(self):
        start = time.monotonic()
        tracemalloc.start()
        for code in ['JFK', 'LAX', 'SYD']:
            self.assertGreater(lookup(code=code)['totalMatches'], 0)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLess(peak, 64 * 1024 * 1024, 'Indexed lookup must not materialize the worldwide registry')
        self.assertLess(time.monotonic() - start, 15, 'Indexed code lookup regressed to an impractical full-registry scan')


class BulkReviewTests(unittest.TestCase):
    def test_unavailable_historical_numeric_ids_never_create_dangling_matches(self):
        missing = match_reference('12345', {})
        self.assertIsNone(missing['referenceId'])
        self.assertEqual(missing['basis'], 'numeric_external_record_unavailable')
        rid = stable_id('ref_', ['ourairports', '12345'])
        matched = match_reference('12345', {rid: []})
        self.assertEqual(matched['referenceId'], rid)
        self.assertFalse(matched['verifiedPhysicalIdentity'])

    def groups(self, count):
        for n in range(count):
            yield {'eventGroupId': f'group-{n}', 'status': 'awaiting_primary_evidence', 'candidateIds': [f'cand_{n:024x}'],
                   'members': [{'sourceId': 'ourairports'}], 'name': 'Unreviewed airport',
                   'evidenceGaps': ['No primary effective-date evidence'], 'nextAction': 'Review official sources'}

    def test_no_five_airport_ceiling_and_original_twenty_event_rule(self):
        batches = list(packets(self.groups(53), '2026-10-28', '4' * 40))
        self.assertEqual([len(b['events']) for b in batches], [20, 20, 13])
        self.assertEqual(len(validate_batch_series(batches)), 53)
        with self.assertRaises(ValueError):
            list(packets(self.groups(53), '2026-10-28', '4' * 40, 21))
        duplicate = json.loads(json.dumps(batches))
        duplicate[1]['events'][0]['candidateIds'] = duplicate[0]['events'][0]['candidateIds']
        with self.assertRaises(ValueError):
            validate_batch_series(duplicate)

    def test_corrections_backfills_and_city_codes_are_not_historical_events(self):
        self.assertEqual(classify({'types': ['icao_change'], 'changes': {'icao': [None, '']}}), 'empty_namespace_backfill_excluded')
        self.assertEqual(classify({'types': ['city_code_membership_change'], 'changes': {}}), 'city_membership_excluded')
        self.assertEqual(classify({'types': ['possible_relocation'], 'changes': {}, 'distanceKm': 50}), 'location_change_or_directory_correction')

    def fixture(self):
        batch = list(packets(self.groups(1), '2026-10-28', '4' * 40))[0]
        batch.pop('preparationOnly')
        event = batch['events'][0]
        event['status'] = 'ready_to_admit'
        event['admittedAssignmentIds'] = ['new-assignment']
        event['sourceIds'] = ['official-observation']
        for claim in event['claims'].values():
            claim.update(sourceIds=['official-observation'], evidenceType='primary_direct')
        batch['sources'][0].update(sourceId='official-observation', sourceType='primary')
        batch['statusCounts'].update(pending_review=0, ready_to_admit=1)
        base = {'schemaVersion': '3.0.0', 'dataVersion': '0.7.0', 'airports': [], 'assignments': [], 'names': [], 'sources': []}
        proposed = {**base, 'dataVersion': '0.8.0', 'assignments': [{'assignmentId': 'new-assignment', 'scheme': 'IATA', 'sourceIds': ['official-observation']}],
                    'sources': [{'sourceId': 'official-observation', 'sourceType': 'primary', 'verificationStatus': 'verified'}]}
        dossier = [{'recordId': 'new-assignment', 'decision': 'accepted', 'reviewer': 'fixture reviewer',
                    'boundaryAssessment': 'Explicitly unknown start; bounded by dated official observation.',
                    'continuityAssessment': 'Reviewed inference between dated observations only.',
                    'observations': [{'sourceId': 'official-observation', 'observedOn': '2020-01-01', 'sourceFamily': 'official-aip',
                                      'independentOriginal': True, 'claimScope': 'IATA', 'basis': 'Fixture explicit observation, not real evidence.'}]}]
        return base, proposed, [batch], dossier

    def test_admission_gate_accepts_dated_reviewed_original_proposal(self):
        self.assertEqual(validate_admission(*self.fixture())['assignments'], 1)

    def test_admission_gate_rejects_derivatives_unreviewed_or_changed_ids(self):
        for mutation in ('derivative', 'future', 'unreviewed', 'unmapped', 'prepared', 'missing_boundaries', 'existing_changed'):
            base, proposed, batches, dossier = self.fixture()
            if mutation == 'derivative':
                dossier[0]['observations'][0]['sourceFamily'] = 'ourairports'
            elif mutation == 'future':
                dossier[0]['observations'][0]['observedOn'] = '2030-01-01'
            elif mutation == 'unreviewed':
                dossier[0]['decision'] = 'pending'
            elif mutation == 'unmapped':
                dossier[0]['observations'][0]['sourceId'] = 'missing'
            elif mutation == 'prepared':
                batches[0]['preparationOnly'] = True
            elif mutation == 'missing_boundaries':
                dossier[0].pop('boundaryAssessment')
            else:
                base['airports'] = [{'airportId': 'permanent', 'name': 'unchanged'}]
                proposed['airports'] = [{'airportId': 'permanent', 'name': 'overwritten'}]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_admission(base, proposed, batches, dossier)


if __name__ == '__main__':
    unittest.main()
