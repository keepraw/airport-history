"""Original custody, open cross-site bounds, immutable history and pending admission."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/evidence'))
import transfer_batch as tb


class TransferTests(unittest.TestCase):
    def test_two_sided_associations_are_not_allocation_dates(self):
        a,s,f,allfacts=tb.verify()
        complete=[c for c in a['cases'] if c['classification']=='complete_same_iata_candidate']
        self.assertEqual({c['caseKey'] for c in complete},{'bohol','lianyungang','yibin'})
        for c in complete:
            self.assertNotEqual(c['oldSite']['airportId'],c['newSite']['airportId'])
            self.assertTrue(c['oldSite']['iataObservations'] and c['newSite']['iataObservations'])
        spring=f['lianyungang-old-spring-2020-09-21']
        _,spans=tb.verify_sources()
        self.assertEqual(spans[spring['citationIds'][1]][1]['representation'],'decoded_html')
        self.assertIn('href=',spans[spring['citationIds'][1]][1]['quote'])
        self.assertEqual(f['lianyungang-new-quality']['observation']['earliest'],'2023-05-01')
        self.assertEqual(s['p0-cn-quality-2022']['dataPeriod'],['2022-01-01','2022-12-31'])
        self.assertEqual(f['bohol-old-schedule-2017']['observation']['earliest'],'2017-10-01')
        self.assertEqual(s['p0-bohol-factbook-2017']['printedEdition'],'2016')
        self.assertIsNone(f['lyg-old-guide-undated']['observation'])

    def test_pending_records_cannot_pass_admission_and_formal_is_identical(self):
        a,s,f,_=tb.verify();proposed,dossier=tb.propose(a,s,f)
        base=tb.read(ROOT/'test/curated-0.8.0.json');batches=tb.packets(a,s,dossier)
        for collection,key in tb.FIELDS:
            now={r[key]:r for r in proposed[collection]}
            self.assertTrue(all(now[r[key]]==r for r in base[collection]))
        with self.assertRaisesRegex(ValueError,'explicit claim review'):
            tb.gb.validate_admission(base,proposed,batches,dossier)
        self.assertTrue(all(d['decision']=='pending' and d['reviewer'] is None for d in dossier))
        formal={r['assignmentId'] for r in base['assignments']}
        self.assertTrue(all(r['verificationStatus']=='pending' and r['verifiedOn'] is None for r in proposed['assignments'] if r['assignmentId'] not in formal))
        self.assertTrue(all(len(b['events'])<=20 for b in batches))
        # Existing research owners are supplemented, not duplicated.
        supplements=[e for b in batches for e in b['events'] if 'transferSupplement' in e]
        self.assertEqual(len(supplements),5)
        self.assertEqual(len({e['eventGroupId'] for b in batches for e in b['events']}),sum(len(b['events']) for b in batches))

    def test_actual_resolver_preserves_open_cross_site_uncertainty(self):
        rows=tb.read(tb.OUT/'country-year.json')['rows']
        # A dated suspension or opening statement is not a dated IATA observation.
        self.assertFalse(any(r['datedCodeObservationInspected'] for r in rows if r['caseKey']=='ankang'))
        c=tb.read(tb.OUT/'transfer-coverage.json')
        self.assertEqual(c['totals']['incrementalResolvedDates'],0)
        self.assertEqual(c['totals']['previousHypotheticalResolvedDatesNowUncertain'],61)
        self.assertEqual(c['totals']['confirmedConflictDates'],0)
        self.assertEqual(c['totals']['changedPublishedResolvedQueries'],0)
        self.assertGreater(c['formalReferenceRegressionQueries'],17000)
        for case,code in [('bohol','TAG'),('lianyungang','LYG'),('yibin','YBP')]:
            row=c['cases'][case]['byCode'][code]
            self.assertEqual(row['oldResolvedDates']+row['newResolvedDates'],0)
            self.assertEqual(row['crossSitePossibleDates'],row['uncertainDates'])
            self.assertEqual(row['windows'][0]['from'],'2015-01-01')
            self.assertEqual(row['windows'][-1]['toExclusive'],'2026-10-30')

    def test_techo_uses_formal_kti_not_invented_pnh_and_zhanjiang_old_is_blocked(self):
        a,s,f,_=tb.verify();p,_=tb.propose(a,s,f)
        c=next(c for c in a['cases'] if c['caseKey']=='phnom-penh')
        self.assertFalse(c['sameIataLead'])
        self.assertFalse(any(r['airportId']==c['newSite']['airportId'] and r['code']=='PNH' for r in p['assignments']))
        z=next(c for c in a['cases'] if c['caseKey']=='zhanjiang')
        self.assertIsNone(z['oldSite']['coordinates'])
        self.assertNotIn(z['oldSite']['airportId'],{r['airportId'] for r in p['airports']})

    def test_offline_rebuild_reproduces_every_output_without_network(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            out=Path(folder)
            with patch('urllib.request.urlopen',side_effect=AssertionError('Offline build used network')):
                tb.build(out);tb.validate(out)
            def files(root):return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(files(out),files(tb.OUT))

    def test_tampered_retained_quote_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            target=Path(folder);shutil.copytree(tb.BASE,target,dirs_exist_ok=True)
            path=next((target/'excerpts').glob('*.json'));path.write_text(path.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'Changed retained quotation'):tb.verify_sources(target)

    def test_collector_resume_retry_and_recovery_rejects_changed_bytes(self):
        raw=b'<html><p>Invented airport evidence for a collector fixture, with sufficient text for extraction. This is not a third-party publication.</p><p>OLD XYZ</p></html>'
        entry={'sourceId':'fixture-one','url':'https://example.test/original','originalPublicationKey':'fixture-publication',
               'title':'Invented original','publisher':'Invented publisher','sourceType':'primary',
               'citations':[{'citationId':'fixture-quote','representation':'normalized_text','quote':'OLD XYZ'}]}
        class Response:
            def __init__(self,body):self.body=body
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return self.body[:n]
            def geturl(self):return entry['url']
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            root=Path(folder);directory=root/'snapshot';cache=root/'private';directory.mkdir()
            tb.gb.write(directory/'catalog.json',{'sources':[entry]})
            with patch('urllib.request.urlopen',side_effect=OSError('temporary unavailable')),patch('time.sleep'):
                self.assertEqual(tb.fetch(directory=directory,cache=cache)[0]['status'],'failed')
            with patch('urllib.request.urlopen',return_value=Response(raw)) as request,patch('time.sleep'):
                self.assertEqual(tb.fetch(directory=directory,cache=cache),[]);request.assert_not_called()
                rows=tb.fetch(directory=directory,cache=cache,retry_failures=True)
                self.assertEqual(rows[0]['status'],'original_hash_verified')
                self.assertEqual(tb.fetch(directory=directory,cache=cache),[])
            locked=(directory/'source-lock.json').read_bytes()
            tb.verify_sources(directory,cache)
            with patch('urllib.request.urlopen',return_value=Response(raw+b' changed')),patch('time.sleep'):
                result=tb.fetch(directory=directory,cache=cache,recover=True)
            self.assertEqual(result[0]['status'],'failed')
            self.assertIn('Original changed',result[0]['error'])
            self.assertEqual((directory/'source-lock.json').read_bytes(),locked)
            self.assertEqual(list(directory.rglob('*.raw')),[])


if __name__=='__main__':unittest.main()
