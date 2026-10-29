"""Priority-market source custody, negative admission, balancing and offline replay."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/evidence'))
import market_batch as mb


class MarketTests(unittest.TestCase):
    def test_country_balance_does_not_reward_one_easy_source(self):
        a,_,_=mb.verify()
        prototype=copy.deepcopy(a['cases'][0])
        rows=[]
        for country,n in [('IN',80),('CN',8),('US',8),('GB',8),('JP',8),('KR',8)]:
            for i in range(n):
                c=copy.deepcopy(prototype);c.update(country=country,caseKey=country+str(i));rows.append(c)
        q=mb.rank(rows,'A',limit=30)
        self.assertEqual(len(q['selected']),30)
        self.assertLessEqual(sum(c['country']=='IN' for c in q['selected']),11)
        self.assertTrue(q['deferred'])
        # A missing original never removes a high-value lead from the queue.
        rows[0]['factIds']=[]
        self.assertIn(rows[0]['caseKey'],{c['caseKey'] for c in mb.rank(rows,'A',limit=30)['selected']})

    def test_pending_gate_and_permanent_formal_records(self):
        a,s,f=mb.verify();proposed,dossier=mb.propose(a,s,f)
        base=mb.read(ROOT/'data/airports.json')
        for collection,key in [('airports','airportId'),('assignments','assignmentId'),('names','nameId'),('sources','sourceId')]:
            now={r[key]:r for r in proposed[collection]}
            self.assertTrue(all(now[r[key]]==r for r in base[collection]))
        batches=mb.review_packets(a,s,f,dossier)
        with self.assertRaisesRegex(ValueError,'explicit claim review'):
            mb.gb.validate_admission(base,proposed,batches,dossier)
        self.assertTrue(all(d['decision']=='pending' and d['reviewer'] is None for d in dossier))
        self.assertEqual(len(a['cases']),60)
        self.assertEqual(len({c['caseKey'] for c in a['cases']}),60)
        self.assertTrue(all(c['factIds'] for c in a['cases']))

    def test_retained_quote_or_hash_tampering_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            target=Path(folder)
            import shutil
            for p in mb.BASE.glob('*.json'):shutil.copy2(p,target/p.name)
            shutil.copytree(mb.BASE/'excerpts',target/'excerpts')
            a=mb.read(target/'assessments.json');a['facts'][0]['quote']='fabricated claim'
            mb.gb.write(target/'assessments.json',a)
            with patch.object(mb,'BASE',target):
                with self.assertRaisesRegex(ValueError,'retained original span'):mb.verify()

    def test_all_outputs_rebuild_without_network(self):
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            out=Path(folder)
            with patch('urllib.request.urlopen',side_effect=AssertionError('Network during offline build')):
                mb.build(out);mb.validate(out)
            def files(root):return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(files(out),files(mb.OUT))

    def test_old_and_new_chinese_sites_cannot_share_permanent_identity(self):
        a,_,_=mb.verify()
        pairs={c['caseKey']:c['siteKeys'] for c in a['cases'] if len(c['siteKeys'])==2}
        sites={s['siteKey']:s for s in a['sites']}
        for keys in pairs.values():
            self.assertNotEqual(sites[keys[0]]['proposedAirportId'],sites[keys[1]]['proposedAirportId'])
            self.assertNotEqual(sites[keys[0]]['ourAirports'],sites[keys[1]]['ourAirports'])


if __name__=='__main__':unittest.main()
