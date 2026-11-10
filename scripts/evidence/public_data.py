#!/usr/bin/env python3
"""One-task, checkpointed public-airport acquisition and enrichment. No formal writes."""
import threading
import argparse, concurrent.futures as futures, datetime as dt, gzip, hashlib, json, math, re, time, urllib.parse, urllib.request
from pathlib import Path
from collections import defaultdict, Counter
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/evidence/global-public-data'
CACHE=ROOT/'work/global-public-data'
UA='KeeprawAirportHistory/1.0 (https://github.com/keepraw/airport-history; public historical research)'
HORIZON=['1970-01-01','2026-11-10']
REQUEST_LOCK=threading.Lock()
NEXT_REQUEST=0.0
def dump(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
MAX_SHARD_BYTES=8*1024*1024

def dataset_paths(path):
 """Resolve a logical JSONL name without accepting ambiguous or gapped shards."""
 path=Path(path)
 parts=sorted(path.parent.glob(path.name.removesuffix('.jsonl.gz')+'.[0-9][0-9][0-9].jsonl.gz'))
 if path.exists():
  if parts:raise ValueError('Both monolith and shards exist: '+str(path))
  return [path]
 if not parts:raise FileNotFoundError(path)
 expected=[path.with_name(path.name.removesuffix('.jsonl.gz')+f'.{i:03d}.jsonl.gz') for i in range(len(parts))]
 if parts!=expected:raise ValueError('Non-contiguous shards: '+str(path))
 return parts

def rows(path):
 for part in dataset_paths(path):
  with gzip.open(part,'rt',encoding='utf-8') as f:
   for line in f:yield json.loads(line)

def artifact_metadata(path):
 raw=path.read_bytes();content=gzip.decompress(raw) if path.name.endswith('.gz') else raw
 return {'path':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
         'compressedBytes':len(raw),'uncompressedBytes':len(content),
         'recordCount':len(content.splitlines()) if path.name.endswith('.jsonl.gz') else None}

def write_jsonl(path,records,limit=MAX_SHARD_BYTES):
 """Preserve raw record bytes/order; deterministically shard at record boundaries."""
 import tempfile
 path=Path(path)
 if not path.name.endswith('.jsonl.gz') or not 0<limit<=MAX_SHARD_BYTES:raise ValueError('Invalid JSONL path or shard limit')
 path.parent.mkdir(parents=True,exist_ok=True)
 # Stage all data before replacing a valid dataset, including on oversized records.
 with tempfile.TemporaryDirectory(prefix='.public-jsonl-',dir=path.parent) as scratch:
  temporary=[];stream=None;raw=None;size=0;total=0;count=0;digest=hashlib.sha256();previous_ended=True
  def begin():
   dest=Path(scratch)/f'{len(temporary):03d}.gz';temporary.append(dest)
   raw=dest.open('wb');return raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0)
  try:
   raw,stream=begin()
   for record in records:
    if not isinstance(record,bytes) or not record or b'\n' in record.rstrip(b'\n') or record.endswith(b'\n\n'):raise ValueError('Expected one serialized JSONL record')
    if len(record)>limit:raise ValueError('Individual JSONL record exceeds shard limit')
    if not previous_ended:raise ValueError('Unterminated JSONL record before another record')
    json.loads(record);previous_ended=record.endswith(b'\n')
    if size and size+len(record)>limit:
     stream.close();raw.close();raw,stream=begin();size=0
    stream.write(record);digest.update(record);size+=len(record);total+=len(record);count+=1
  finally:
   if stream:stream.close()
   if raw:raw.close()
  stem=path.name.removesuffix('.jsonl.gz')
  names=[path.name] if len(temporary)==1 else [f'{stem}.{i:03d}.jsonl.gz' for i in range(len(temporary))]
  previous=[path,*path.parent.glob(stem+'.[0-9][0-9][0-9].jsonl.gz')]
  for src,name in zip(temporary,names):src.replace(path.parent/name)
  for obsolete in previous:
   if obsolete.name not in names:obsolete.unlink(missing_ok=True)
 registry=path.parent/'jsonl-shards.json'
 index=json.loads(registry.read_text()) if registry.exists() else {'formatVersion':1,'maxUncompressedShardBytes':MAX_SHARD_BYTES,'datasets':{}}
 index['datasets'][path.name]={'uncompressedSha256':digest.hexdigest(),'uncompressedBytes':total,'recordCount':count,'shards':[artifact_metadata(path.parent/name) for name in names]}
 dump(registry,index)
 return index['datasets'][path.name]

