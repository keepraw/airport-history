"""Guard the physical-identity and date boundaries of public-data enrichment."""
import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('public_data',Path(__file__).resolve().parents[2]/'scripts/evidence/public_data.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class Matching(unittest.TestCase):
 def setUp(self):
  self.ref={'referenceId':'r1','sourceEntityId':'123','identifiers':{'IATA':'AAA','ICAO':'AAAA'},'historicalIdentifiers':[],'locations':[{'coordinates':{'latitude':1.0,'longitude':1.0}}],'country':'US','region':'US-CA','name':'Test Airport','curatedAirportIds':['permanent-id']}
  self.entity={'qid':'Q1','codes':{'IATA':['AAA'],'ICAO':[]},'coordinates':[{'latitude':1.001,'longitude':1.001}],'names':['Test Airport'],'countries':['US']}
 def test_code_and_location_match_preserves_id_without_verifying_history(self):
  r=p.match([self.ref],[self.entity])[0];self.assertEqual(r['matches'][0]['airportIds'],['permanent-id']);self.assertFalse(r['matches'][0]['physicalIdentityVerified']);self.assertFalse(r['formalAdmission'])
 def test_code_alone_cannot_merge_distant_physical_sites(self):
  self.entity['coordinates']=[{'latitude':20,'longitude':20}]
  r=p.match([self.ref],[self.entity])[0];self.assertFalse(r['matches']);self.assertEqual(len(r['distantCodeMatches']),1)
 def test_missing_coordinates_cannot_establish_identity(self):
  self.entity['coordinates']=[];self.assertFalse(p.match([self.ref],[self.entity])[0]['matches'])
 def test_conflicting_country_prevents_matching(self):
  self.entity['countries']=['CA'];self.assertFalse(p.match([self.ref],[self.entity])[0]['matches'])
 def test_historical_code_still_requires_location(self):
  self.ref['identifiers']['IATA']=None;self.ref['historicalIdentifiers']=[{'scheme':'IATA','code':'AAA'}]
  self.assertEqual(len(p.match([self.ref],[self.entity])[0]['matches']),1)
 def test_osm_match_retains_license_family(self):
  o={'type':'way','id':123,'center':{'lat':1,'lon':1},'tags':{'iata':'AAA','name':'Test Airport'}}
  r=p.match([self.ref],[o],True)[0];self.assertEqual(r['sourceFamily'],'osm');self.assertFalse(r['formalAdmission'])

class Sharding(unittest.TestCase):
 def setUp(self):
  import tempfile
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.directory=Path(self.tmp.name);self.path=self.directory/'records.jsonl.gz'
  self.records=[b'{ "id": 0 }\n', '{"id":1,"name":"東京"}\n'.encode(),b'{"id":2}\n',b'{"id":3}\n']
 def test_deterministic_gzip_and_sequential_names(self):
  first=p.write_jsonl(self.path,self.records,limit=32)
  before={f.name:f.read_bytes() for f in p.dataset_paths(self.path)}
  second=p.write_jsonl(self.path,self.records,limit=32)
  self.assertEqual(first,second);self.assertEqual(before,{f.name:f.read_bytes() for f in p.dataset_paths(self.path)})
  self.assertEqual(list(before),[f'records.{i:03d}.jsonl.gz' for i in range(len(before))])
  for raw in before.values():self.assertEqual(raw[3:8],b'\0'*5)
 def test_size_order_and_exact_serialized_record_preservation(self):
  import gzip
  p.write_jsonl(self.path,self.records,limit=32)
  contents=[gzip.decompress(f.read_bytes()) for f in p.dataset_paths(self.path)]
  self.assertTrue(all(len(content)<=32 for content in contents))
  self.assertEqual(b''.join(contents),b''.join(self.records))
  self.assertEqual([line for content in contents for line in content.splitlines(keepends=True)],self.records)
  self.assertEqual([r['id'] for r in p.rows(self.path)],[0,1,2,3])
 def test_manifest_hash_sizes_record_counts_and_reconstruction(self):
  import gzip,hashlib
  meta=p.write_jsonl(self.path,self.records,limit=32)
  self.assertEqual(meta['uncompressedSha256'],hashlib.sha256(b''.join(self.records)).hexdigest())
  self.assertEqual(meta['recordCount'],len(self.records));self.assertEqual(meta['uncompressedBytes'],sum(map(len,self.records)))
  for shard in meta['shards']:
   raw=(self.directory/shard['path']).read_bytes();content=gzip.decompress(raw)
   self.assertEqual(shard['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(shard['compressedBytes'],len(raw));self.assertEqual(shard['uncompressedBytes'],len(content));self.assertEqual(shard['recordCount'],len(content.splitlines()))
  p.validate_shards(self.directory)
 def test_manifest_tampering_is_rejected(self):
  import json
  p.write_jsonl(self.path,self.records,limit=32)
  index=self.directory/'jsonl-shards.json';data=json.loads(index.read_text());data['datasets'][self.path.name]['shards'][0]['recordCount']+=1;index.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'integrity'):p.validate_shards(self.directory)
 def test_reversed_manifest_order_is_rejected(self):
  import json
  p.write_jsonl(self.path,self.records,limit=32)
  index=self.directory/'jsonl-shards.json';data=json.loads(index.read_text());data['datasets'][self.path.name]['shards'].reverse();index.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'ordering'):p.validate_shards(self.directory)
 def test_oversized_record_does_not_replace_existing_dataset(self):
  p.write_jsonl(self.path,[self.records[0]])
  before=self.path.read_bytes();index=(self.directory/'jsonl-shards.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'Individual JSONL record'):p.write_jsonl(self.path,[b'{"value":"'+b'x'*40+b'"}\n'],limit=32)
  self.assertEqual(self.path.read_bytes(),before);self.assertEqual((self.directory/'jsonl-shards.json').read_bytes(),index)
 def test_shard_gaps_and_ambiguous_monolith_are_rejected(self):
  p.write_jsonl(self.path,self.records,limit=32)
  parts=p.dataset_paths(self.path);parts[0].rename(self.path)
  with self.assertRaisesRegex(ValueError,'Both monolith'):p.dataset_paths(self.path)
  self.path.unlink()
  with self.assertRaisesRegex(ValueError,'Non-contiguous'):p.dataset_paths(self.path)
 def test_rewrite_removes_obsolete_monolith_and_shards(self):
  p.write_jsonl(self.path,self.records)
  self.assertTrue(self.path.exists())
  p.write_jsonl(self.path,self.records,limit=32);self.assertFalse(self.path.exists())
  p.write_jsonl(self.path,self.records[:1]);self.assertEqual(p.dataset_paths(self.path),[self.path]);self.assertFalse(list(self.directory.glob('records.[0-9]*.jsonl.gz')))
 def test_exact_limit_empty_dataset_and_unterminated_final_record(self):
  import gzip
  p.write_jsonl(self.path,[self.records[0]],limit=len(self.records[0]));self.assertEqual(gzip.decompress(self.path.read_bytes()),self.records[0])
  p.write_jsonl(self.path,[]);self.assertEqual(gzip.decompress(self.path.read_bytes()),b'');p.validate_shards(self.directory)
  p.write_jsonl(self.path,[b'{"id":7}']);self.assertEqual(gzip.decompress(self.path.read_bytes()),b'{"id":7}')
 def test_frozen_package_manifests_and_original_reconstruction(self):
  import gzip,hashlib,json
  index=p.validate_shards(p.OUT)
  original=json.loads((p.OUT/'shard-reconstruction.json').read_text())
  for name,record in original['datasets'].items():
   raw=b''.join(gzip.decompress(part.read_bytes()) for part in p.dataset_paths(p.OUT/name))
   self.assertEqual(hashlib.sha256(raw).hexdigest(),record['uncompressedSha256']);self.assertEqual(len(raw),record['uncompressedBytes']);self.assertEqual(len(raw.splitlines()),record['recordCount'])
   self.assertEqual(index['datasets'][name]['uncompressedSha256'],record['uncompressedSha256'])
  for entry in json.loads((p.OUT/'artifact-manifest.json').read_text())['artifacts']:self.assertEqual(p.artifact_metadata(p.OUT/entry['path']),entry)

if __name__=='__main__':unittest.main()
