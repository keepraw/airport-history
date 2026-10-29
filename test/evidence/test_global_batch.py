"""Global evidence regressions: originals, namespaces, replay and admission."""
import copy
import gzip
import importlib.util
import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('global_batch', ROOT/'scripts/evidence/global_batch.py')
gb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gb)


class GlobalBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assessment = json.loads((gb.BASE/'assessments.json').read_text())
        cls.proposed = json.loads((gb.OUT/'proposed-data.json').read_text())
        cls.formal = json.loads((ROOT/'data/airports.json').read_text())
        cls.dossier = json.loads((gb.OUT/'dossier.json').read_text())

    def test_complete_offline_rebuild_is_byte_identical(self):
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            output = Path(folder)
            with patch('urllib.request.urlopen', side_effect=AssertionError('Offline build attempted network')):
                gb.build(output)
                gb.validate(output)
            committed = {str(p.relative_to(gb.OUT)):p.read_bytes() for p in gb.OUT.rglob('*') if p.is_file()}
            rebuilt = {str(p.relative_to(output)):p.read_bytes() for p in output.rglob('*') if p.is_file()}
            self.assertEqual(committed,rebuilt)

    def test_retained_excerpts_authenticate_original_hash_provenance(self):
        count = 0
        with tempfile.TemporaryDirectory() as folder:
            for source,text in gb.locked(gb.BASE):
                self.assertEqual(source['retention'],'metadata_and_cited_excerpts')
                retained=gb.BASE/source['retainedPath']
                self.assertEqual(gb.sha(retained.read_bytes()),source['retainedSha256'])
                self.assertEqual(json.loads(retained.read_text())['originalSha256'],source['originalSha256'])
                self.assertFalse((gb.BASE/source['inputPath']).exists())
                self.assertFalse((gb.BASE/source['textPath']).exists())
                count += 1
        self.assertGreater(count,30)

    def test_wrong_original_and_path_escape_are_rejected(self):
        lock = json.loads((gb.BASE/'source-lock.json').read_text())
        source = copy.deepcopy(lock['sources'][0])
        source.pop('retention')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            gb.write(root/'source-lock.json',{'sources':[source]})
            source['inputPath']='../escape.gz'
            gb.write(root/'source-lock.json',{'sources':[source]})
            with self.assertRaisesRegex(ValueError,'escapes'):
                list(gb.locked(root))
            source['inputPath']='original.gz'
            (root/'original.gz').write_bytes(b'wrong')
            gb.write(root/'source-lock.json',{'sources':[source]})
            with self.assertRaisesRegex(ValueError,'Changed compressed'):
                list(gb.locked(root))

    def test_navaid_or_cross_site_code_cannot_be_substituted(self):
        facts={f['factId']:f for f in self.assessment['facts']}
        hsr=next(a for a in self.assessment['assignments'] if a['code']=='HSR')
        wrong=copy.deepcopy(hsr);wrong['factIds']=['rajkot-aip']
        with self.assertRaisesRegex(ValueError,'namespace'):
            gb.check_binding(wrong,facts)
        wrong=copy.deepcopy(hsr);wrong['siteKey']='rajkot-old'
        with self.assertRaisesRegex(ValueError,'physical-site'):
            gb.check_binding(wrong,facts)
        for a in self.assessment['assignments']:
            gb.check_binding(a,facts)

    def test_rejected_http_200_responses_support_no_fact(self):
        loaded={s['sourceId']:(s,t) for s,t in gb.locked(gb.BASE)}
        bad={'sourceId':'id-mentawai-actual','factId':'fake','quote':'Request Rejected','locator':'body'}
        with self.assertRaisesRegex(ValueError,'Error response'):
            gb.citation(bad,loaded)
        self.assertNotIn('id-mentawai-actual',{f['sourceId'] for f in self.assessment['facts']})

    def test_pending_records_fail_real_admission_gate(self):
        batches=list(gb.read_jsonl(gb.OUT/'review-packets.jsonl.gz'))
        with self.assertRaisesRegex(ValueError,'explicit claim review'):
            gb.validate_admission(self.formal,self.proposed,batches,self.dossier)
        self.assertTrue(all(d['decision']=='pending' and d['reviewer'] is None for d in self.dossier))

    def test_current_formal_and_frozen_snapshot_are_separate(self):
        self.assertEqual(self.formal['dataVersion'],'0.8.0')
        self.assertEqual([len(self.formal[c]) for c in ['airports','assignments','names','sources']],[27,43,3,77])
        for c,field in [('airports','airportId'),('assignments','assignmentId'),('names','nameId'),('sources','sourceId')]:
            byid={r[field]:r for r in self.proposed[c]}
            self.assertTrue(all(byid[r[field]]==r for r in self.formal[c]))
        frozen=ROOT/'test/curated-0.7.0.json'
        self.assertEqual(gb.digest(frozen),'31c5735b333881d7afdd527fe4af1db8e28413d5bba114fbf88a4aad0809cff7')

    def test_multiple_bounded_batches_and_unique_owners(self):
        batches=list(gb.read_jsonl(gb.OUT/'review-packets.jsonl.gz'))
        self.assertGreater(len(batches),1)
        self.assertTrue(all(1<=len(b['events'])<=20 and b['preparationOnly'] for b in batches))
        ids=[r for b in batches for e in b['events'] for r in e['proposedRecordIds']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),{d['recordId'] for d in self.dossier})

    def test_external_record_number_cannot_automatically_merge_physical_sites(self):
        existing={'12':{'airportId':'published-permanent-id'}}
        with self.assertRaisesRegex(ValueError,'no automatic merge'):
            gb.existing_identity({'ourAirports':'12','name':'Same name'},existing)
        self.assertEqual(gb.existing_identity({'ourAirports':'12','existingAirportId':'published-permanent-id'},existing),existing['12'])

    def test_collector_resumes_and_identifies_identical_original_bytes(self):
        raw=b'<html><body>Official airport notice: dated code and physical location. '+b'Original factual text. '*10+b'</body></html>'
        def response(*args,**kwargs):
            stream=io.BytesIO(raw)
            stream.geturl=lambda:'https://official.example/notice'
            return stream
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/'archive'
            rows=[{'sourceId':i,'url':'https://official.example/'+i,'publisher':'Authority','title':'Original','sourceFamily':'authority','expectedText':['Official airport notice'],'license':{'id':'test','note':'Test fixture'}} for i in ['one','two']]
            gb.write(root/'catalog.json',{'sources':rows})
            with patch.object(gb,'BASE',root),patch('urllib.request.urlopen',side_effect=response) as network,patch('time.sleep'):
                gb.fetch(output,limit=1)
                gb.fetch(output)
                gb.fetch(output)
                self.assertEqual(network.call_count,2)
            sources=json.loads((output/'source-lock.json').read_text())['sources']
            self.assertEqual(sources[1]['sameOriginalContentAs'],['one'])
            self.assertEqual(sources[1]['originalPublicationKey'],sources[0]['originalPublicationKey'])

    def test_collector_rejects_duplicate_and_escaping_catalog_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for rows in [[{'sourceId':'one','url':'https://official.example'}]*2,[{'sourceId':'../escape','url':'https://official.example'}]]:
                gb.write(root/'catalog.json',{'sources':rows})
                with patch.object(gb,'BASE',root),patch('urllib.request.urlopen',side_effect=AssertionError('Network before catalog validation')):
                    with self.assertRaisesRegex(ValueError,'safe source IDs'):
                        gb.fetch(root/'archive')

    def test_null_event_years_never_use_revision_year(self):
        queue=list(gb.read_jsonl(gb.OUT/'queue.jsonl.gz'))
        self.assertEqual(len(queue),100)
        screened=[r for r in queue if r['researchStatus']=='screened_only']
        self.assertTrue(screened)
        self.assertTrue(all(r['eventDate'] is None for r in screened))
        report=json.loads((gb.OUT/'coverage-by-country-year.json').read_text())
        self.assertEqual(sum(r['humanApproved']+r['formallyAdmitted'] for r in report['rows']),0)
        self.assertIn('not_assessed',report['uncollectedCountries'])


if __name__=='__main__':
    unittest.main()
