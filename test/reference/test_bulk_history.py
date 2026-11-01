"""Bulk ingestion tests: no airport allowlist, no invented effective dates."""
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'scripts/reference'))
from common import canonical, digest, stable_id
from bulk_history import build, lookup, _relation, _code


def write_gz(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as comp:
            for row in rows:
                comp.write((canonical(row)+'\n').encode())


def write_manifest(directory, files):
    (directory/'manifest.json').write_text(json.dumps({'files':{p.name:{'sha256':digest(p)} for p in files}}))


class WorldBulkHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.ref,self.triage,self.discovery = [root/p for p in ('reference','triage','discovery')]
        for folder in (self.ref,self.triage,self.discovery): folder.mkdir()
        self.db = root/'world.sqlite'
        self.curated = root/'airports.json'
        def loc(coord,kind='snapshot', candidate=None):
            return {'locationId':stable_id('loc_',coord),'coordinates':coord,'kind':kind,
                    'candidateIds':[candidate] if candidate else [],'curatedAirportIds':[]}
        old={'latitude':3.5,'longitude':107.0}
        new={'latitude':3.8,'longitude':108.0}
        r1 = {
            'referenceId':'ref_old','sourceId':'ourairports','sourceEntityId':'50','name':'Old Site',
            'country':'KR','presentAtSnapshot':True,'locations':[loc(old,'snapshot')],
            'curatedAirportIds':[],'identifiers':{'IATA':'KTI','ICAO':None,'GPS':'ZZZZ','LOCAL':None,'IDENT':None},
            'observedAt':'2026-10-26T00:00:00Z','observation':{'revision':'a'*40,'blob':'b'*40},
            'historicalIdentifiers':[]}
        r2 = {
            **r1,'referenceId':'ref_new','sourceEntityId':'51','name':'New Site',
            'locations':[loc(new)],'identifiers':{**r1['identifiers'],'GPS':None}}
        # A reused source record must NOT relocate a historic code to its modern site.
        r3 = {
            **r1,'referenceId':'ref_repurposed','sourceEntityId':'52','name':'Repurposed Row',
            'locations':[loc(new),loc(old,'unresolved_transition_location','cand_old')],
            'identifiers':{'IATA':'NOW','ICAO':None,'GPS':None,'LOCAL':None,'IDENT':None},
            'historicalIdentifiers':[{'sourceId':'ourairports','scheme':'IATA','code':'OLD',
               'candidateId':'cand_old','side':'before','commit':'c'*40,'blob':'d'*40,
               'revisionObservedAt':'2025-01-02T00:00:00Z'}]}
        shard=self.ref/'records.a.jsonl.gz'
        write_gz(shard,[r1,r2,r3])
        write_manifest(self.ref,[shard, *(self._empty_shard(letter) for letter in '0123456789bcdef')])
        event = {'eventGroupId':'lead1','country':'KR','name':'Some source revision',
            'physicalMatch':{'referenceId':'ref_old'},'classifications':['code_change_observation'],
            'status':'awaiting_primary_evidence','members':[{'candidateId':'cand_event','sourceId':'ourairports',
            'sourceEntityId':'50','firstRevisionObservedAt':'2020-02-01T00:00:00Z'}]}
        groups=self.triage/'groups.jsonl.gz'
        write_gz(groups,[event]);write_manifest(self.triage,[groups])
        cand=self.discovery/'ourairports.candidates.a.jsonl.gz'
        write_gz(cand,[{'candidateId':'cand_event','changes':{'iata':['ABC','DEF'],'icao':['ABCD','WXYZ']},
                     'types':['iata_change','icao_change']}])
        write_manifest(self.discovery,[cand])
        airport1={'airportId':'apt_old','name':{'value':'Qingdao Liuting'},
                  'coordinates':{'value':{'latitude':36.0,'longitude':120.0}}}
        airport2={'airportId':'apt_new','name':{'value':'Qingdao Jiaodong'},
                  'coordinates':{'value':{'latitude':36.4,'longitude':120.1}}}
        self.curated.write_text(json.dumps({'dataVersion':'0.10.0','airports':[airport1,airport2],
             'assignments':[
             {'assignmentId':'tao-old','airportId':'apt_old','scheme':'IATA','code':'TAO',
              'validFrom':{'earliest':None,'latest':'2016-01-01'},
              'validTo':{'earliest':'2021-08-12','latest':'2021-08-12'},
              'verifiedOn':'2026-01-01','evidenceType':'continuity_inference','sourceIds':['primary-old']},
             {'assignmentId':'tao-new','airportId':'apt_new','scheme':'IATA','code':'TAO',
              'validFrom':{'earliest':'2021-08-12','latest':'2021-08-12'},
              'validTo':{'earliest':'2026-10-25','latest':None},
              'verifiedOn':'2026-01-01','evidenceType':'continuity_inference','sourceIds':['primary-new']}]},
             ensure_ascii=False))

    def _empty_shard(self, letter):
        path = self.ref / f'records.{letter}.jsonl.gz'
        write_gz(path, [])
        return path

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        return build(self.db,self.ref,self.triage,self.discovery,self.curated,strict=True)

    def test_ingests_full_fixture_population_and_history(self):
        metrics=self.build()['metrics']
        self.assertEqual(metrics['referenceRecords'],3)
        self.assertEqual(metrics['formalCodeAssignments'],2)
        self.assertEqual(metrics['indexedEventGroups'],1)
        self.assertEqual(metrics['indexedTransitionCodeObservations'],4)
        self.assertEqual(lookup(self.db,'ABC')['transitionLeadGroupCount'],1)
        self.assertEqual(lookup(self.db,'WXYZ',scheme='ICAO')['transitionLeadGroupCount'],1)
        self.assertEqual(lookup(self.db,'ZZZZ',scheme='GPS')['referenceObservationCount'],1)
        self.assertEqual(lookup(self.db,'ZZZZ',scheme='ICAO')['status'],'not_found')

    def test_curated_code_time_and_reference_uncertainty(self):
        self.build()
        old=lookup(self.db,'TAO',at='2020-01-01')
        self.assertEqual(old['status'],'resolved')
        self.assertEqual(old['resolvedAirportId'],'apt_old')
        self.assertEqual(lookup(self.db,'TAO',at='2021-08-12')['status'],'resolved')
        latest=lookup(self.db,'TAO',at='2027-01-01')
        self.assertEqual(latest['status'],'uncertain')
        rep=lookup(self.db,'KTI',at='2020-01-01')
        self.assertEqual(rep['status'],'historical_observations_only')
        self.assertEqual(rep['referenceObservationCount'],2)
        self.assertIsNone(rep['resolvedAirportId'])

    def test_historical_repurposed_code_links_only_changed_site(self):
        self.build()
        r=lookup(self.db,'OLD',at='2020-01-01')['referenceObservations']
        self.assertEqual(len(r),1)
        self.assertAlmostEqual(r[0]['latitude'],3.5)
        self.assertEqual(r[0]['kind'],'source_transition')
        self.assertEqual(r[0]['side'],'before')
        self.assertEqual(r[0]['revision_observed_at'],'2025-01-02T00:00:00Z')
        self.assertEqual(lookup(self.db,'OLD',at='2020-01-01')['status'],'historical_observations_only')

    def test_full_rebuild_reproducible_and_invalid_date_fails(self):
        a=self.build()['databaseSha256']
        self.assertEqual(a,self.build()['databaseSha256'])
        with self.assertRaises(ValueError):lookup(self.db,'TAO',at='2020-02-30')
        with self.assertRaises(ValueError):lookup(self.db,'TAO',at='2020-1-1')
        with self.assertRaises(ValueError):lookup(self.db,'tao',limit=0)
        self.assertEqual(_code('ICAO','rksi'),'RKSI')


if __name__=='__main__':unittest.main()