def write_rows(name,values):
 return write_jsonl(OUT/name,((json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode() for row in values))

def shard_existing():
 """One-time conversion, reading original serialized bytes without re-encoding."""
 names=sorted(p.name for p in OUT.glob('*.jsonl.gz') if not re.search(r'\.\d{3}\.jsonl\.gz$',p.name))
 for name in names:
  with gzip.open(OUT/name,'rb') as f:write_jsonl(OUT/name,f)

def validate_shards(directory=None):
 directory=OUT if directory is None else Path(directory);index=json.loads((directory/'jsonl-shards.json').read_text());registered=set()
 if index['maxUncompressedShardBytes']!=MAX_SHARD_BYTES:raise ValueError('Changed shard limit')
 for name,dataset in index['datasets'].items():
  parts=dataset_paths(directory/name)
  if [p.name for p in parts]!=[m['path'] for m in dataset['shards']]:raise ValueError('Shard manifest ordering mismatch')
  digest=hashlib.sha256();size=0;count=0
  for part,metadata in zip(parts,dataset['shards']):
   if artifact_metadata(part)!=metadata:raise ValueError('Shard manifest integrity mismatch: '+part.name)
   raw=part.read_bytes()
   if raw[3]!=0 or raw[4:8]!=b'\0'*4:raise ValueError('Non-deterministic gzip header')
   content=gzip.decompress(raw)
   if len(content)>MAX_SHARD_BYTES:raise ValueError('Oversized shard')
   for line in content.splitlines():json.loads(line)
   digest.update(content);size+=len(content);count+=len(content.splitlines());registered.add(part.name)
  if (digest.hexdigest(),size,count)!=(dataset['uncompressedSha256'],dataset['uncompressedBytes'],dataset['recordCount']):raise ValueError('Dataset reconstruction mismatch')
 if registered!={p.name for p in directory.glob('*.jsonl.gz')}:raise ValueError('Unregistered or missing JSONL artifact')
 return index

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def get(url,kind='json'):
 CACHE.mkdir(parents=True,exist_ok=True);key=hashlib.sha256(url.encode()).hexdigest();p=CACHE/(key+'.'+kind);receipt=CACHE/(key+'.receipt.json')
 if p.exists():return json.loads(p.read_text()) if kind=='json' else p.read_bytes().decode('cp1252')
 global NEXT_REQUEST
 if 'wikidata.org/w/api.php' in url:
  with REQUEST_LOCK:
   delay=max(0,NEXT_REQUEST-time.monotonic())
   if delay:time.sleep(delay)
   NEXT_REQUEST=time.monotonic()+0.75
 r={'url':url,'attemptedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'cacheKey':key}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json' if kind=='json' else '*/*'}),timeout=90) as f:b=f.read();r.update(httpStatus=f.status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
  value=json.loads(b) if kind=='json' else b.decode('cp1252');
  if kind=='json' and ('error' in value or 'remark' in value):raise ValueError(str(value.get('error',value.get('remark'))))
  p.write_bytes(b);r['status']='complete';dump(receipt,r);return value
 except Exception as e:
  r.update(status='failed',error=str(e),retryAfter=getattr(e,'headers',{}).get('Retry-After'))
  dump(receipt,r);return None

def sparql(query):
 suffix='?'+urllib.parse.urlencode({'query':query,'format':'json'})
 x=get('https://query.wikidata.org/sparql'+suffix)
 if x is None:x=get('https://query.wikidata.org/bigdata/namespace/wdq/sparql'+suffix)
 return x
def api(**kw):return get('https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode({'format':'json','formatversion':2,**kw}))
def acquire():
 def wd(prop):
  # Independent property checkpoints: one failure does not erase another source.
  q='SELECT ?item ?code ?coord ?country ?name ?inception ?dissolution ?replaces ?replacedBy WHERE { ?item wdt:'+prop+' ?code . OPTIONAL { ?item wdt:P625 ?coord } OPTIONAL { ?item wdt:P17/wdt:P297 ?country } OPTIONAL { ?item rdfs:label ?name FILTER(LANG(?name)="en") } OPTIONAL { ?item wdt:P571 ?inception } OPTIONAL { ?item wdt:P576 ?dissolution } OPTIONAL { ?item wdt:P1365 ?replaces } OPTIONAL { ?item wdt:P1366 ?replacedBy } }'
  x=sparql(q);dump(OUT/('checkpoint-'+prop+'.json'),{'property':prop,'status':'complete' if x else 'failed','rows':len(x['results']['bindings']) if x else 0})
  return prop,x
 with futures.ThreadPoolExecutor(max_workers=2) as ex:wddata=list(ex.map(wd,['P238','P239']))
 entities={}
 for prop,x in wddata:
  for b in (x or {}).get('results',{}).get('bindings',[]):
   qid=b['item']['value'].rsplit('/',1)[-1];e=entities.setdefault(qid,{'qid':qid,'sourceFamily':'wikidata','codes':{'IATA':[],'ICAO':[]},'coordinates':[],'countries':[],'names':[],'inception':[],'dissolution':[],'replaces':[],'replacedBy':[]})
   def add(k,v):
    if v not in e[k]:e[k].append(v)
   code=b['code']['value'];scheme='IATA' if prop=='P238' else 'ICAO'
   if code not in e['codes'][scheme]:e['codes'][scheme].append(code)
   for k in ['country','name','inception','dissolution','replaces','replacedBy']:
    if k in b:add({'country':'countries','name':'names'}.get(k,k),b[k]['value'])
   if 'coord' in b:
    m=re.search(r'Point\(([-\d.]+) ([-\d.]+)\)',b['coord']['value'])
    if m:add('coordinates',{'latitude':float(m[2]),'longitude':float(m[1])})
 write_rows('wikidata-entities.jsonl.gz',sorted(entities.values(),key=lambda e:e['qid']))
 print('Wikidata entity acquisition',len(entities),flush=True)

def distance(a,b):
 p1,p2=math.radians(a['latitude']),math.radians(b['latitude']);d1=p2-p1;d2=math.radians(b['longitude']-a['longitude']);v=math.sin(d1/2)**2+math.cos(p1)*math.cos(p2)*math.sin(d2/2)**2
 return 6371*2*math.asin(min(1,math.sqrt(v)))
def norm(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def references():return [r for p in sorted((ROOT/'reference/generated').glob('records.*.jsonl.gz')) for r in rows(p)]
def match(refs,entities,osm=False):
 idx=defaultdict(list)
 for r in refs:
  for scheme in ['IATA','ICAO']:
   code=r['identifiers'].get(scheme)
   if code:idx[(scheme,code)].append(r)
   for o in r.get('historicalIdentifiers',[]):
    if o.get('scheme')==scheme and o.get('code'):idx[(scheme,o['code'])].append(r)
 result=[]
 for e in entities:
  if osm:
   t=e.get('tags',{});codes={s:[v.strip() for v in t.get(s.lower(),'').split(';') if v.strip()] for s in ['IATA','ICAO']};coords=[{'latitude':e.get('lat',e.get('center',{}).get('lat')),'longitude':e.get('lon',e.get('center',{}).get('lon'))}];coords=[c for c in coords if None not in c.values()];names=[t.get('name','')];countries=[];eid=f"{e['type']}/{e['id']}";qid=t.get('wikidata')
  else:codes=e['codes'];coords=e['coordinates'];names=e['names'];countries=e['countries'];eid=e['qid'];qid=eid
  candidates={r['referenceId']:r for s,cs in codes.items() for c in cs for r in idx[(s,c)]}
  accepted=[];conflicts=[]
  for rid,r in candidates.items():
   ds=[distance(a,l['coordinates']) for a in coords for l in r['locations'] if l.get('coordinates')];d=min(ds) if ds else None
   country_ok=not countries or r['country'] in countries
   name_ok=any(norm(n)==norm(r['name']) for n in names if n)
   # A directory correspondence, never proof of continuous physical identity.
   if d is not None and country_ok and (d<=2 or (d<=10 and name_ok)):
    accepted.append({'referenceId':rid,'ourAirportsId':r['sourceEntityId'],'airportIds':r['curatedAirportIds'],'distanceKm':round(d,3),'nameExact':name_ok,'country':r['country'],'region':r['region'],'basis':['code','coordinates']+(['name'] if name_ok else [])+(['country'] if countries else []),'physicalIdentityVerified':False})
   elif d is not None and d>20:conflicts.append({'referenceId':rid,'distanceKm':round(d,3),'reason':'shared_code_distant_site_or_source_error'})
  result.append({'sourceFamily':'osm' if osm else 'wikidata','license':'ODbL-1.0' if osm else 'CC0-1.0','sourceEntityId':eid,'qid':qid,'codes':codes,'matches':sorted(accepted,key=lambda a:a['distanceKm']),'distantCodeMatches':conflicts,'classification':'identity_only' if accepted else 'insufficient_evidence','formalAdmission':False})
 return result

def crosswalk():
 refs=references();wd=list(rows(OUT/'wikidata-entities.jsonl.gz'));osm=list(rows(OUT/'osm-airport-entities.jsonl.gz'))
 cross=match(refs,wd)+match(refs,osm,True);write_rows('global-crosswalk.jsonl.gz',cross)
 return refs,cross

def history():
 refs,cross=crosswalk()
 # Entire existing code-linked and high-value universe, with no airport count cap.
 relevant=set()
 for link in rows(ROOT/'research/evidence/global-code-expansion/ranked-code-links.jsonl.gz'):relevant.update(link['referenceIds'])
 for e in rows(ROOT/'research/evidence/global-code-expansion/high-value-queue.jsonl.gz'):
  relevant.update(s['referenceId'] for s in e['candidatePhysicalSites'])
 targets=sorted({c['sourceEntityId'] for c in cross if c['sourceFamily']=='wikidata' and any(m['referenceId'] in relevant for m in c['matches'])})
 dump(OUT/'checkpoint-wikidata-history.json',{'status':'running','targetQids':targets,'completed':0,'selection':'all coordinate-supported matches to all 2484 code-linked candidates and all 1198 high-value event groups','revisionWindow':HORIZON})
 histdir=CACHE/'history';histdir.mkdir(exist_ok=True)
 def one(qid):
  dest=histdir/(qid+'.json')
  if dest.exists() and json.loads(dest.read_text()).get('complete'):return json.loads(dest.read_text())
  revisions=[];cont={};complete=False
  while True:
   x=api(action='query',titles=qid,prop='revisions',rvprop='ids|timestamp|comment',rvlimit=500,rvstart='2026-11-10T23:59:59Z',rvend='1970-01-01T00:00:00Z',**cont)
   if not x:break
   for page in x.get('query',{}).get('pages',[]):revisions.extend(page.get('revisions',[]))
   if 'continue' not in x:complete=True;break
   cont=x['continue']
  # Code-property comments identify candidate edits; fetch both sides, never infer values from comments.
  edits=[r for r in revisions if re.search(r'\bP23[89]\b',r.get('comment',''))]
  ids=sorted({i for r in edits for i in [r['revid'],r.get('parentid')] if i});content={};content_complete=True
  for offset in range(0,len(ids),20):
   x=api(action='query',prop='revisions',revids='|'.join(map(str,ids[offset:offset+20])),rvprop='ids|timestamp|content',rvslots='main')
   if not x:content_complete=False;continue
   for page in x.get('query',{}).get('pages',[]):
    for r in page.get('revisions',[]):
     try:content[r['revid']]=json.loads(r['slots']['main']['content'])
     except (KeyError,ValueError):content_complete=False
  changes=[]
  def codes(entity,prop):
   claims=entity.get('claims') or {}; claims=claims if isinstance(claims,dict) else {}
   return sorted({c['mainsnak']['datavalue']['value'] for c in claims.get(prop,[]) if c.get('mainsnak',{}).get('snaktype')=='value' and isinstance(c['mainsnak'].get('datavalue',{}).get('value'),str)})
  for r in edits:
   if r['revid'] not in content or r.get('parentid') not in content:continue
   for prop,scheme in [('P238','IATA'),('P239','ICAO')]:
    old,new=codes(content[r['parentid']],prop),codes(content[r['revid']],prop)
    if old!=new:changes.append({'qid':qid,'revisionId':r['revid'],'parentRevisionId':r['parentid'],'timestamp':r['timestamp'],'property':prop,'scheme':scheme,'oldValue':old,'newValue':new,'classification':'observation_only','effectiveDate':None,'sourceUrl':f"https://www.wikidata.org/w/index.php?title={qid}&oldid={r['revid']}",'meaning':'Verified structured statement edit; not a verified real-world allocation event.'})
  result={'qid':qid,'complete':complete and content_complete,'revisionMetadataComplete':complete,'revisionCount':len(revisions),'codeEditCandidates':len(edits),'changes':changes,'limitation':'Comments select property-edit candidates; bulk imports or edits with non-property comments may be missed. Not an exhaustive content diff of every revision.'};dump(dest,result);return result
 allresults=[]
 with futures.ThreadPoolExecutor(max_workers=4) as ex:
  for result in ex.map(one,targets):
   allresults.append(result)
   if len(allresults)%25==0:print('Wikidata histories',len(allresults),'/',len(targets),flush=True)
 write_rows('wikidata-history.jsonl.gz',(c for r in allresults for c in r['changes']))
 dump(OUT/'checkpoint-wikidata-history.json',{'status':'complete' if all(r['complete'] for r in allresults) else 'partial','targetQids':targets,'completed':sum(r['complete'] for r in allresults),'revisionMetadataCount':sum(r['revisionCount'] for r in allresults),'propertyEditsInspected':sum(r['codeEditCandidates'] for r in allresults),'limitations':['Property-comment candidate selection does not prove exhaustive revision-content coverage.','Wikidata revision timestamps are observations, not effective dates.'],'entities':[{k:v for k,v in r.items() if k!='changes'} for r in allresults]})
 osm_history()

def osm_history():
 refs,cross=crosswalk()
 relevant=set()
 for link in rows(ROOT/'research/evidence/global-code-expansion/ranked-code-links.jsonl.gz'):relevant.update(link['referenceIds'])
 for e in rows(ROOT/'research/evidence/global-code-expansion/high-value-queue.jsonl.gz'):relevant.update(x['referenceId'] for x in e['candidatePhysicalSites'])
 # All OSM matches in the same candidate universe, including versions with removed tags.
 targets=[c['sourceEntityId'] for c in cross if c['sourceFamily']=='osm' and any(m['referenceId'] in relevant for m in c['matches'])]
 def osmone(eid):
  x=get(f'https://api.openstreetmap.org/api/0.6/{eid}/history.json');out=[];previous=None
  for e in sorted((x or {}).get('elements',[]),key=lambda e:e['version']):
   if e.get('timestamp','9999')[:10]>HORIZON[1]:continue
   tags=e.get('tags',{});new={s:tags.get(s.lower()) for s in ['IATA','ICAO']}
   if previous:
    for s in ['IATA','ICAO']:
     if previous[1][s]!=new[s]:out.append({'sourceEntityId':eid,'version':e['version'],'timestamp':e['timestamp'],'scheme':s,'oldValue':previous[1][s],'newValue':new[s],'classification':'observation_only','effectiveDate':None,'license':'ODbL-1.0','visible':e.get('visible',True)})
   previous=(e,new)
  return {'id':eid,'complete':x is not None,'versionCount':len((x or {}).get('elements',[])),'changes':out}
 with futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(osmone,targets))
 write_rows('osm-history.jsonl.gz',(c for r in results for c in r['changes']))
 dump(OUT/'checkpoint-osm-history.json',{'targets':len(targets),'completed':sum(r['complete'] for r in results),'versionCount':sum(r['versionCount'] for r in results),'limitation':'Current Overpass discovery cannot enumerate every deleted historical airport object.','objects':[{k:v for k,v in r.items() if k!='changes'} for r in results]})
 print('OSM histories complete',len(results),flush=True)

def statements():
 results=[]
 for prop,scheme in [('P238','IATA'),('P239','ICAO')]:
  q='SELECT ?item ?statement ?code ?rank ?start ?end ?point ?reference ?url WHERE { ?item p:'+prop+' ?statement . ?statement ps:'+prop+' ?code ; wikibase:rank ?rank . OPTIONAL { ?statement pq:P580 ?start } OPTIONAL { ?statement pq:P582 ?end } OPTIONAL { ?statement pq:P585 ?point } OPTIONAL { ?statement prov:wasDerivedFrom ?reference . OPTIONAL { ?reference pr:P854 ?url } } }'
  x=sparql(q)
  for b in (x or {}).get('results',{}).get('bindings',[]):
   r={k:v['value'] for k,v in b.items()};r.update(qid=r.pop('item').rsplit('/',1)[-1],scheme=scheme,property=prop,classification='bounded_historical_interval' if 'start' in r and 'end' in r else 'observation_only',formalAdmission=False,effectiveDate=None);results.append(r)
  dump(OUT/('checkpoint-statements-'+prop+'.json'),{'status':'complete' if x else 'failed','rows':len((x or {}).get('results',{}).get('bindings',[]))})
 write_rows('wikidata-code-statements.jsonl.gz',results)
 print('Wikidata statements',len(results),flush=True)

def build():
 refs,cross=crosswalk();cross_by_qid={c['sourceEntityId']:c for c in cross if c['sourceFamily']=='wikidata'};refmap={r['referenceId']:r for r in refs};external=defaultdict(list)
 for c in cross:
  for m in c['matches']:external[m['referenceId']].append({'sourceFamily':c['sourceFamily'],'sourceEntityId':c['sourceEntityId'],'distanceKm':m['distanceKm'],'license':c['license']})
 formal=json.loads((ROOT/'data/airports.json').read_text());assert formal['dataVersion']=='0.12.0' and formal['schemaVersion']=='3.0.0'
 groups=Counter();countries=Counter();regions=Counter();classes=Counter();candidates=[];high=0;matched_groups=0;transition_obs=0
 high_ids={e['eventGroupId'] for e in rows(ROOT/'research/evidence/global-code-expansion/high-value-queue.jsonl.gz')}
 remaining_ids={e['eventGroupId'] for e in rows(ROOT/'research/evidence/global-code-next/remaining-high-value-queue.jsonl.gz')}
 reviewed_ids=high_ids-remaining_ids
 prior_progress=json.loads((ROOT/'research/evidence/global-code-next/review-progress.json').read_text())
 prior_claims=json.loads((ROOT/'research/evidence/global-code-next/normalized-candidates.json').read_text())
 dump(OUT/'reused-review-decisions.json',{'sourcePaths':['research/evidence/global-code-next/review-progress.json','research/evidence/global-code-next/normalized-candidates.json'],'priorCounts':prior_progress['counts'],'previouslyReviewedHighValueGroupIds':sorted(reviewed_ids),'existingNormalizedClaimsUnchanged':prior_claims['claims'],'newSubstantiveReviewsClaimedByMechanicalJoin':0})
 for path in sorted((ROOT/'research/evidence/global-code-expansion').glob('ranked-events.[0-9]*.jsonl.gz')):
  for e in rows(path):
   groups['all']+=1;countries[e.get('country','unknown')]+=1
   sites=e.get('candidatePhysicalSites',[]);rids=sorted({s['referenceId'] for s in sites});joined=[{'referenceId':rid,**x} for rid in rids for x in external[rid]]
   if joined:matched_groups+=1
   if e.get('priorityTier')=='high':high+=1
   obs=[]
   for o in e.get('directoryObservations',[]):
    for field,scheme in [('iata','IATA'),('icao','ICAO')]:
     v=o.get('changes',{}).get(field)
     if v and v[0]!=v[1]:
      transition_obs+=1;obs.append({'sourceId':o['sourceId'],'sourceEntityId':o['sourceEntityId'],'scheme':scheme,'oldValue':v[0],'newValue':v[1],'observationTime':o.get('time'),'candidateId':o.get('candidateId'),'classification':'observation_only','effectiveDate':None})
   if obs:
    candidates.append({'candidateId':e['eventGroupId'],'kind':'existing_event_enrichment','priorHighValueReviewed':e['eventGroupId'] in reviewed_ids,'priorReviewContext':'reused-review-decisions.json','country':e.get('country'),'referenceIds':rids,'classification':'observation_only','codeObservations':obs,'externalMatches':joined,'effectiveDate':None,'verifiedCodeChange':False,'formalAdmission':False})
   groups['externallyMatched' if joined else 'withoutExternalMatch']+=1
 links=list(rows(ROOT/'research/evidence/global-code-expansion/ranked-code-links.jsonl.gz'))
 for l in links:
  candidates.append({'candidateId':l['candidateId'],'kind':'existing_code_link','scheme':l['scheme'],'code':l['code'],'referenceIds':l['referenceIds'],'countries':l.get('countries',[]),'externalMatches':[{'referenceId':rid,**x} for rid in l['referenceIds'] for x in external[rid]],'classification':'insufficient_evidence','effectiveDate':None,'formalAdmission':False})
 wdchanges=list(rows(OUT/'wikidata-history.jsonl.gz')) if (OUT/'wikidata-history.jsonl.gz').exists() else []
 osmchanges=list(rows(OUT/'osm-history.jsonl.gz')) if (OUT/'osm-history.jsonl.gz').exists() else []
 for c in wdchanges:candidates.append({'candidateId':f"wd-{c['qid']}-{c['revisionId']}-{c['property']}",'kind':'wikidata_revision_change',**c,'formalAdmission':False})
 # OSM-derived research remains a separate ODbL database; only counts enter MIT summary.
 bystatement={}
 for s in rows(OUT/'wikidata-code-statements.jsonl.gz'):
  key=s['statement'];r=bystatement.setdefault(key,dict(s,references=[]));
  if s.get('reference'):r['references'].append({k:s[k] for k in ['reference','url'] if k in s})
 bounded=0
 for sid,s in sorted(bystatement.items()):
  bounded+=s['classification']=='bounded_historical_interval'
  candidates.append({'candidateId':sid,'kind':'wikidata_statement','referenceIds':[m['referenceId'] for m in cross_by_qid.get(s['qid'],{}).get('matches',[])],**s,'datePrecision':'not_yet_verified','meaning':'Structured Wikidata assertion; qualifier dates require cited-primary-source and precision review before admission.'})
 write_rows('historical-code-candidates.jsonl.gz',candidates)
 reuse=[];site_pairs=0
 wd_by_code=defaultdict(list)
 wdentities=list(rows(OUT/'wikidata-entities.jsonl.gz'))
 for e in wdentities:
  for scheme,cs in e['codes'].items():
   for code in cs:wd_by_code[(scheme,code)].append(e)
 for r in rows(ROOT/'research/evidence/global-code-expansion/ranked-reuse-leads.jsonl.gz'):
  qentities=wd_by_code[(r['scheme'],r['code'])];distinct=[]
  for i,a in enumerate(qentities):
   for b in qentities[i+1:]:
    ds=[distance(c,d) for c in a['coordinates'] for d in b['coordinates']]
    if ds and min(ds)>20:distinct.append({'qids':[a['qid'],b['qid']],'minimumDistanceKm':round(min(ds),3),'status':'distinct_entity_coordinates; airport type and historical code attribution unverified'})
  site_pairs+=bool(distinct)
  reuse.append({'scheme':r['scheme'],'code':r['code'],'referenceIds':r['referenceIds'],'eventGroupIds':r['eventGroupIds'],'externalMatches':[{'referenceId':rid,**x} for rid in r['referenceIds'] for x in external[rid]],'wikidataDistinctEntityPairs':distinct,'classification':'identity_only' if distinct else 'insufficient_evidence','physicalReuseVerified':False,'effectiveDate':None,'formalAdmission':False})
 # Discover additional shared codes beyond the 493 preexisting leads.
 existing={(r['scheme'],r['code']) for r in reuse};additional=0
 for (scheme,code),es in sorted(wd_by_code.items()):
  if (scheme,code) in existing:continue
  pairs=[]
  for i,a in enumerate(es):
   for b in es[i+1:]:
    ds=[distance(c,d) for c in a['coordinates'] for d in b['coordinates']]
    if ds and min(ds)>20:pairs.append({'qids':[a['qid'],b['qid']],'minimumDistanceKm':round(min(ds),3)})
  if pairs:
   additional+=1;reuse.append({'scheme':scheme,'code':code,'kind':'new_wikidata_shared_code_lead','wikidataDistinctEntityPairs':pairs,'classification':'identity_only','physicalReuseVerified':False,'formalAdmission':False})
 write_rows('physical-reuse-candidates.jsonl.gz',reuse)
 for c in candidates:classes[c['classification']]+=1
 for r in refs:
  if external.get(r['referenceId']):regions[r.get('region','unknown')]+=1
 newqids=[c['sourceEntityId'] for c in cross if c['sourceFamily']=='wikidata' and not c['matches']]
 write_rows('unmatched-wikidata-entities.jsonl.gz',({'qid':q,'status':'unmatched entity; may be non-airport, duplicate or missing reference','classification':'insufficient_evidence'} for q in newqids))
 dump(OUT/'admission-proposal.json',{'baselineCommit':'bb1046455e949c6c0bf3a18769464cb232bec19e','dataVersion':formal['dataVersion'],'schemaVersion':formal['schemaVersion'],'newEvidenceCompleteCandidates':[],'newEligibleCandidates':0,'formalDataModified':False,'ownerAuthorizationRequested':False,'reason':'New directory and revision observations do not meet existing claim-specific historical admission requirements. Existing separately prepared boundary proposals are unchanged and not counted as new enrichment.','existingAdmissionMechanism':'admission/v1/; scripts/evidence/current_project_admission.py','sourcesAndScopesPreserved':True})
 # Lookup all codes touched by the batch, separately from actual historical flight corpora.
 codes={(l['scheme'],l['code']) for l in links}
 for e in wdentities:
  codes.update((scheme,c) for scheme,cs in e['codes'].items() for c in cs)
 codes.update((a['scheme'],a['code']) for a in formal['assignments'])
 dump(OUT/'resolver-query-codes.json',[{'scheme':s,'code':c} for s,c in sorted(codes) if re.fullmatch('[A-Z]{3}' if s=='IATA' else '[A-Z]{4}',c)])
 receipts=[json.loads(p.read_text()) for p in sorted(CACHE.glob('*.receipt.json'))]
 if not receipts and (OUT/'source-lock.json').exists():receipts=json.loads((OUT/'source-lock.json').read_text()).get('acquisitionReceipts',[])
 dump(OUT/'source-lock.json',{'baselineCommit':'bb1046455e949c6c0bf3a18769464cb232bec19e','existingOurairportsLock':json.loads((ROOT/'reference/source-lock.json').read_text()),'reusedInputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size} for pat in ['reference/generated/records.*.jsonl.gz','reference/triage/*.jsonl.gz','research/evidence/global-code-expansion/ranked-*.jsonl.gz','research/evidence/global-code-expansion/high-value-queue.jsonl.gz','research/evidence/global-code-next/*.json','research/discovery/generated/*entities.jsonl.gz'] for p in sorted(ROOT.glob(pat))],'acquisitionReceipts':receipts})
 catalog={'horizon':HORIZON,'sources':[{'id':'ourairports','license':'Public Domain','lineage':['airport-codes','airport-codes-raw','datasets/airport-codes'],'role':'Existing pinned snapshot and source observations; all derivatives count as one family.'},{'id':'wikidata','license':'CC0-1.0','url':'https://www.wikidata.org/','role':'Structured main-namespace code, identity and revision facts; not effective-date authority.'},{'id':'osm','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','url':'https://www.openstreetmap.org/copyright','role':'Separate research database: osm-airport-entities.jsonl.gz and osm-history.jsonl.gz. Crosswalk OSM rows and OSM-derived matches retain ODbL obligations. No formal data incorporation.'},{'id':'bts','url':'https://www.transtats.bts.gov/','role':'US lookup only; no real-flight records acquired or counted.'},{'id':'faa','url':'https://www.faa.gov/air_traffic/flight_info/aeronav/Aero_Data/NASR_Subscription/','role':'NASR discovery; historical effective files require acquisition.'},{'id':'airportsdata-mwgg','role':'Existing references reused through ranked groups; source independence not established.'}]}
 dump(OUT/'source-catalog.json',catalog)
 report={'baseline':{'commit':'bb1046455e949c6c0bf3a18769464cb232bec19e','dataVersion':formal['dataVersion'],'schemaVersion':formal['schemaVersion'],'physicalAirports':len(formal['airports']),'assignments':len(formal['assignments']),'sources':len(formal['sources'])},'horizon':HORIZON,'processing':{'referenceRecords':len(refs),'priorSubstantivelyReviewedHighValueGroupsPreserved':len(reviewed_ids),'historicalEventGroups':groups['all'],'codeLinkedCandidates':len(links),'codeLinkedCandidatesByScheme':dict(Counter(l['scheme'] for l in links)),'existingGeographicReuseLeads':493,'highValueEventGroups':sum(1 for _ in rows(ROOT/'research/evidence/global-code-expansion/high-value-queue.jsonl.gz')),'eventGroupsWithExternalMatches':matched_groups,'directoryCodeTransitionObservations':transition_obs},'results':{'wikidataEntities':len(wdentities),'osmEntities':sum(1 for _ in rows(OUT/'osm-airport-entities.jsonl.gz')),'globallyMatchedWikidataEntities':sum(bool(c['matches']) for c in cross if c['sourceFamily']=='wikidata'),'globallyMatchedOsmEntities':sum(bool(c['matches']) for c in cross if c['sourceFamily']=='osm'),'matchedReferenceRecords':sum(bool(v) for v in external.values()),'unmatchedWikidataEntities':len(newqids),'wikidataCodeStatementRelationships':len(bystatement),'wikidataQualifierBoundedRelationshipsUnverified':bounded,'wikidataRevisionCodeChanges':len(wdchanges),'osmRevisionCodeChanges':len(osmchanges),'existingReuseLeadsWithDistantWikidataEntities':site_pairs,'additionalDistantEntityCodeLeads':additional,'newVerifiedPhysicalAirportIdentities':0,'newVerifiedIataHistoricalRelationships':0,'newVerifiedIcaoHistoricalRelationships':0,'newVerifiedCodeChangeEvents':0,'newVerifiedBoundedHistoricalIntervals':0,'newAdmissionEligibleCandidates':0,'newlySolvedCrossSiteReuse':0,'realAffectedFlightRecords':None,'actualFlightCorpusAcquired':False},'classifications':{k:classes[k] for k in ['direct_effective_date','bounded_historical_interval','continuity_inference','identity_only','observation_only','conflicting_evidence','insufficient_evidence']},'eventGroupsByCountry':dict(sorted(countries.items())),'matchedReferencesByRegion':dict(sorted(regions.items())),'limitations':['Directory corroboration and code-property revisions do not establish actual effective allocation dates.','All event groups were joined mechanically; this is not substantive resolution of 88330 histories.','All-rank Wikidata statement discovery includes deprecated assertions; deprecated status does not certify historical truth.','Revision acquisition uses property-edit comments and cannot guarantee detection of uncommented or bulk-import code edits.','OSM current-object discovery misses deleted objects absent from current Overpass results; targeted history does not solve that global gap.','No real historical flight corpus acquired. BTS/FAA landing and lookup acquisition is not historical flight validation.','No new candidate meets existing formal admission requirements; production coverage gain is zero.']}
 report['matchedEntitiesByCountry']={family:dict(sorted(Counter(m['country'] for c in cross if c['sourceFamily']==family for m in {a['country']:a for a in c['matches']}.values()).items())) for family in ['wikidata','osm']}
 report['acquisitionCheckpoints']={p.name:json.loads(p.read_text()) for p in sorted(OUT.glob('checkpoint-*.json')) if 'history' not in p.name}
 report['limitations']=list(dict.fromkeys(report['limitations']))
 dump(OUT/'coverage-report.json',report)
 # Empty artifact means zero fetched changes, not an assertion that no changes exist.
 for n in ['wikidata-history.jsonl.gz','osm-history.jsonl.gz']:
  if not (OUT/n).exists():write_rows(n,[])
 print(json.dumps({'processing':report['processing'],'results':report['results']}),flush=True)

def osm_acquire():
 # Global quadrants, coded aerodromes: each tile has independent cache and checkpoint.
 boxes=[(-90,-180,0,-90),(-90,-90,0,0),(-90,0,0,90),(-90,90,0,180),(0,-180,90,-90),(0,-90,90,0)]+[(a,b,a+45,b+45) for a in [0,45] for b in [0,45,90,135]]
 boxes=[b for b in boxes if b!=(0,45,45,90)]+[(a,b,a+22.5,b+22.5) for a in [0,22.5] for b in [45,67.5]]
 def tile(box):
  b=','.join(map(str,box));query=f'[out:json][timeout:50];(nwr["aeroway"="aerodrome"]["iata"]({b});nwr["aeroway"="aerodrome"]["icao"]({b}););out center meta;'
  result=None
  for endpoint in ['https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter']:
   result=get(endpoint+'?'+urllib.parse.urlencode({'data':query}))
   if result:break
  return {'bbox':box,'complete':result is not None,'elements':(result or {}).get('elements',[])}
 with futures.ThreadPoolExecutor(max_workers=2) as ex:tiles=list(ex.map(tile,boxes))
 es={}
 for t in tiles:
  for e in t['elements']:
   e.pop('user',None);e.pop('uid',None);es[(e['type'],e['id'])]={'sourceFamily':'osm','license':'ODbL-1.0',**e}
 write_rows('osm-airport-entities.jsonl.gz',(es[k] for k in sorted(es)))
 dump(OUT/'checkpoint-osm-entities.json',{'status':'complete' if all(t['complete'] for t in tiles) else 'partial','scope':'Global coded aerodromes; codeless and deleted objects outside current discovery.','tiles':[{k:v for k,v in t.items() if k!='elements'}|{'count':len(t['elements'])} for t in tiles]})
 print('OSM',len(es),'entities',flush=True)

def bts():
 import csv,io
 lookup={};seqs={};checkpoints=[]
 for name,url in [('airport-id','https://www.transtats.bts.gov/Download_Lookup.asp?Y11x72=Y_NVe214g_VQ'),('airport-seq-id','https://www.transtats.bts.gov/Download_Lookup.asp?Y11x72=Y_NVe214g_fRd_VQ')]:
  text=get(url,'csv')
  records=list(csv.DictReader(io.StringIO(text or '')))
  records=[r for r in records if r.get('Code') and r.get('Description')]
  if name=='airport-id':lookup={r['Code']:r['Description'] for r in records}
  else:seqs={r['Code']:r['Description'] for r in records}
  write_rows('bts-'+name+'-lookup.jsonl.gz',records);checkpoints.append({'lookup':name,'rows':len(records),'url':url,'status':'complete' if records else 'failed'})
 refs=references();index=defaultdict(list)
 for r in refs:
  if r['country']=='US':index[(norm(r['name']),norm(r['municipality'] or ''),r['region'].removeprefix('US-'))].append(r)
 matches=[]
 for aid,description in lookup.items():
  m=re.match(r'(.+), ([A-Z]{2}): (.+)',description)
  if not m:continue
  city,state,name=m.groups();rs=index[(norm(name),norm(city),state)]
  if len(rs)==1:matches.append({'airportIdBts':aid,'description':description,'referenceId':rs[0]['referenceId'],'ourAirportsId':rs[0]['sourceEntityId'],'basis':['airport_name','municipality','US_state'],'classification':'identity_only','physicalIdentityVerified':False,'airportSeqIds':[s for s in seqs if s[:-2]==aid],'effectiveDate':None,'note':'Sequence numeric-prefix join retained as a lead, not an effective interval or verified physical-site continuity.'})
 write_rows('bts-crosswalk.jsonl.gz',matches);dump(OUT/'checkpoint-bts.json',{'lookups':checkpoints,'nameCityStateMatches':len(matches),'actualFlightRecords':0,'limitation':'Lookups have no sequence effective chronology and are not actual flight records.'});print('BTS',len(lookup),len(seqs),len(matches),flush=True)

def complete_entities():
 entities={e['qid']:e for e in rows(OUT/'wikidata-entities.jsonl.gz')};statements=list(rows(OUT/'wikidata-code-statements.jsonl.gz'));missing=sorted({s['qid'] for s in statements}-entities.keys())
 def batch(qids):return api(action='wbgetentities',ids='|'.join(qids),props='claims|labels|aliases|info',languages='en')
 chunks=[missing[i:i+40] for i in range(0,len(missing),40)]
 with futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(batch,chunks))
 for x in results:
  for q,e in (x or {}).get('entities',{}).items():
   claims=e.get('claims') or {};claims=claims if isinstance(claims,dict) else {}
   def vals(prop):return [c['mainsnak']['datavalue']['value'] for c in claims.get(prop,[]) if c.get('mainsnak',{}).get('snaktype')=='value']
   entities[q]={'qid':q,'revisionId':e.get('lastrevid'),'sourceFamily':'wikidata','discovery':'all_rank_code_statement','codes':{'IATA':[],'ICAO':[]},'coordinates':[{'latitude':c['latitude'],'longitude':c['longitude']} for c in vals('P625') if c.get('globe','').endswith('/Q2')],'countries':[],'countryQids':[v['id'] for v in vals('P17')],'names':[v['value'] for v in e.get('labels',{}).values()]+[a['value'] for al in e.get('aliases',{}).values() for a in al],'inception':vals('P571'),'dissolution':vals('P576'),'replaces':vals('P1365'),'replacedBy':vals('P1366')}
 for e in entities.values():e.setdefault('bestRankCodes',json.loads(json.dumps(e['codes'])))
 for s in statements:
  if s['qid'] in entities and s['code'] not in entities[s['qid']]['codes'][s['scheme']]:entities[s['qid']]['codes'][s['scheme']].append(s['code'])
 write_rows('wikidata-entities.jsonl.gz',(entities[q] for q in sorted(entities)))
 dump(OUT/'checkpoint-entity-enumeration.json',{'globalStatementQids':len({s['qid'] for s in statements}),'entityRecords':len(entities),'allRankAdditionalQids':len(missing),'metadataCompleteForAllStatementQids':set(s['qid'] for s in statements)<=entities.keys(),'note':'codes includes all statement ranks, including deprecated claims; bestRankCodes preserves initial truthy query values. No historical truth or continuity inferred.'})
 print('all rank entities',len(entities),flush=True)

def faa():
 import csv,io,zipfile,uuid
 # Two official effective editions, not archive acquisition timestamps.
 source_ids=['public-faa-nasr-20261001','public-faa-nasr-20261029'];editions=[];locks=[]
 fields=['EFF_DATE','SITE_NO','SITE_TYPE_CODE','STATE_CODE','ARPT_ID','CITY','COUNTRY_CODE','ARPT_NAME','LAT_DECIMAL','LONG_DECIMAL','ICAO_ID','ARPT_STATUS']
 for date,label in [('2026-10-01','01_Oct'),('2026-10-29','29_Oct')]:
  url=f'https://nfdc.faa.gov/webContent/28DaySub/extra/{label}_2026_APT_CSV.zip';key=hashlib.sha256(url.encode()).hexdigest();file=CACHE/(key+'.zip')
  projection=OUT/('faa-nasr-'+date+'.jsonl.gz')
  if not file.exists() and projection.exists() and (OUT/'faa-source-lock.json').exists():
   rs=list(rows(projection));editions.append({r['SITE_NO']:r for r in rs});locks.append(next(l for l in json.loads((OUT/'faa-source-lock.json').read_text()) if l['effectiveEdition']==date));continue
  if not file.exists():
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=90) as response:raw=response.read()
    file.write_bytes(raw);dump(CACHE/(key+'.receipt.json'),{'url':url,'status':'complete','sha256':sha(file),'bytes':len(raw),'effectiveEdition':date})
   except Exception as error:
    dump(OUT/'checkpoint-faa.json',{'status':'failed','url':url,'error':str(error)});return
  with zipfile.ZipFile(file) as z:raw=z.read('APT_BASE.csv')
  rs=[{f:r[f] for f in fields} for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))];editions.append({r['SITE_NO']:r for r in rs})
  write_rows('faa-nasr-'+date+'.jsonl.gz',rs)
  locks.append({'url':url,'archiveSha256':sha(file),'archiveBytes':file.stat().st_size,'member':'APT_BASE.csv','memberSha256':hashlib.sha256(raw).hexdigest(),'effectiveEdition':date,'rows':len(rs),'projectedFields':fields,'license':'US government factual airport data; 17 USC 105; no third-party charts or private contact fields redistributed.'})
 idfile=OUT/'proposed-airport-id-bindings.json'
 bindings=json.loads(idfile.read_text()) if idfile.exists() else {}
 refs=references();idx=defaultdict(list)
 for r in refs:
  if r['country']=='US' and r.get('presentAtSnapshot'):
   for scheme in ['ICAO','GPS','LOCAL']:
    if r['identifiers'].get(scheme):idx[r['identifiers'][scheme]].append(r)
 formal=json.loads((ROOT/'data/airports.json').read_text());proposed=json.loads(json.dumps(formal));byoa={a['externalIds'].get('ourAirports'):a for a in formal['airports']};exclusions=Counter();claims=[];newairports={};seen_codes=Counter();review=[]
 existing_assignments={(a['airportId'],a['scheme'],a['code']) for a in formal['assignments']}
 for site,old in editions[0].items():
  new=editions[1].get(site)
  if not new:exclusions['site_absent_later_edition']+=1;continue
  code=old['ICAO_ID']
  if old['COUNTRY_CODE']!='US' or new['COUNTRY_CODE']!='US' or not re.fullmatch('[A-Z]{4}',code or ''):exclusions['outside_US_or_no_four_letter_ICAO']+=1;continue
  if code!=new['ICAO_ID']:exclusions['ICAO_changed_requires_boundary_review']+=1;review.append({'siteNo':site,'oldCode':code,'newCode':new['ICAO_ID'],'classification':'observation_only'});continue
  if old['ARPT_STATUS']!='O' or new['ARPT_STATUS']!='O':exclusions['not_open_both_editions']+=1;continue
  a={'latitude':float(old['LAT_DECIMAL']),'longitude':float(old['LONG_DECIMAL'])};b={'latitude':float(new['LAT_DECIMAL']),'longitude':float(new['LONG_DECIMAL'])}
  if distance(a,b)>.1:exclusions['FAA_coordinate_difference_over_100m']+=1;continue
  candidates={r['referenceId']:r for k in [code,new['ARPT_ID']] for r in idx[k]}
  matched=[]
  for r in candidates.values():
   if r['region']!='US-'+new['STATE_CODE']:continue
   coords=[l['coordinates'] for l in r['locations'] if l.get('kind')=='snapshot' and l.get('coordinates')]
   if not coords:continue
   if min(distance(b,c) for c in coords)>.5:continue
   if r['identifiers'].get('ICAO')!=code and r['identifiers'].get('GPS')!=code:continue
   # Require independently keyed FAA local identifier as well as ICAO and position.
   if new['ARPT_ID'] not in [r['identifiers'].get('LOCAL'),r['identifiers'].get('IDENT')]:continue
   matched.append(r)
  if len(matched)!=1:exclusions['no_unique_ICAO_local_id_coordinate_state_match']+=1;continue
  r=matched[0]
  if not r.get('timezone'):exclusions['missing_existing_timezone_reference']+=1;continue
  airport=byoa.get(r['sourceEntityId']);airport_id=airport['airportId'] if airport else bindings.setdefault(r['sourceEntityId'],'apt_'+str(uuid.uuid4()))
  if (airport_id,'ICAO',code) in existing_assignments:exclusions['already_formal_relationship']+=1;continue
  if not airport:
   airport={'airportId':airport_id,'externalIds':{'ourAirports':r['sourceEntityId']},'name':{'value':r['name'],'status':'reference','sourceIds':['public-ourairports-snapshot'],'note':'Reference display name; no historical official-name claim.'},'coordinates':{'value':b,'status':'reference','sourceIds':source_ids,'note':'FAA reference position, stable within 100 m across the two effective editions.'},'timezone':{'value':r['timezone'],'status':'reference','sourceIds':['public-airportsdata-timezones'],'note':'Reused pinned reference timezone; not an allocation date or fixed UTC offset.'}}
   newairports[airport_id]=airport
  assignment={'assignmentId':'public-faa-'+site.replace('.','')+'-icao','airportId':airport_id,'scheme':'ICAO','code':code,'validFrom':{'earliest':None,'latest':'2026-10-02','precision':'unknown'},'validTo':{'earliest':'2026-10-28','latest':None,'precision':'unknown'},'evidenceType':'continuity_inference','verificationStatus':'pending','verifiedOn':None,'sourceIds':source_ids,'note':'Unapproved bounded continuity inference between two FAA effective editions at one stable FAA site. Certain whole-date core 2026-10-02 through 2026-10-27. An extra guard day before the second civil edition date avoids inventing an effective UTC instant or treating an edition date as a local airport timestamp. Allocation/withdrawal dates and validity outside observations remain unknown; publication is not allocation. Same issuer temporal observations, not two independent source families. Owner scope authorization required.'}
  claims.append({'assignment':assignment,'referenceId':r['referenceId'],'faaSiteNo':site,'ourAirportsId':r['sourceEntityId'],'country':'US','region':r['region'],'classification':'continuity_inference','identityBasis':['stable_FAA_site_number','stable_ICAO_across_editions','FAA_local_identifier','coordinates_within_500m','same_US_state'],'editionRows':[old,new],'rowSha256':[hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest() for v in [old,new]],'newPhysicalAirport':airport_id in newairports,'evidenceCompleteForBoundedClaim':True,'ownerAuthorization':'not_granted','formalAdmission':False});seen_codes[code]+=1
 # Multiple sites claiming one code require genuine conflict review, never winner selection.
 conflicts=[c for c in claims if seen_codes[c['assignment']['code']]>1];claims=[c for c in claims if seen_codes[c['assignment']['code']]==1];needed={c['assignment']['airportId'] for c in claims}
 proposed['airports'].extend(a for aid,a in sorted(newairports.items()) if aid in needed)
 proposed['assignments'].extend(c['assignment'] for c in claims)
 for date,sid,lock in zip(['2026-10-01','2026-10-29'],source_ids,locks):
  proposed['sources'].append({'sourceId':sid,'title':'FAA NASR airport base, effective '+date,'url':lock['url'],'accessedOn':'2026-11-10','sourceType':'primary','verificationStatus':'pending','license':{'id':'LicenseRef-US-Government-Facts','url':'https://www.copyright.gov/title17/92chap1.html#105','note':'Selected factual FAA government data; no third-party charts/contact information redistributed.'},'note':'Scope: listed US site/ICAO observations in this edition only. Archive and member hashes in FAA source lock. Pending new Owner authorization; no legacy grant reused.'})
 reflock=json.loads((ROOT/'reference/source-lock.json').read_text());tz=json.loads((ROOT/'reference/generated/sources.json').read_text())['airportsdata']
 proposed['sources'].extend([{'sourceId':'public-ourairports-snapshot','title':'Existing pinned OurAirports reference','url':reflock['downloadUrl'],'accessedOn':'2026-11-10','sourceType':'secondary','verificationStatus':'pending','license':{'id':'Public-Domain','url':reflock['licenseUrl'],'note':'Existing public-domain snapshot, reused for site identity only.'},'note':'Reference label, coordinates and stable numeric ID only; no code allocation date inferred.'},{'sourceId':'public-airportsdata-timezones','title':'Existing pinned airportsdata timezone references','url':'https://github.com/mborsetti/airportsdata/blob/'+tz['revision']+'/airportsdata/airports.csv','accessedOn':'2026-11-10','sourceType':'secondary','verificationStatus':'pending','license':{'id':'MIT','url':'https://github.com/mborsetti/airportsdata/blob/'+tz['revision']+'/LICENSE','note':'Existing reference/LICENSE-airportsdata notice retained.'},'note':'Timezone reference only; no independent historical code confirmation.'}])
 dump(idfile,bindings);dump(OUT/'checkpoint-faa.json',{'status':'complete','effectiveEditions':[l['effectiveEdition'] for l in locks]});dump(OUT/'faa-source-lock.json',locks);write_rows('faa-admission-candidates.jsonl.gz',claims);dump(OUT/'faa-conflicts.json',conflicts);dump(OUT/'proposed-data.json',proposed)
 dump(OUT/'faa-admission-summary.json',{'effectiveEditions':['2026-10-01','2026-10-29'],'evidenceCompleteCandidates':len(claims),'newPhysicalAirportProposals':sum(aid in needed for aid in newairports),'newIcaoRelationships':len(claims),'newIataRelationships':0,'newVerifiedCodeChangeEvents':0,'inferredCore':['2026-10-02','2026-10-27'],'exclusions':dict(exclusions),'duplicateCodeConflicts':len(conflicts),'countryDistribution':{'US':len(claims)},'regions':dict(Counter(c['region'] for c in claims)),'admissionStatus':'prepared; source/claim scopes and Owner authorization required by existing admission mechanism','formalDataModified':False,'actualFlightRecords':None})
 dump(OUT/'admission-proposal.json',{'baselineCommit':'bb1046455e949c6c0bf3a18769464cb232bec19e','schemaVersion':'3.0.0','dataVersion':'0.12.0','newEligibleCandidates':len(claims),'newEvidenceCompleteCandidates':[c['assignment']['assignmentId'] for c in claims],'proposedDataset':'proposed-data.json','dossiers':'faa-admission-candidates.jsonl.gz','existingAdmissionMechanism':'admission/v1/; existing source-claims policy and Owner source/claim scopes','ownerAuthorization':'not_granted','formalDataModified':False,'sourceScope':'Two identified FAA editions for listed ICAO/site relationships; existing grants and source scopes remain unchanged.','hypothesis':'Evidence-ready pending policy/source-scope review; simulation may approve only these new records in memory.'})
 print('FAA bounded candidates',len(claims),'new physical proposals',sum(aid in needed for aid in newairports),flush=True)

def finalize():
 report=json.loads((OUT/'coverage-report.json').read_text());faa_summary=json.loads((OUT/'faa-admission-summary.json').read_text());claims=list(rows(OUT/'faa-admission-candidates.jsonl.gz'))
 c=list(rows(OUT/'historical-code-candidates.jsonl.gz'));c=[r for r in c if r.get('kind')!='faa_bounded_continuity']
 for claim in claims:c.append({'candidateId':claim['assignment']['assignmentId'],'kind':'faa_bounded_continuity','classification':'continuity_inference','country':'US','region':claim['region'],'referenceIds':[claim['referenceId']],'scheme':'ICAO','code':claim['assignment']['code'],'boundedCore':faa_summary['inferredCore'],'sourceIds':claim['assignment']['sourceIds'],'formalAdmission':False,'ownerAuthorization':'not_granted'})
 write_rows('historical-code-candidates.jsonl.gz',c)
 cross=[r for r in rows(OUT/'global-crosswalk.jsonl.gz') if r['sourceFamily'] in ['wikidata','osm']]
 for claim in claims:cross.append({'sourceFamily':'faa','sourceEntityId':claim['faaSiteNo'],'codes':{'ICAO':[claim['assignment']['code']]},'matches':[{'referenceId':claim['referenceId'],'ourAirportsId':claim['ourAirportsId'],'proposedAirportId':claim['assignment']['airportId'],'basis':claim['identityBasis']}],'classification':'identity_only','formalAdmission':False})
 for r in rows(OUT/'bts-crosswalk.jsonl.gz'):cross.append({'sourceFamily':'bts','sourceEntityId':r['airportIdBts'],'matches':[{'referenceId':r['referenceId'],'ourAirportsId':r['ourAirportsId'],'basis':r['basis']}],'airportSeqIds':r['airportSeqIds'],'classification':'identity_only','formalAdmission':False})
 write_rows('global-crosswalk.jsonl.gz',cross)
 report['faaAdmissionProposal']=faa_summary;report['btsSupplement']=json.loads((OUT/'checkpoint-bts.json').read_text());report['results'].update(newEvidenceCompleteBoundedProposals=len(claims),newIcaoRelationshipsProposed=len(claims),newPhysicalAirportIdentitiesProposed=faa_summary['newPhysicalAirportProposals'],newAdmissionEligibleCandidates=0,admissionEligibleConditionalOnOwnerScopes=len(claims),currentlyAuthorizedAdmissions=0)
 report['classifications']=dict(Counter(r['classification'] for r in c))
 for name in ['direct_effective_date','bounded_historical_interval','continuity_inference','identity_only','observation_only','conflicting_evidence','insufficient_evidence']:report['classifications'].setdefault(name,0)
 wd=json.loads((OUT/'checkpoint-wikidata-history.json').read_text());osm=json.loads((OUT/'checkpoint-osm-history.json').read_text());tiles=json.loads((OUT/'checkpoint-osm-entities.json').read_text())
 report['historicalAcquisition']={'wikidata':{k:v for k,v in wd.items() if k not in ['entities','targetQids']},'wikidataTargets':len(wd['targetQids']),'wikidataEntitiesWithoutTargetedHistory':report['results']['wikidataEntities']-len(wd['targetQids']),'osm':{k:v for k,v in osm.items() if k!='objects'},'osmDiscovery':tiles}
 report['limitations']=[s for s in report['limitations'] if 'No new candidate meets' not in s and 'FAA landing' not in s]
 report['limitations'].extend(['FAA supports only 2458 US ICAO continuity proposals over the stated October 2026 core; global historical effective-date coverage remains incomplete.','Evidence-ready FAA proposals are not admitted: existing Owner source/claim scopes must authorize any formal intake. No existing grant is extended.','Wikidata qualifier dates normalize low precision to day-like strings in SPARQL; qualified-relationship-review.json retains original precision, including EDDB year/month qualifiers. None of the three two-sided qualifiers is admitted.'])
 report['limitations']=list(dict.fromkeys(report['limitations']))
 dump(OUT/'coverage-report.json',report)
 catalog=json.loads((OUT/'source-catalog.json').read_text())
 for src in catalog['sources']:
  if src['id']=='faa':src.update(role='Two official NASR effective editions; selected factual airport fields, stable-site ICAO continuity proposals only.',license='US government factual data; 17 USC 105',sourceLock='faa-source-lock.json')
  if src['id']=='bts':src.update(role='AirportID and AirportSeqID lookup data; name/city/state research links only. No actual flight records.',records=report['btsSupplement'])
 dump(OUT/'source-catalog.json',catalog)
 r=report['results'];d=report['productionResolver'];country=report['matchedEntitiesByCountry'];pending_wd=len(wd['targetQids'])-wd['completed'];pending_osm=osm['targets']-osm['completed'];failed_tiles=[t['bbox'] for t in tiles['tiles'] if not t['complete']]
 summary=f'''# Global public-data airport-history enrichment

Research baseline: `bb1046455e949c6c0bf3a18769464cb232bec19e`, data 0.12.0, Schema 3.0.0. Research/query horizon: 1970-01-01 through 2026-11-10. Formal data remains 46 identities, 55 assignments and 112 sources.

## Measured results

| Measure | Result |
| --- | ---: |
| Existing reference records reused | 86,950 |
| Historical event groups joined | 88,330 |
| Existing code-linked candidates processed | 2,484 (2,012 IATA; 472 ICAO) |
| Existing geographic reuse leads processed | 493 |
| High-value event groups processed | 1,198 |
| Wikidata entities enumerated, including all-rank-only entities | {r['wikidataEntities']:,} |
| Wikidata entities with coordinate-supported reference matches | {r['globallyMatchedWikidataEntities']:,} |
| OSM coded airport objects acquired | {r['osmEntities']:,} |
| OSM objects with coordinate-supported reference matches | {r['globallyMatchedOsmEntities']:,} |
| Matched Wikidata / OSM country buckets | {len(country['wikidata'])} / {len(country['osm'])} |
| Wikidata code-statement relationships, deduplicated | {r['wikidataCodeStatementRelationships']:,} |
| Wikidata structured code revisions actually compared | {r['wikidataRevisionCodeChanges']:,} |
| OSM code-tag changes actually compared | {r['osmRevisionCodeChanges']:,} |
| Existing reuse leads with distant distinct Wikidata entities | {r['existingReuseLeadsWithDistantWikidataEntities']:,} |
| Additional distant-entity shared-code leads | {r['additionalDistantEntityCodeLeads']:,} |
| New verified real-world code-change events / solved cross-site reuse | 0 / 0 |
| New evidence-ready bounded ICAO proposals | {len(claims):,} |
| New physical-airport proposals in that batch | {faa_summary['newPhysicalAirportProposals']:,} |
| New IATA admission proposals | 0 |
| Currently Owner-authorized new admissions | 0 |
| Conditional newly resolved code/date queries | {d['newResolvedCodeDateQueries']:,} |
| uncertain → resolved / not_found → resolved | {d['uncertainToResolved']:,} / {d['notFoundToResolved']:,} |
| Existing resolved answers changed / new resolver conflicts | {d['existingResolvedAnswersChanged']} / {d['newConflicts']} |

The global entity, revision and reuse counts are research results. They do not certify an airport's physical continuity or code effective dates. Code-tag/edit timestamps remain observations. Matched entities can have multiple candidate reference associations; no code-only identity is admitted.

## Consolidated FAA admission proposal

The October 1 and October 29, 2026 FAA NASR `APT_BASE.csv` editions provide primary observations at stable FAA site numbers. The batch requires unchanged four-letter ICAO, open status in both editions, coordinate variation no greater than 100 m, a unique existing US reference match within 500 m, agreement on local FAA identifier and ICAO, the same state, and an existing pinned timezone reference. Shared-code collisions and ambiguous matches are withheld. Two dated editions are temporal observations from one issuer, not two independent source families.

The proposed certain whole-date core is **2026-10-02 through 2026-10-27**. The extra guard before the second civil edition date avoids assuming an effective UTC instant or treating an edition date as an airport-local timestamp. Outer allocation/withdrawal bounds remain unknown. This is a bounded continuity inference, not an assertion that the code was allocated on October 1. These are US supplementary gains; they do not constitute global historical completeness.

`proposed-data.json` is a native Schema 3.0.0 **pending research proposal**. New source and assignment states remain pending. Existing airports, assignments, source records and IDs are preserved byte-for-byte as JSON values. New UUIDv4 IDs are reserved in `proposed-airport-id-bindings.json` for this proposal only. `faa-admission-candidates.jsonl.gz` supplies per-site evidence, exact projected rows, row hashes and scoped claims. `faa-source-lock.json` pins both official ZIP archives and CSV member hashes. No OSM material enters the proposal.

Applicable Owner source/claim authorization and the existing admission path remain required. Existing AAI, Korean or other grants are not extended. No new approval system, policy, executor or schema is introduced. The proposal is prepared for one consolidated review; it has not been executed as a formal admission.

## Resolver measurement

The actual production `resolveAirport` ran {d['actualResolverCalls']:,} times on assignment-boundary partitions across {d['uniqueSchemeCodeKeys']:,} namespace/code keys. Exact day weights cover the full requested horizon. The {d['newResolvedCodeDateQueries']:,} gained query cells equal the 26-day core across the {len(claims):,} proposed ICAO relationships. Only the simulation marks new scoped records reviewed in memory. There are **zero published production gains until admission**. The hypothetical unknown outer bounds also change {d['notFoundToUncertainNotCoverageGain']:,} not_found cells to uncertain; these are explicitly excluded from coverage gains. These synthetic query cells are not historical flights. No real flight corpus was acquired, and affected-flight counts are unknown.

## Exact source gaps and uncertainty

- Wikidata: {wd['completed']:,}/{len(wd['targetQids']):,} targeted entity histories complete; {pending_wd:,} pending. `{wd['status']}` checkpoint records per-entity counts. Initial HTTP 429 responses were followed by paced resumable retrieval. Other entities have statement enrichment without targeted revision retrieval. Property-comment selection can miss uncommented/bulk-import edits; this is not an exhaustive content diff of every entity revision.
- OSM: {osm['completed']:,}/{osm['targets']:,} targeted object histories complete; {pending_osm:,} pending. Failed discovery tiles: `{failed_tiles}`. API failures and exact URLs are in the source lock. Current-object discovery does not enumerate all deleted airports; codeless objects remain outside the coded-airport acquisition scope.
- Three Wikidata relationships have both start/end qualifiers. They are secondary assertions, not new admitted intervals. ISL is deprecated and conflicts with treating inauguration as allocation; EDDB includes year/month precision and conflicts with interpreting a Wikidata entity's end as physical/code withdrawal. The Bicol LGP claim needs primary source authority and effective-date verification. Raw precision and review notes are preserved.
- BTS lookup acquisition links {report['btsSupplement']['nameCityStateMatches']:,} US references on airport name, city and state. AirportSeqID prefix links are leads without effective chronology; lookup rows are not flights.
- FAA coverage is limited to the two pinned October 2026 editions. Earlier historical NASR epochs and actual flight validation remain gaps. Country and state distributions, all exclusions and pending claims are explicit in the JSON reports.

## Licensing and reproducibility

JSONL names below are logical dataset names. Resolve them through `jsonl-shards.json`; oversized datasets use sequential `.000.jsonl.gz` shards, each at most 8 MiB uncompressed. Concatenating decompressed shards in manifest order exactly reconstructs the original serialized records. Both manifests include hashes, compressed/uncompressed sizes and record counts.

See `LICENSES.md`. OSM databases and combined OSM-derived research joins retain ODbL obligations and attribution. Restricted source documents are not redistributed. FAA projections omit contact fields and third-party PDFs. The source lock contains exact URLs, acquisition outcomes, hashes, reused-input hashes and scoped citations.

Fresh acquisition commands (successful responses cache by URL; failed requests remain resumable):

```sh
python3 scripts/evidence/public_data.py acquire
python3 scripts/evidence/public_data.py statements
python3 scripts/evidence/public_data.py complete_entities
python3 scripts/evidence/public_data.py osm_acquire
python3 scripts/evidence/public_data.py bts
python3 scripts/evidence/public_data.py history
```

Rebuild from the delivered locked research snapshots, without repeating the worldwide scan or downloading OurAirports:

```sh
python3 scripts/evidence/public_data.py build
python3 scripts/evidence/public_data.py faa
node scripts/evidence/public_data_coverage.ts
python3 scripts/evidence/public_data.py finalize
python3 scripts/evidence/public_data.py validate
```

FAA can rebuild from the delivered field projections when original ZIPs are not cached. Original downloads remain reproducible from the pinned official URLs and hashes. Do not run fresh acquisition to reproduce a frozen snapshot against today's mutable source state.

Validation: native schema validation of pending and simulated datasets; production resolver differential; the public-data identity and sharding regression suite (`pnpm test:public-data`, explicitly executed by CI); existing TypeScript checks, formal data validation and 444 repository tests. Formal data, Keepraw-Fly and PR #114 are unchanged. Research-only merge does not admit the FAA proposals; no release or auto-merge is requested.
'''
 (OUT/'summary.md').write_text(summary)
 dump(OUT/'artifact-manifest.json',{'formatVersion':2,'maxUncompressedShardBytes':MAX_SHARD_BYTES,'artifacts':[artifact_metadata(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ['artifact-manifest.json','validation.json']]})
 print('finalized',r['globallyMatchedWikidataEntities'],r['globallyMatchedOsmEntities'],d['newResolvedCodeDateQueries'],flush=True)

def validate():
 import subprocess
 expected={'referenceRecords':86950,'historicalEventGroups':88330,'codeLinkedCandidates':2484,'existingGeographicReuseLeads':493,'highValueEventGroups':1198}
 report=json.loads((OUT/'coverage-report.json').read_text())
 for k,v in expected.items():assert report['processing'][k]==v,(k,report['processing'][k])
 validate_shards()
 manifest=json.loads((OUT/'artifact-manifest.json').read_text())
 expected_files={p.name for p in OUT.iterdir() if p.is_file() and p.name not in ['artifact-manifest.json','validation.json']}
 assert expected_files=={a['path'] for a in manifest['artifacts']},'Artifact manifest inventory mismatch'
 for a in manifest['artifacts']:
  assert artifact_metadata(OUT/a['path'])==a,a['path']
 original=subprocess.check_output(['git','show','bb1046455e949c6c0bf3a18769464cb232bec19e:data/airports.json'],cwd=ROOT);assert original==(ROOT/'data/airports.json').read_bytes()
 required=['source-catalog.json','source-lock.json','wikidata-entities.jsonl.gz','wikidata-history.jsonl.gz','osm-airport-entities.jsonl.gz','osm-history.jsonl.gz','global-crosswalk.jsonl.gz','historical-code-candidates.jsonl.gz','physical-reuse-candidates.jsonl.gz','coverage-report.json','summary.md']
 for name in required:
  if name.endswith('.jsonl.gz'):dataset_paths(OUT/name)
  else:assert (OUT/name).is_file(),name
 for c in rows(OUT/'faa-admission-candidates.jsonl.gz'):
  a,b=c['editionRows'];assert a['SITE_NO']==b['SITE_NO']==c['faaSiteNo'];assert a['ICAO_ID']==b['ICAO_ID']==c['assignment']['code'];assert a['EFF_DATE']=='2026/10/01' and b['EFF_DATE']=='2026/10/29';assert c['assignment']['verificationStatus']=='pending' and c['assignment']['verifiedOn'] is None;assert c['assignment']['validFrom']['earliest'] is None and c['assignment']['validTo']['latest'] is None
  assert c['rowSha256']==[hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest() for v in [a,b]]
 d=report['productionResolver'];assert d['existingResolvedAnswersChanged']==d['newConflicts']==0;assert d['newResolvedCodeDateQueries']==26*len(list(rows(OUT/'faa-admission-candidates.jsonl.gz')))
 dump(OUT/'validation.json',{'status':'passed','checks':['required artifacts present','complete fixed candidate-universe counts','all frozen artifact hashes and size/record metadata','ordered deterministic JSONL shards at most 8 MiB','byte-identical decompressed dataset reconstruction','formal data byte-identical to specified base','FAA site/code/edition/row-hash consistency','all proposed assignments pending','unknown outer code-allocation bounds preserved','actual resolver gain matches 26-day cores','no existing resolved answer changes or new conflicts']})
 print('Public data package integrity passed',flush=True)

def reproduce():
 """Rebuild in isolation using only the frozen package, with an empty cache."""
 import contextlib,io,shutil,subprocess,tempfile
 global OUT,CACHE
 original_out,original_cache=OUT,CACHE
 before={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}
 with tempfile.TemporaryDirectory(prefix='public-data-replay-',dir=ROOT/'work') as directory:
  scratch=Path(directory)
  try:
   OUT=scratch/'package';CACHE=scratch/'empty-cache';shutil.copytree(original_out,OUT)
   with contextlib.redirect_stdout(io.StringIO()):
    build();faa()
    subprocess.run(['node','scripts/evidence/public_data_coverage.ts',str(OUT)],cwd=ROOT,check=True,stdout=subprocess.PIPE)
    finalize();validate()
   after={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}
   changed=[p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)]
   if changed:raise ValueError('Offline reproduction changed: '+', '.join(sorted(changed)))
   if CACHE.exists():raise ValueError('Offline reproduction used acquisition cache')
  finally:OUT,CACHE=original_out,original_cache
 print('Byte-identical offline reproduction passed:',len(before),'artifacts; no acquisition cache or global history scan')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['acquire','history','crosswalk','statements','build','osm_acquire','bts','complete_entities','faa','osm_history','finalize','validate','shard_existing','reproduce']);a=p.parse_args();globals()[a.command]()
