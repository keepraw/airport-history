"""Claim-specific IATA transfer research. Full originals stay in ignored work/.

The immutable global/market stages are inputs, never rewritten by this stage.
No airport, country, event date, code boundary or human decision is inferred
by the collector. Those are explicit, reviewable assessment data.
"""
import argparse
import collections
import copy
import datetime as dt
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request

import global_batch as gb
import market_batch as mb

ROOT = gb.ROOT
BASE = ROOT / 'research/evidence/transfers'
OUT = BASE / 'generated'
CACHE = ROOT / 'work/transfer-originals'
FIELDS = [('airports','airportId'),('assignments','assignmentId'),('names','nameId'),('sources','sourceId')]
UNKNOWN = {'earliest':None,'latest':None,'precision':'unknown'}


def read(path):
    return json.loads(path.read_text())


def locate(raw, text, citation, encoding='utf-8'):
    """Offsets are in the stated representation, never pretend hrefs are body text."""
    quote = citation['quote']
    if citation['representation']=='decoded_html':
        representation=raw.decode(encoding)
        start=representation.find(quote)
        if start<0:raise ValueError('Cited HTML attribute absent')
        return {**citation,'page':None,'characterStart':start,'characterEnd':start+len(quote)}
    if citation['representation']!='normalized_text':raise ValueError('Unknown citation representation')
    quote=' '.join(quote.split())
    for page,part in enumerate(text.split('\f'),1):
        start=' '.join(part.split()).find(quote)
        if start>=0:return {**citation,'quote':quote,'page':page if '\f' in text else None,
                            'characterStart':start,'characterEnd':start+len(quote)}
    raise ValueError('Cited original text absent: '+quote)


def retain(entry, raw, accessed, retrieval, directory=BASE):
    """Only minimal per-claim quotations enter the repository, never full copies."""
    text=gb.extract(raw,entry.get('encoding','utf-8'))
    spans=[locate(raw,text,c,entry.get('encoding','utf-8')) for c in entry['citations']]
    if len(text)<100:raise ValueError('Not a usable original')
    # Explicit ceiling prevents accidental inclusion of a whole HTML/PDF export.
    if sum(len(c['quote']) for c in spans)>1800:raise ValueError('Excerpts exceed per-publication review limit')
    excerpt={'originalSha256':gb.sha(raw),'textOriginalSha256':gb.sha(text.encode()),'spans':spans}
    relative='excerpts/'+entry['sourceId']+'.json'
    gb.write(directory/relative,excerpt)
    return {k:v for k,v in {**entry,'accessedAt':accessed,'retrievalUrl':retrieval,
            'originalSha256':excerpt['originalSha256'],'originalBytes':len(raw),
            'textOriginalSha256':excerpt['textOriginalSha256'],'retainedPath':relative,
            'retainedSha256':gb.sha((directory/relative).read_bytes()),
            'extractionTool':'pdftotext-layout' if raw.startswith(b'%PDF-') else 'stdlib-HTMLParser-v1',
            'rights':{'mode':'metadata_and_short_excerpts','fullRedistributionPermission':'not_established',
                      'note':'Publisher rights retained; repository MIT license does not cover this work. No full original, image, chart or full extraction redistributed.'}}.items() if k!='citations'}


