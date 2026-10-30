"""Research-corpus custody and the actual namespace/date counterexamples."""
import datetime as dt
import json
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/evidence'))
import code_dates as cd


class CodeDateResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = cd.load(cd.BASE / 'source-lock.json')
        cls.sources = {r['sourceId']: r for r in cls.lock['sources']}
        cls.cases = {r['caseKey']: r for r in cd.load(cd.BASE / 'assessments.json')['cases']}
        cls.screen = cd.load(cd.BASE / 'korea-screening.json')

    def test_retained_corpus_and_receipt_verify_without_claiming_fresh_originals(self):
        # The existing admission rehearsal deliberately mutates formal/grant files
        # in its disposable candidate clone. The standalone CLI checks all 772
        # real-main hashes; these corpus checks also run inside that rehearsal.
        result = cd.verify(baseline=False)
        self.assertFalse(result['originalBytesRecheckedHere'])
        self.assertEqual(15, result['cases'])
        self.assertEqual(0, result['formalNewResolvedQueries'])

    def test_pre_relocation_archive_instant_does_not_become_a_whole_valid_day(self):
        for key in ['luzhou', 'lianyungang', 'yanan', 'yibin', 'ankang', 'zhanjiang']:
            case = self.cases[key]
            archived = [o for o in case['observations'] if o['evidenceType'] == 'archived_directory_statement']
            self.assertEqual(2, len(archived))
            self.assertTrue(all(o['localObservationDate'] == '2017-07-16' for o in archived))
            self.assertTrue(all(o['validityWindow'] is None and not o['allocationDateProved'] for o in archived))
            self.assertIsNone(case['approvedCompleteLocalDateWindow'])

    def test_fuzzy_iata_rows_and_city_rows_cannot_become_other_airport_evidence(self):
        for sid, exact, excluded in [('iata-eny-20261030', 'ENY', 'ENI'),
                                     ('iata-dax-20261030', 'DAX', 'PKX')]:
            source = self.sources[sid]
            excerpt = cd.load(cd.BASE / source['excerptPath'])
            quotes = ' '.join(s['quote'] for s in excerpt['spans'])
            self.assertEqual(exact, source['exactCodeFilter'])
            self.assertIn(exact, quotes)
            self.assertNotIn(excluded, quotes)
        ngo = self.sources['iata-ngo-20261030']
        quotes = [s['quote'] for s in cd.load(cd.BASE / ngo['excerptPath'])['spans']]
        self.assertTrue(any('Metropolitan Area' in q for q in quotes))
        self.assertTrue(all('airport row only' in o['siteHypothesis'] for o in self.cases['chubu']['observations'] if o['namespace'] == 'IATA'))

    def test_meteorological_and_certificate_events_do_not_supply_allocation_dates(self):
        met = [o for k in ['chubu', 'komaki'] for o in self.cases[k]['observations'] if o['namespace'] == 'MET']
        self.assertEqual({'RJGG', 'RJNN', 'RJNA'}, {o['code'] for o in met})
        self.assertTrue(all(not o['allocationDateProved'] for o in met))
        caa = self.sources['uk-caa-dsa-letter']
        self.assertEqual('2022-12-12', caa['certificateSurrenderEffectiveOn'])
        self.assertFalse(caa['codeWithdrawalEstablished'])
        self.assertEqual([], self.cases['doncaster']['observations'])

    def test_korean_full_local_dates_exclude_both_partial_edges(self):
        zone = ZoneInfo('Asia/Seoul')
        left = dt.datetime.fromisoformat('2025-04-16T16:00:00+00:00').astimezone(zone)
        right = dt.datetime.fromisoformat('2025-05-14T16:00:00+00:00').astimezone(zone)
        self.assertEqual(1, left.hour)
        self.assertEqual(1, right.hour)
        first = left.date() + dt.timedelta(days=1)
        end = right.date()
        self.assertEqual('2025-04-18', first.isoformat())
        self.assertEqual('2025-05-15', end.isoformat())
        self.assertEqual(27, (end - first).days)
        self.assertFalse(self.screen['productionEligible'])
        self.assertIsNone(self.screen['physicalIdentityResearch']['independentHumanReviewer'])

    def test_notam_duplicates_reference_codes_and_archive_limits_remain_visible(self):
        groups = {r['location']: r for r in self.screen['notamGroups']}
        self.assertEqual(1061, sum(g['recordsScreened'] for g in groups.values()))
        self.assertEqual({'A0112/24': 2}, groups['RKSI']['repeatedNoticeNumbers'])
        duplicates = [r for r in groups['RKSI']['records'] if r['notamNo'] == 'A0112/24']
        self.assertEqual(1, len({r['fullTextSha256'] for r in duplicates}))
        self.assertEqual(2, len({r['serverRecordId'] for r in duplicates}))
        flags = [r for r in groups['RKSI']['records'] if 'possible_code_or_name_change' in r['flags']]
        self.assertEqual(3, len(flags))
        self.assertTrue(all('not a four-letter' in r['researchInterpretation'] for r in flags))
        sup = self.screen['supplementScreening']
        self.assertEqual(51, sup['relevantRetrievalUrls'])
        self.assertEqual(49, sup['distinctRecoveredOriginals'])
        self.assertIn('2023-10-31', self.screen['notamQueryCoverage']['earlierHistoryAvailability'])


if __name__ == '__main__':
    unittest.main()