def fetch(only=None,limit=None,retry_failures=False,recover=False,directory=BASE,cache=CACHE):
    directory.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    catalog=read(directory/'catalog.json')['sources']
    ids=[s['sourceId'] for s in catalog]
    if len(ids)!=len(set(ids)) or any(not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,100}',s) for s in ids):
        raise ValueError('Catalog needs unique safe source IDs')
    with (directory/'.acquisition.lock').open('w') as mutex:
        try:fcntl.flock(mutex,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another transfer collector is running')
        path=directory/'source-lock.json'
        lock=read(path) if path.exists() else {'formatVersion':1,'sources':[],'attempts':[]}
        if path.exists():verify_sources(directory)
        existing={s['sourceId']:s for s in lock['sources']}
        failed={r['sourceId'] for r in lock['attempts'] if r['status']=='failed'}
        rows=[]
        for e in catalog:
            sid=e['sourceId']
            if only and sid not in only:continue
            if not recover and (sid in existing or (sid in failed and not retry_failures)):continue
            if limit is not None and len(rows)>=limit:break
            url=e.get('retrievalUrl',e['url'])
            if not url.startswith('https://'):raise ValueError('Explicit HTTPS source required')
            row={'sourceId':sid,'requestedUrl':url,'accessedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}
            try:
                for attempt in range(3):
                    try:
                        request=urllib.request.Request(url,headers={'User-Agent':'Keepraw-Airport-History/1.0 (public historical research)'})
                        with urllib.request.urlopen(request,timeout=25) as response:
                            raw=response.read(32*1024*1024+1);final=response.geturl()
                        break
                    except urllib.error.HTTPError as error:
                        if error.code not in (429,502,503,504) or attempt==2:raise
                        time.sleep(attempt+1)
                if len(raw)>32*1024*1024:raise ValueError('Original exceeds bounded acquisition size')
                if sid in existing and gb.sha(raw)!=existing[sid]['originalSha256']:
                    raise ValueError('Original changed; do not overwrite locked evidence')
                if recover and sid not in existing:raise ValueError('Recovery requires a locked original')
                # All extraction and citation checks precede either checkpoint update.
                text=gb.extract(raw,e.get('encoding','utf-8'))
                for c in e['citations']:locate(raw,text,c,e.get('encoding','utf-8'))
                temporary=cache/(sid+'.raw.tmp');temporary.write_bytes(raw);temporary.replace(cache/(sid+'.raw'))
                if not recover:
                    source=retain(e,raw,row['accessedAt'],final,directory)
                    lock['sources'].append(source);existing[sid]=source
                row.update(status='original_hash_verified',originalSha256=gb.sha(raw))
            except (OSError,ValueError,subprocess.CalledProcessError) as error:
                row.update(status='failed',error=str(error),nextAction='Find an authorized original or public archival capture; do not bypass access controls.')
            rows.append(row)
            if not recover:
                lock['attempts'].append(row);gb.write(path,lock)
            time.sleep(.35)
        if recover:gb.write(cache/'recovery-report.json',rows)
        return rows


def verify_sources(directory=BASE, cache=None):
    lock=read(directory/'source-lock.json');sources={};spans={}
    catalog={s['sourceId']:s for s in read(directory/'catalog.json')['sources']}
    for s in lock['sources']:
        sid=s['sourceId']
        if sid in sources:raise ValueError('Duplicate original')
        entry=catalog.get(sid)
        if entry is None:raise ValueError('Locked source absent from catalog')
        if any(s.get(k)!=entry.get(k) for k in ['url','title','publisher','publicationDate','documentEffectiveDate',
                                               'sourceType','sourceFamily','originalPublicationKey','reusesPublication']):
            raise ValueError('Catalog and locked publication provenance differ')
        path=(directory/s['retainedPath']).resolve()
        if not path.is_relative_to(directory.resolve()):raise ValueError('Excerpt escapes snapshot')
        if gb.sha(path.read_bytes())!=s['retainedSha256']:raise ValueError('Changed retained quotation')
        e=read(path)
        if e['originalSha256']!=s['originalSha256'] or e['textOriginalSha256']!=s['textOriginalSha256']:
            raise ValueError('Detached original hash mismatch')
        if s['rights']['mode']!='metadata_and_short_excerpts':raise ValueError('Full redistribution not authorized')
        for c in e['spans']:
            if c['characterEnd']-c['characterStart']!=len(c['quote']):raise ValueError('Invalid original locator')
            if c['citationId'] in spans:raise ValueError('Duplicate citation ID')
            spans[c['citationId']]=(sid,c)
        expected={c['citationId']:(c['representation'],c['quote'] if c['representation']=='decoded_html' else ' '.join(c['quote'].split())) for c in entry['citations']}
        if expected!={c['citationId']:(c['representation'],c['quote']) for c in e['spans']}:
            raise ValueError('Retained original differs from catalog citations')
        if cache is not None:
            raw=(cache/(sid+'.raw')).read_bytes()
            if gb.sha(raw)!=s['originalSha256']:raise ValueError('Original hash mismatch')
            text=gb.extract(raw,s.get('encoding','utf-8'))
            if gb.sha(text.encode())!=s['textOriginalSha256']:raise ValueError('Full extraction hash mismatch')
            for c in e['spans']:
                if locate(raw,text,{k:v for k,v in c.items() if k not in ['page','characterStart','characterEnd']},s.get('encoding','utf-8'))!=c:
                    raise ValueError('Original quotation does not reproduce')
        sources[sid]=s
    return sources,spans


def verify():
    a=read(BASE/'assessments.json');sources,spans=verify_sources(BASE)
    if a['decision']!='pending' or a['reviewer'] is not None:raise ValueError('Human approval invented')
    if gb.sha((ROOT/'data/airports.json').read_bytes())!=a['formalBaselineSha256']:raise ValueError('Formal baseline changed')
    facts={}
    for f in a['facts']:
        if f['decision']!='pending' or f['reviewer'] is not None:raise ValueError('Fact approval invented')
        if f['factId'] in facts:raise ValueError('Duplicate fact')
        if any(spans[c][0]!=f['sourceId'] for c in f['citationIds']):raise ValueError('Claim detached from original')
        if f.get('observation'):
            o=f['observation']
            if o['latest']>a['cutoff'] or o['earliest']>o['latest']:raise ValueError('Invalid observation bounds')
        facts[f['factId']]=f
    market=read(mb.BASE/'assessments.json');global_a=read(gb.BASE/'assessments.json')
    prior={f['factId']:f for f in global_a['facts']+market['facts']}
    if len({c['caseKey'] for c in a['cases']})!=len(a['cases']):raise ValueError('Duplicate case')
    allfacts={**prior,**facts}
    for c in a['cases']:
        if c['decision']!='pending' or c['reviewer'] is not None:raise ValueError('Case approval invented')
        if any(f not in allfacts for f in c['factIds']):raise ValueError('Unknown case fact')
        if c['oldSite']['airportId']==c['newSite']['airportId']:raise ValueError('Different physical sites merged')
        if c['classification']=='complete_same_iata_candidate':
            for side in ['oldSite','newSite']:
                for fid in c[side]['iataObservations']:
                    f=allfacts[fid]
                    if not f.get('observation') and not f.get('observedOn'):raise ValueError('Undated association counted as dated')
                    if not any(b['scheme']=='IATA' and b['siteKey']==c[side]['siteKey'] and b['code'] in c['codes'] for b in f['codeBindings']):
                        raise ValueError('Two-sided candidate lacks the claimed airport-specific IATA binding')
                if not c[side]['iataObservations']:raise ValueError('One-sided chain claimed complete')
    return a,sources,facts,allfacts


def propose(a,sources,facts):
    base=read(ROOT/'data/airports.json');proposed=read(mb.OUT/'proposed-data.json');dossier=[]
    existing={s['sourceId'] for s in proposed['sources']}
    for sid,s in sources.items():
        if sid not in existing:
            proposed['sources'].append({'sourceId':sid,'title':s['title'],'url':s['url'],
                'accessedOn':s['accessedAt'][:10],'verificationStatus':'pending','sourceType':s['sourceType'],
                'license':{'id':'LicenseRef-Quotation-Only','url':s['url'],'note':s['rights']['note']},
                'note':'Original SHA-256 '+s['originalSha256']+'. Exact claim scope, archival capture and dependence are in the transfer source lock.'})
    airports={s['airportId']:s for s in proposed['airports']}
    for s in a['newSites']:
        if s['airportId'] in airports:raise ValueError('Duplicate permanent physical airport ID')
        if s['ourAirports'] and any(r['externalIds'].get('ourAirports')==s['ourAirports'] for r in proposed['airports']):
            raise ValueError('External physical hypothesis already reserved')
        proposed['airports'].append({'airportId':s['airportId'],
            'name':{'value':s['name'],'status':'reference','sourceIds':s['sourceIds'],'note':'Display name, not an official name interval.'},
            'coordinates':{'value':s['coordinates'],'status':'reference','sourceIds':s['coordinateSourceIds'],'note':s['assessmentZh']},
            'timezone':{'value':None,'status':'unknown','sourceIds':[],'note':'No historical timezone determination.'},
            'externalIds':{'ourAirports':s['ourAirports']}})
        airports[s['airportId']]=proposed['airports'][-1]
        dossier.append({'recordId':s['airportId'],'recordType':'physicalAirport','caseKey':s['caseKey'],
            'decision':'pending','reviewer':None,'factIds':s['factIds'],'identityAssessment':s['assessmentZh'],
            'approvalBlockers':['Human physical-site and coordinate review required.']})
    assignments={s['assignmentId']:s for s in proposed['assignments']}
    formal={s['assignmentId'] for s in base['assignments']}
    for r in a['assignmentReviews']:
        aid=r['assignmentId'];enrichment=aid in assignments
        if aid in formal:raise ValueError('Published assignment revisions require a separate explicit proposal')
        if enrichment:
            record=assignments[aid]
            if any(record[k]!=r[k] for k in ['airportId','scheme','code']):raise ValueError('Pending identity changed')
            # Supplemental evidence does not silently replace an earlier valid judgment.
            record['sourceIds']=sorted(set(record['sourceIds']+r['sourceIds']))
        else:
            record={k:copy.deepcopy(r[k]) for k in ['assignmentId','airportId','scheme','code','sourceIds','evidenceType','note']}
            record.update(validFrom=copy.deepcopy(UNKNOWN),validTo=copy.deepcopy(UNKNOWN),verificationStatus='pending',verifiedOn=None)
            proposed['assignments'].append(record);assignments[aid]=record
        dossier.append({'recordId':aid,'recordType':'assignment','caseKey':r['caseKey'],
            'decision':'pending','reviewer':None,'factIds':r['factIds'],'revisesPendingOnly':enrichment,
            'boundaryAssessment':r['boundaryAssessment'],'continuityAssessment':r['continuityAssessment'],
            'approvalBlockers':r['approvalBlockers'],'observations':r['observations']})
    for collection,key in FIELDS:
        now={r[key]:r for r in proposed[collection]}
        if len(now)!=len(proposed[collection]) or any(now.get(r[key])!=r for r in base[collection]):raise ValueError('Published record changed')
    return proposed,dossier


def packets(a,sources,dossier):
    # Reuse existing event ownership. A supplementary case is not a new event.
    batches=list(gb.read_jsonl(gb.OUT/'review-packets.jsonl.gz'))+read(mb.OUT/'review-packets.json')
    for batch in batches:
        if batch.get('baseCommitFingerprint'):
            batch['originalSnapshotBaseCommitFingerprint']=batch.pop('baseCommitFingerprint')
        else:
            batch['originalSnapshotBaseCommit']=batch['baseCommit']
        batch['baseCommit']=a['formalBaseCommit']
    for case in a['cases']:
        related=[d for d in dossier if d['caseKey']==case['caseKey']]
        if not related:continue
        owners=[e for b in batches for e in b['events'] if e['eventGroupId']==case['ownerEventGroupId']]
        if len(owners)!=1:raise ValueError('Supplement must reuse one existing event owner')
        event=owners[0];sids=sorted({s for r in a['assignmentReviews'] if r['caseKey']==case['caseKey'] for s in r['sourceIds']})
        sids=sorted(set(sids+[s for site in a['newSites'] if site['caseKey']==case['caseKey'] for s in site['sourceIds']]))
        event['sourceIds']=sorted(set(event['sourceIds']+sids))
        event['proposedRecordIds']=sorted(set(event.get('proposedRecordIds',[])+[d['recordId'] for d in related]))
        event['transferSupplement']={'decision':'pending','reviewer':None,'classification':case['classification'],
                                    'factIds':case['factIds'],'boundaryDecision':case['boundaryDecisionZh']}
        for claim in ['iata','physicalIdentity','historicalBoundary']:
            event['claims'][claim]['sourceIds']=sorted(set(event['claims'][claim]['sourceIds']+sids))
        for batch in batches:
            if event not in batch['events']:continue
            present={s['sourceId'] for s in batch['sources']}
            for sid in sids:
                if sid in present:continue
                if sid not in sources:
                    # Reused primary physical evidence remains under its prior owner.
                    previous=next(s for s in read(gb.BASE/'source-lock.json')['sources'] if s['sourceId']==sid)
                else:previous=sources[sid]
                batch['sources'].append({'sourceId':sid,'url':previous['url'],'sourceType':previous.get('sourceType','primary'),
                    'accessedOn':previous['accessedAt'][:10],'supportedFacts':['Only explicitly cited transfer supplement claims.'],
                    'limitations':['Code association is not an allocation or withdrawal notice; no whole-day continuity assumed.'],
                    'accessResult':'Original hash and retained quotations verified.',
                    'license':{'id':'LicenseRef-Quotation-Only','note':'Publisher rights retained; no full redistribution.'}})
    gb.validate_batch_series(batches)
    return batches


def build(output=OUT):
    a,sources,facts,allfacts=verify();output.mkdir(parents=True,exist_ok=True)
    proposed,dossier=propose(a,sources,facts);batches=packets(a,sources,dossier)
    gb.write(output/'proposed-data.json',proposed);gb.write(output/'dossier.json',dossier)
    gb.write(output/'review-packets.json',batches);gb.write(output/'matrix.json',a['cases'])
    try:gb.validate_admission(read(ROOT/'data/airports.json'),proposed,batches,dossier)
    except ValueError as error:
        if 'explicit claim review' not in str(error):raise
    else:raise ValueError('Pending transfer research passed formal admission')
    subprocess.run(['node','scripts/evidence/global_coverage.ts',str(output)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['node','scripts/evidence/transfer_coverage.ts',str(output)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    coverage=read(output/'transfer-coverage.json')
    combined=read(output/'query-coverage.json');previous=read(mb.OUT/'query-coverage.json')
    code_counts=lambda report:{scheme:sum(r['potentialNewResolvedQueries'] for k,r in report['byCode'].items() if k.startswith(scheme+':')) for scheme in ['IATA','ICAO']}
    focus=[c for c in a['cases'] if c['sameIataLead']]
    m={'cases':len(a['cases']),'prioritySameIataCandidates':sum(c['sameIataLead'] for c in a['cases']),
       'countries':sorted({c['country'] for c in a['cases']}),
       'newCitedPublications':len({s['originalPublicationKey'] for s in sources.values() if not s.get('reusesPublication')}),
       'lockedComponents':len(sources),'newClaimJudgments':len(facts),
       'newDatedIataObservations':sum(bool(f.get('observation') and f['codeBindings']) and not f.get('notNewHistoricalFact',False) for f in facts.values()),
       'newHistoricalEventsBeyondPriorResearch':sum(c.get('newExecutedEventBeyondPriorResearch',False) for c in a['cases']),
       'completeSameIataAssociationCandidates':sum(c['classification']=='complete_same_iata_candidate' for c in a['cases']),
       'directBothSidesCandidates':sum(c.get('bothSidesDirect',False) for c in a['cases']),
       'exactCodeHandoverDates':sum(bool(c.get('codeHandoverDate')) for c in a['cases']),'newPhysicalRecords':len(a['newSites']),
       'newAssignments':sum(not d.get('revisesPendingOnly') and d['recordType']=='assignment' for d in dossier),
       'supplementedPendingAssignments':sum(d.get('revisesPendingOnly',False) for d in dossier),
       'newDistinctPhysicalSiteCodeAssociationFacts':sum(not d.get('revisesPendingOnly') and d['recordType']=='assignment' for d in dossier),
       'oldSideDatedIataObservations':sum(len(c['oldSite']['iataObservations']) for c in focus),
       'newSideDatedIataObservations':sum(len(c['newSite']['iataObservations']) for c in focus),
       'exactExecutedEventDates':sum(c['eventDate']['precision']=='exact' for c in a['cases']),
       'partialExecutedEventDates':sum(c['eventDate']['precision']!='exact' for c in a['cases']),
       'eventYears':sorted({int(c['eventDate']['earliest'][:4]) for c in a['cases']}),
       'combinedPotentialResolvedQueries':code_counts(combined),'previousStagePotentialResolvedQueries':code_counts(previous),
       'pendingRecordReviews':len(dossier),'humanApproved':0,'formalAdmissions':0,
       'formalCounts':[27,43,3,77],'formalVersion':'0.8.0',**coverage['totals']}
    gb.write(output/'metrics.json',m)
    years=[]
    for c in a['cases']:
        for year in range(2015,2027):
            related=[allfacts[f] for f in c['factIds']]
            inspected=any(f['codeBindings'] and
                          ((f.get('observation') and int(f['observation']['earliest'][:4])<=year<=int(f['observation']['latest'][:4])) or
                           (f.get('observedOn') and int(f['observedOn'][:4])==year)) for f in related)
            event=bool(c['eventDate'] and str(year)==c['eventDate']['earliest'][:4])
            years.append({'country':c['country'],'year':year,'caseKey':c['caseKey'],'namespace':'IATA',
                          'eventInThisYear':event,'datedCodeObservationInspected':inspected,
                          'scopedFactJudgmentInThisYear':event or inspected,'uninspectedYearStatus':'unknown' if not event and not inspected else None,
                          'reviewableAssociationProposalEvent':event and any(d['caseKey']==c['caseKey'] for d in dossier),
                          'recommendedForFormalIntervalApproval':False,
                          'humanApproved':False,'formallyAdmitted':False,'exhaustiveCountryCoverage':False})
    gb.write(output/'country-year.json',{'scope':'Only the explicitly investigated cases; uninspected years/countries are unknown, never no-change.','rows':years})
    documents(output,a,sources,facts,m,coverage,dossier)
    inputs=[BASE/'assessments.json',BASE/'catalog.json',BASE/'source-lock.json',BASE/'discovery-log.json',ROOT/'data/airports.json',
            mb.OUT/'manifest.json',mb.OUT/'proposed-data.json',mb.OUT/'review-packets.json',gb.OUT/'review-packets.jsonl.gz',
            ROOT/'scripts/evidence/transfer_batch.py',ROOT/'scripts/evidence/transfer_coverage.ts',ROOT/'scripts/evidence/global_coverage.ts']
    inputs+=sorted((BASE/'excerpts').glob('*.json'))
    gb.write(output/'manifest.json',{'inputs':{str(p.relative_to(ROOT)):gb.sha(p.read_bytes()) for p in inputs},
        'outputs':{str(p.relative_to(output)):gb.sha(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='manifest.json'}})


def documents(output,a,sources,facts,m,coverage,dossier):
    lines=['# PR #15 IATA 跨场址补证与待审核清单','',
           '本报告是原全球／60 组市场调查的增量补证；此前快照保持原样。全部提案 pending、verifiedOn=null，所有判断 reviewer=null。正式 0.8.0 的 27 机场／43 分配／3 名称／77 来源完全未改。','',
           f"实际推进 {m['prioritySameIataCandidates']} 个同码候选，另核实金边 1 组不同代码替代；新增引用出版物 {m['newCitedPublications']} 份、锁定组件 {m['lockedComponents']} 份、事实判断 {m['newClaimJudgments']} 项（不是同等数量的独立新事件）。完整双侧**关联候选** {m['completeSameIataAssociationCandidates']} 组，其中双侧直接代码陈述 {m['directBothSidesCandidates']} 组；行政交接日可确定 {m['exactCodeHandoverDates']} 组。不得把关联候选称为已证实连续分配链。",'',
           f"新增物理记录 {m['newPhysicalRecords']}、IATA 记录 {m['newAssignments']}、补证既有 pending IATA 记录 {m['supplementedPendingAssignments']}；新增 ICAO 记录 0。新增正式查询 0。相对前一 pending 假设新增 resolved {m['incrementalResolvedDates']}，失去 {m['previousHypotheticalResolvedDatesNowUncertain']}；后者来自新增旧场可能区间，保留并报告而不缩边界掩盖。",'',
           f"同码候选共取得旧侧有日期关联 {m['oldSideDatedIataObservations']} 次、新侧 {m['newSideDatedIataObservations']} 次（含复用 CAAP；抓取日与表内月份不代表整日有效）。新增独立的场址/代码关联判断 {m['newDistinctPhysicalSiteCodeAssociationFacts']} 项；{m['newClaimJudgments']} 个细项判断包含补证和复核，不冒充同等数量的新事件。实际事件精确到日 {m['exactExecutedEventDates']}、仅月/年范围 {m['partialExecutedEventDates']}，事件年为 {m['eventYears']}。",'',
           '联合提案的潜在查询（含此前成果，不能归功本次新增）：'+json.dumps(m['combinedPotentialResolvedQueries'],ensure_ascii=False)+'；上一阶段 '+json.dumps(m['previousStagePotentialResolvedQueries'],ensure_ascii=False)+'。完整同码候选本次潜在 resolved 仍为 0，行政边界没有被资料补齐。','',
           '## 证据矩阵','',
           '| 案例 | 旧场有日期 IATA 观察 | 新场有日期 IATA 观察 | 分类 | 本轮新增 resolved |',
           '|---|---:|---:|---|---:|']
    for c in a['cases']:
        r=coverage['cases'][c['caseKey']]
        lines.append(f"| {c['labelZh']} | {len(c['oldSite']['iataObservations'])} | {len(c['newSite']['iataObservations'])} | {c['classificationZh']} | {r['incrementalResolvedDates']} |")
    lines += ['', '观察数是出版物中有日期的关联，不是独立分配事实；同页不同捕获及同机构连续版本不能作为独立交叉验证。目录月份、网页抓取时间、予定生效、实际首航和代码分配日期分别保存。','',
              '## 逐条待审（不是批准建议）','']
    for i,c in enumerate(a['cases'],1):
        lines += [f"### {i}. {c['labelZh']}（{c['country']}）",'',c['findingZh'],'']
        for side,title in [('oldSite','旧场'),('newSite','新场')]:
            s=c[side]
            lines.append(f"- {title} `{s['airportId']}`：{s['name']}；参考坐标 {json.dumps(s['coordinates'],ensure_ascii=False)}；{s['identityStatusZh']}；有日期代码观察："+', '.join(s['iataObservations'])+'。')
        lines += ['', '迁场：'+json.dumps(c['eventDate'],ensure_ascii=False)+'；'+c['eventDateAssessmentZh'],
                  '', '代码时间：'+c['boundaryDecisionZh'],'','独立性：'+c['independenceZh'],'',
                  '阻塞／下一步：'+'；'.join(c['gapsZh']),'']
        lines += ['本案原件核查范围：'+c['scopedInvestigationZh']+'；附加获取／读件记录：'+', '.join(c['examinedDiscoverySourceIds'])+'。','']
        for fid in c['factIds']:
            if fid not in facts:
                lines.append(f'- 复用既有事实 `{fid}`（原 global/markets 快照、哈希、定位保持原样）。');continue
            f=facts[fid];s=sources[f['sourceId']]
            lines.append(f"- `{fid}`：[{s['title']}]({s['url']})；{f['conclusionZh']}；原件 `{s['originalSha256']}`；引用 `"+'`, `'.join(f['citationIds'])+'`。')
        lines += ['', '实际解析器逐日结果：'+json.dumps(coverage['cases'][c['caseKey']],ensure_ascii=False),'']
        for d in dossier:
            if d['caseKey']==c['caseKey']:lines.append(f"- 待审 `{d['recordId']}`：{d['recordType']}，pending / reviewer=null；"+'；'.join(d['approvalBlockers']))
        lines.append('')
    lines += ['## 离线复现与继续采集','',
              '`pnpm evidence:transfers build` 从锁定最小摘录及既有快照确定性离线重建。`pnpm evidence:transfers verify` 验证摘录哈希及脱离原件的哈希出处；不能从摘录重构完整原件。', '',
              '`pnpm evidence:transfers fetch --source <id> --limit 5` 只采目录中的新原件，断点跳过已取得项；`--retry-failures` 明确重试失败，`--recover` 校验重新下载字节与锁定 SHA。完整原件只存 ignored work/；动态页面改变时拒绝覆盖。可用 `verify --cache work/transfer-originals` 核验私有原件及完整提取，不把全文加入 Git。', '',
              '继续工作应按 matrix 的 gaps 补充 catalog/citations/assessments，再采集和构建；无需重扫全球目录。保留 discovery-log 中获取失败、未认证镜像、城市代码表等排除原因。原全球和市场报告是阶段快照，最终采用本补证的联合解析结果。','']
    (output/'RESULTS.zh-CN.md').write_text('\n'.join(lines).rstrip()+'\n')


def validate(output=OUT):
    verify();manifest=read(output/'manifest.json')
    for p,h in manifest['inputs'].items():
        if gb.sha((ROOT/p).read_bytes())!=h:raise ValueError('Changed transfer input: '+p)
    for p,h in manifest['outputs'].items():
        if gb.sha((output/p).read_bytes())!=h:raise ValueError('Changed transfer output: '+p)
    print('Transfer originals provenance, pending judgments and deterministic outputs verified')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['fetch','build','verify','validate'])
    p.add_argument('--source',action='append');p.add_argument('--limit',type=int);p.add_argument('--retry-failures',action='store_true')
    p.add_argument('--recover',action='store_true');p.add_argument('--output',type=Path,default=OUT);p.add_argument('--cache',type=Path)
    args=p.parse_args()
    if args.command=='build':build(args.output)
    elif args.command=='validate':validate(args.output)
    elif args.command=='verify':
        verify();sources,_=verify_sources(cache=args.cache);print('Verified '+str(len(sources))+' retained source components'+(' and private full originals' if args.cache else '; full-original re-extraction not claimed'))
    else:print(json.dumps(fetch(args.source,args.limit,args.retry_failures,args.recover),ensure_ascii=False,indent=2))
