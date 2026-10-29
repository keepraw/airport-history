"""Priority-market research: scoped originals, balanced dual queues, pending proposals.

The earlier worldwide snapshot stays a separate, reproducible research input.
No function writes formal data or records a human approval.
"""
import argparse
import collections
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import urllib.request

import global_batch as gb

ROOT = gb.ROOT
BASE = ROOT / 'research/evidence/markets'
OUT = BASE / 'generated'
REGIONS = ['中国大陆', '日本', '韩国', '美国', '英国', '欧洲大陆']
WEIGHTS = {'passengerService':10000, 'physicalReplacementLead':2000,
           'sameIataLead':1000, 'importantAirport':500, 'priorityMarket':200,
           'officialEvidenceLead':100, 'unresolvedBoundary':50, 'flightGeolocationValue':25}


def read(path):
    return json.loads(path.read_text())


def rank(cases, queue, limit=None, maximum_country_share=.35):
    """Evidence availability never removes a lead. Balance countries within each queue."""
    if not 0 < maximum_country_share <= 1:
        raise ValueError('Invalid country share')
    rows = [{**c, 'priorityScore':sum(WEIGHTS[k] for k,v in c['priority'].items() if v)}
            for c in cases if c['queue']==queue]
    remaining = sorted(rows,key=lambda c:(-c['priorityScore'],c['caseKey']))
    target = min(limit if limit is not None else len(rows), len(rows))
    cap = max(1, math.ceil(target*maximum_country_share))
    chosen, counts = [], collections.Counter()
    while remaining and len(chosen)<target:
        eligible = [c for c in remaining if counts[c['country']] < cap]
        if not eligible:
            break  # Do not fill a balanced queue with one country's easy publications.
        # Interleave countries; retain the event score within the current country round.
        c = min(eligible,key=lambda c:(counts[c['country']],-c['priorityScore'],c['caseKey']))
        chosen.append(c); counts[c['country']]+=1; remaining.remove(c)
    return {'queue':queue,'maximumCountryShare':maximum_country_share,
            'selectionPolicy':WEIGHTS,'selected':chosen,'deferred':remaining}


def verify():
    a, lock = read(BASE/'assessments.json'), read(BASE/'source-lock.json')
    if a['decision']!='pending' or a['reviewer'] is not None:
        raise ValueError('No human approval may be synthesized')
    if gb.sha((ROOT/'test/curated-0.8.0.json').read_bytes()) != a['formalBaselineSha256']:
        raise ValueError('Formal baseline changed')
    sources = {}
    spans = {}
    for s in lock['sources']:
        sid=s['sourceId']
        if sid in sources:raise ValueError('Duplicate source')
        p=(BASE/s['excerptPath']).resolve()
        if not p.is_relative_to(BASE.resolve()):raise ValueError('Excerpt path escapes snapshot')
        if gb.sha(p.read_bytes())!=s['excerptSha256']:raise ValueError('Changed retained evidence')
        e=read(p)
        if e['originalSha256']!=s['originalSha256'] or e['originalTextSha256']!=s['textOriginalSha256']:
            raise ValueError('Original hash provenance changed')
        if s['rights']['mode']!='metadata_and_short_excerpts':raise ValueError('Full redistribution needs an explicit licence')
        for span in e['spans']:
            fid=span['factId']
            if fid in spans:raise ValueError('Duplicate fact span')
            if span['normalizedCharacterEnd']-span['normalizedCharacterStart']!=len(span['quote']):raise ValueError('Bad original locator')
            spans[fid]=(sid,span)
        sources[sid]=s
    facts={}
    for f in a['facts']:
        if f['factId'] in facts:raise ValueError('Duplicate fact')
        if f['decision']!='pending' or f['reviewer'] is not None:raise ValueError('Fact approval invented')
        sid,span=spans[f['factId']]
        if sid!=f['sourceId'] or span['quote']!=f['quote'] or any(span[k]!=v for k,v in f['citation'].items()):
            raise ValueError('Fact does not match retained original span')
        if f['observedOn'] and f['observedOn']>a['cutoff']:raise ValueError('Future observation')
        facts[f['factId']]=f
    if len({c['caseKey'] for c in a['cases']})!=len(a['cases']):raise ValueError('Duplicate case')
    for c in a['cases']:
        if c['decision']!='pending' or c['reviewer'] is not None:raise ValueError('Case approval invented')
        if any(fid not in facts for fid in c['factIds']):raise ValueError('Missing case fact')
    return a,sources,facts


def fetch(only=None, recover=False):
    """Raw copies stay in ignored work/. Recovery verifies full originals when available."""
    _,existing,_=verify()
    catalog=read(BASE/'catalog.json')['sources']
    cache=ROOT/'work/market-originals';cache.mkdir(parents=True,exist_ok=True)
    report=[]
    for s in catalog:
        if only and s['sourceId'] not in only:continue
        if not recover and s['sourceId'] in existing:continue
        row={'sourceId':s['sourceId'],'url':s['url']}
        try:
            with urllib.request.urlopen(urllib.request.Request(s['url'],headers={'User-Agent':'Keepraw-Airport-History/1.0 (historical source verification)'}),timeout=30) as r:
                raw=r.read(32*1024*1024+1)
            if len(raw)>32*1024*1024:raise ValueError('Source exceeds bounded size')
            digest=gb.sha(raw)
            expected=existing.get(s['sourceId'])
            if expected and digest!=expected['originalSha256']:
                raise ValueError('Dynamic original changed; preserved evidence must not be overwritten')
            text=gb.extract(raw,s.get('encoding','utf-8'))
            if any(q not in ' '.join(text.split()) for q in s['expectedQuotes']):raise ValueError('Original fingerprint absent')
            (cache/s['sourceId']).write_bytes(raw)
            row.update(status='original_hash_verified',originalSha256=digest)
        except (OSError,ValueError,subprocess.CalledProcessError) as error:
            row.update(status='blocked',error=str(error))
        report.append(row)
    gb.write(cache/'recovery-report.json',report)
    return report


def propose(a,sources,facts):
    baseline=read(ROOT/'test/curated-0.8.0.json')
    proposed=read(gb.OUT/'proposed-data.json')
    source_ids={s['sourceId'] for s in proposed['sources']}
    for sid,s in sources.items():
        if sid not in source_ids:
            proposed['sources'].append({'sourceId':sid,'title':s['title'],'url':s['url'],'accessedOn':s['accessedAt'][:10],
                'verificationStatus':'pending','sourceType':'primary',
                'license':{'id':'LicenseRef-Quotation-Only','url':s['url'],'note':s['rights']['note']},
                'note':'Original SHA-256 '+s['originalSha256']+'. Only claim-specific retained excerpts are public.'})
    dossier=[]
    all_ids={r['airportId'] for r in proposed['airports']}
    for site in a['sites']:
        sid=site['proposedAirportId']
        if sid in all_ids:raise ValueError('Duplicate physical identity')
        if any(r['externalIds'].get('ourAirports')==site['ourAirports'] for r in proposed['airports']):
            raise ValueError('Reuse an existing permanent physical identity explicitly')
        fids=site['factIds'];sids=sorted({facts[f]['sourceId'] for f in fids})
        proposed['airports'].append({'airportId':sid,'name':{'value':site['name'],'status':'reference','sourceIds':sids,'note':'Display label, not an official-name timeline.'},
            'coordinates':{'value':site['coordinates'],'status':'reference','sourceIds':['global-ourairports-reference'],'note':site['identityAssessmentZh']},
            'timezone':{'value':None,'status':'unknown','sourceIds':[],'note':'No historical timezone claim.'},'externalIds':{'ourAirports':site['ourAirports']}})
        dossier.append({'recordId':sid,'recordType':'physicalAirport','siteKey':site['siteKey'],'decision':'pending','reviewer':None,
            'factIds':fids,'identityAssessment':site['identityAssessmentZh'],'approvalBlockers':['Primary ARP/footprint and independent human identity review still needed; reference coordinates are not approved.']})
    sites={s['siteKey']:s for s in a['sites']}
    bindings=collections.defaultdict(list)
    for f in facts.values():
        for b in f['codeBindings']:
            if b['siteKey'] in sites:bindings[(b['siteKey'],b['scheme'],b['code'])].append(f['factId'])
    for (sk,scheme,code),fids in sorted(bindings.items()):
        aid='markets-proposal-'+sk+'-'+scheme.lower()+'-'+code.lower()
        # A reporting appendix and prospective carrier notice do not prove continuity.
        record={'assignmentId':aid,'airportId':sites[sk]['proposedAirportId'],'scheme':scheme,'code':code,
            'validFrom':{'earliest':None,'latest':None,'precision':'unknown'},'validTo':{'earliest':None,'latest':None,'precision':'unknown'},
            'sourceIds':sorted({facts[f]['sourceId'] for f in fids}),'verificationStatus':'pending','verifiedOn':None,
            'evidenceType':'indirect','note':'Association only. Reporting-guide year and prospective transfer notice are not allocation/withdrawal dates. No whole local date is resolved.'}
        proposed['assignments'].append(record)
        dossier.append({'recordId':aid,'recordType':'assignment','siteKey':sk,'decision':'pending','reviewer':None,'factIds':fids,
            'boundaryAssessment':record['note'],'continuityAssessment':'No interpolation or extrapolation is claimed.',
            'approvalBlockers':['Exact code allocation/withdrawal unknown; this association-only record adds no resolved days.']})
    # Enrich the earlier pending Murcia records. Their permanent IDs are reused.
    # The 2019 original names both namespaces and both sites, the current index
    # observes them again. These are deliberately bounded continuity inferences.
    for assignment in proposed['assignments']:
        if assignment['assignmentId'].startswith('global-proposal-murcia-'):
            assignment['validFrom']={'earliest':None,'latest':'2019-08-02','precision':'unknown'}
            assignment['validTo']={'earliest':'2026-10-29','latest':None,'precision':'unknown'}
            assignment['sourceIds']=sorted(set(assignment['sourceIds']+['es-murcia-parliament','es-murcia-index-current']))
            assignment['evidenceType']='continuity_inference'
            assignment['note']='Pending bounded same-site continuity between the 2019-08-01 parliamentary code/site statement and 2026-10-29 ENAIRE AD1.3 observation. Certain window [2019-08-02,2026-10-29). First allocation and final withdrawal remain unknown. MJV and RMU are distinct codes; civil service transfer did not withdraw MJV.'
            oldsite='murcia-old' if assignment['code'] in ['MJV','LELC'] else 'murcia-new'
            dossier.append({'recordId':assignment['assignmentId'],'recordType':'assignment','siteKey':oldsite,'decision':'pending','reviewer':None,
                'factIds':['murcia-index-iata' if oldsite=='murcia-old' else 'murcia-index-new'],'revisesPendingOnly':True,
                'boundaryAssessment':assignment['note'],'continuityAssessment':'Requires explicit human acceptance of bounded continuity; editions/issuer relationships remain visible.',
                'approvalBlockers':['Human review of code/site meaning and interpolation is outstanding.']})
    for collection,key in [('airports','airportId'),('assignments','assignmentId'),('names','nameId'),('sources','sourceId')]:
        now={r[key]:r for r in proposed[collection]}
        if any(now.get(r[key])!=r for r in baseline[collection]):raise ValueError('Published record changed')
    return proposed,dossier


def build(output=OUT):
    a,sources,facts=verify()
    output.mkdir(parents=True,exist_ok=True)
    # China is explicitly the user's leading relocation market. Its genuine
    # replacement leads may occupy more of A; B remains broadly balanced.
    queues=[rank(a['cases'],'A',maximum_country_share=.65),rank(a['cases'],'B')]
    proposed,dossier=propose(a,sources,facts)
    gb.write(output/'queues.json',queues)
    gb.write(output/'proposed-data.json',proposed)
    gb.write(output/'dossier.json',dossier)
    gb.write(output/'facts.json',a['facts'])
    batches=review_packets(a,sources,facts,dossier)
    gb.write(output/'review-packets.json',batches)
    gb.validate_batch_series(batches)
    try:
        gb.validate_admission(read(ROOT/'test/curated-0.8.0.json'),proposed,batches,dossier)
    except ValueError as error:
        if 'explicit claim review' not in str(error):raise
    else:raise ValueError('Pending market research passed admission')
    subprocess.run(['node','scripts/evidence/global_coverage.ts',str(output)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    coverage=read(output/'query-coverage.json')
    previous=read(gb.OUT/'query-coverage.json')
    old_counts=collections.Counter({scheme:sum(r['potentialNewResolvedQueries'] for k,r in previous['byCode'].items() if k.startswith(scheme+':')) for scheme in ['IATA','ICAO']})
    counts={scheme:sum(r['potentialNewResolvedQueries'] for k,r in coverage['byCode'].items() if k.startswith(scheme+':')) for scheme in ['IATA','ICAO']}
    new_rows=[d for d in dossier if not d.get('revisesPendingOnly')]
    regions=[]
    for region in REGIONS:
        cases=[c for c in a['cases'] if c['region']==region]
        sids={facts[f]['sourceId'] for c in cases for f in c['factIds']}
        sks={sk for c in cases for sk in c['siteKeys']}
        rows=[d for d in new_rows if d['siteKey'] in sks]
        if region=='欧洲大陆':rows += [d for d in dossier if d.get('revisesPendingOnly')]
        regions.append({'region':region,'selectedCases':len(cases),'scopedInvestigations':sum(bool(c['factIds']) for c in cases),
            'originalPublications':len({sources[s]['originalPublicationKey'] for s in sids}),
            'executedPhysicalChanges':sum(c['executedChange'] for c in cases),
            'newPhysicalChangesBeyondFormal':sum(c['executedChange'] and not c['alreadyFormal'] for c in cases),
            'pendingRecordReviews':len(rows),'blockedRecordReviews':sum(bool(d['approvalBlockers']) for d in rows),
            'casesNeedingFurtherEvidence':sum(bool(c['gapsZh']) for c in cases)})
    murcia={code:next(r for r in coverage['byAssignment'] if r['code']==code) for code in ['MJV','RMU','LELC','LEMI']}
    complete_iata=all(murcia[c]['newlyResolvedDays']>0 for c in ['MJV','RMU']) and murcia['MJV']['airportId']!=murcia['RMU']['airportId']
    complete_icao=all(murcia[c]['newlyResolvedDays']>0 for c in ['LELC','LEMI']) and murcia['LELC']['airportId']!=murcia['LEMI']['airportId']
    prior_keys={c['caseKey'] for c in read(gb.BASE/'assessments.json')['cases']}
    new_events=[c['caseKey'] for c in a['cases'] if c['executedChange'] and not c['alreadyFormal'] and c['caseKey'] not in prior_keys]
    chain={'completeSameIataCrossSiteChains':0,'completeDifferentIataReplacementChains':int(complete_iata),
        'bothSideIataVerifiedUnderReviewHypothesis':int(complete_iata),'bothSideIcaoVerifiedUnderReviewHypothesis':int(complete_icao),
        'newlyInvestigatedExecutedPhysicalEventsBeyondPriorAndFormal':new_events,
        'completeReplacementChainCaseKeys':['murcia'],'twoSidedPhysicalIdentityCases':[c['caseKey'] for c in a['cases'] if len(c['siteKeys'])==2]+['murcia'],
        'newSiteIataOnlyCases':['ankang','yanan','lianyungang','yibin','jinzhou'],
        'bothSideIataAssociationsWithoutResolvedWindows':['dazhou'],
        'oldSiteOnlyChains':[],'relocationWithoutIataEvidence':['luzhou','zhanjiang','narvik'],
        'conflicts':['The 2023 Guangdong guide contains both DAX/Heshi and DZH/Jinya as 2022 reporting references; it does not establish simultaneous active airport allocations.'],
        'preciseAllocationAndWithdrawalDatesEstablished':0}
    gb.write(output/'chains.json',chain)
    metrics={'regions':regions,'selectedCases':len(a['cases']),'scopedInvestigations':sum(bool(c['factIds']) for c in a['cases']),
        'newFacts':len(facts),'citedOriginalPublications':len({s['originalPublicationKey'] for s in sources.values()}),
        'newlyRetrievedCitedOriginalPublications':len({s['originalPublicationKey'] for s in sources.values() if not s.get('reusedFrom')}),
        'newPhysicalRecords':sum(d['recordType']=='physicalAirport' for d in new_rows),
        'newCodeAssociations':sum(d['recordType']=='assignment' for d in new_rows),'enrichedPendingAssignments':sum(bool(d.get('revisesPendingOnly')) for d in dossier),
        'incrementalPotentialResolvedQueries':{scheme:counts[scheme]-old_counts[scheme] for scheme in counts},
        'combinedPotentialResolvedQueries':counts,'formalNewResolvedQueries':0,'changedPublishedResolvedQueries':coverage['changedPublishedResolvedQueries'],
        'humanApproved':0,'formalAdmissions':0,'formalVersion':'0.8.0','formalCounts':[27,43,3,77],
        'completeSameIataCrossSiteChains':0,'completeDifferentIataReplacementChains':int(complete_iata),
        'scope':'Scoped official-publication examinations, not 60 new changes or an exhaustive 2015-2026 no-change proof.'}
    gb.write(output/'metrics.json',metrics)
    rows=[]
    for c in a['cases']:
        namespaces=sorted({b['scheme'] for fid in c['factIds'] for b in facts[fid]['codeBindings']}) or ['not_established']
        for year in c['checkedYears'] or ['unknown']:
            for ns in namespaces:rows.append({'country':c['country'],'caseKey':c['caseKey'],'checkedYear':year,'namespace':ns,'decision':'pending','reviewer':None,'eventDate':c['eventDate']})
    gb.write(output/'country-year-namespace.json',{'unit':'One case / explicitly inspected year / adjudicated code namespace. Inspection year is not an event year.','rows':rows})
    documents(output,a,sources,facts,metrics,dossier,chain)
    inputs=[BASE/'assessments.json',BASE/'source-lock.json',BASE/'catalog.json',ROOT/'test/curated-0.8.0.json',gb.OUT/'proposed-data.json',gb.OUT/'query-coverage.json',ROOT/'scripts/evidence/market_batch.py',ROOT/'scripts/evidence/global_coverage.ts']
    inputs+=sorted((BASE/'excerpts').glob('*.json'))
    gb.write(output/'manifest.json',{'inputs':{str(p.relative_to(ROOT)):gb.sha(p.read_bytes()) for p in inputs},
        'outputs':{str(p.relative_to(output)):gb.sha(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='manifest.json'}})


def review_packets(a,sources,facts,dossier):
    """Unique explicit manual leads; the earlier Murcia candidate keeps its owner."""
    cases=[c for c in a['cases'] if c['caseKey']!='murcia']
    batches=[]
    for offset in range(0,len(cases),20):
        chunk=cases[offset:offset+20];events=[]
        sids=sorted({facts[f]['sourceId'] for c in chunk for f in c['factIds']})
        for c in chunk:
            cs=sorted({facts[f]['sourceId'] for f in c['factIds']})
            ids=[d['recordId'] for d in dossier if d['siteKey'] in c['siteKeys']]
            events.append({'eventGroupId':'market-case-'+c['caseKey'],'label':c['labelZh'],'reviewedOn':a['cutoff'],
                'status':'pending_review','candidateIds':['legacy-markets-'+c['caseKey']],'relatedCandidateIds':[],
                'candidateOrigin':'Explicit user-prioritized manual investigation, not a directory transition.',
                'sourceIds':cs,'claims':{key:{'conclusion':c['findingsZh'] if key in ['physicalIdentity','closureAndReplacement'] else
                    'Only the explicit typed code bindings and per-record boundary judgments are proposed. No official-name timeline or uninspected period is established.',
                    'evidenceType':'indirect','sourceIds':cs} for key in ['physicalIdentity','iata','icao','historicalBoundary','historicalNames','closureAndReplacement']},
                'continuityInference':{'evidenceType':'continuity_inference','usedForAdmission':False,'note':'A guide year does not establish continuity.'},
                'evidenceGaps':['Explicit human review missing.',*c['gapsZh']],
                'conflicts':['Agent judgment is not independent human approval.'],
                'nextAction':'Obtain the listed claim-specific missing originals and review each pending record.',
                'exclusionReason':None,'admittedAirportIds':[],'admittedAssignmentIds':[],'admittedNameIds':[],
                'proposedRecordIds':ids,'decision':'pending','reviewer':None})
        batches.append({'formatVersion':1,'batchId':'market-evidence-proposal-'+str(len(batches)+1),'reviewedOn':a['cutoff'],
            'baseCommit':None,'baseCommitFingerprint':'0ca52e94ce6eca4f0af5ca4ac85fe7ff05902414ae75f70bfe20f93b10bd4bcd','preparationOnly':True,
            'selection':{'maximumEvents':20,'eventCount':len(chunk),'policy':'Balanced explicit priority-market leads; manual origins disclosed.'},
            'statusCounts':{'pending_review':len(chunk),'ready_to_admit':0,'excluded':0,'insufficient_evidence':0},
            'admission':{'airports':0,'assignments':0,'names':0,'formalSources':0},
            'sources':[{'sourceId':sid,'url':sources[sid]['url'],'sourceType':'primary','accessedOn':a['cutoff'],
                'supportedFacts':['Only cited scoped findings.'],'limitations':['Not a complete allocation ledger. Full redistribution permission not established.'],
                'accessResult':'Original hash provenance and exact minimal spans recorded.',
                'license':{'id':'LicenseRef-Quotation-Only','note':sources[sid]['rights']['note']}} for sid in sids],
            'events':events,'nextBatch':[]})
    return batches


def documents(output,a,sources,facts,m,dossier,chain):
    lines=['# PR #15 重点市场纠偏与集中待审核清单','',
        '全部事实、机场与代码提案均为 pending，reviewer 为 null。PR 保持 Open、未合并；未启用 Auto-merge。正式库 0.8.0 的 27 机场／43 分配／3 名称／77 来源不变。','',
        '## 1. 重点地区研究完成度','',
        '下表的调查单位是明确列出资料范围的机场／事件组；不是新增事件数。连续性检查只针对列出的原件和年份，不证明整个 2015–2026 年绝无变化。权威原件按出版物去重，同一 AIP 多页只算一份；各地区列不可直接相加当全球去重数。','',
        '| 地区 | 实际核查机场／事件 | 权威原件 | 已核实物理变化（含已有正式记录） | 待审核记录 | 阻塞记录 |',
        '|---|---:|---:|---:|---:|---:|']
    for r in m['regions']:lines.append('| '+' | '.join(str(r[k]) for k in ['region','scopedInvestigations','originalPublications','executedPhysicalChanges','pendingRecordReviews','blockedRecordReviews'])+' |')
    lines += ['',f"新增原始资料实际引用 {m['newlyRetrievedCitedOriginalPublications']} 份；含复用资料共 {m['citedOriginalPublications']} 份。事实判断 {m['newFacts']} 项；两个队列共 {m['selectedCases']} 组。本轮没有新增印度调查或印度来源。",'',
        '## 2. 真正的迁址成果','',
        f"新增可审核双侧中国物理身份提案 {m['newPhysicalRecords']} 条，另复用 Murcia 两个既有待审核永久 ID。中国的外部目录曾把旧、新坐标压在同一编号下，本轮显式拆分，并保留坐标 reference 的批准阻塞。",'',
        '**同一 IATA 跨场址完整链仍为 0。** Murcia 完成的是 MJV→RMU 不同代码的替代关系：两侧 IATA/ICAO 均有 2019 原始陈述和 2026 ENAIRE 观察，实际解析器可在有限窗口识别两场。该成果不能冒充“同一代码沿用”。精确首配／撤销日期仍未建立。', '',
        f"本轮首次实查、此前调查和正式库均未计入的实际物理变化为 {len(chain['newlyInvestigatedExecutedPhysicalEventsBeyondPriorAndFormal'])} 组："+', '.join(chain['newlyInvestigatedExecutedPhysicalEventsBeyondPriorAndFormal'])+'。已形成双侧物理身份提案 8 组（7 组中国迁场 + Murcia）；两侧 IATA 可解析关系 1 组，两侧 ICAO 可解析关系 1 组，均只在待批准假设下成立。没有任何已获用户批准的完整新链。','',
        '新场 IATA 证据的半链：安康、延安、连云港、宜宾、锦州。达州已补双侧 DAX/DZH 与执行材料，但没有足够整日连续窗口。泸州、湛江、Narvik 的代码证据仍阻塞。安康 2018 公报明确停航，不能默认旧场在迁建前一直有定期航班。', '',
        'Williston 新增 FAA JO 7350.9U（2020-05-21）机场专属 XWA 行、ISN RCO 行及本土机场加 K 的国际位置代码规则；另有 2020-02-26 FAA 原件确认新场已开放。这些资料补强 KXWA／物理场址关系，但没有证明 IATA，旧 KXWA 提案仍未批准。','',
        '## 3. 真实解析器覆盖','',
        f"相对上一轮提案，新增潜在 IATA resolved 查询 {m['incrementalPotentialResolvedQueries']['IATA']}，ICAO {m['incrementalPotentialResolvedQueries']['ICAO']}。计数单位是 namespace/code/完整本地日期；不是独立历史事实。正式新增查询 0；改变已发布 resolved 查询 {m['changedPublishedResolvedQueries']}。",'',
        'Murcia 的拟议确定窗口为 [2019-08-02, 2026-10-29)，未知首配、撤销边界仍开放。2019-08-01 及之前、2026-10-29 及之后保持 uncertain。MJV 仍属于旧 San Javier，不把客运转移推成撤码。中国新关联不提供确定整日。KSGU、KDXZ、KXWA 的旧阻塞保持。', '',
        '## 4. 工程与证据边界','',
        '构建和验证命令：`pnpm evidence:markets build`、`pnpm evidence:markets validate`、`pnpm check`。生成内容可完全离线重建；原件 SHA-256 与精确引用页／字符偏移在 source-lock 和 excerpts。受保护全文未公开再分发，离线检查验证保留引用的字节，不宣称能从短引用重构整份原件。原始字节可单独恢复并核哈希，动态站点变化或失效需重新取得，不得改写旧哈希。', '',
        '## 5. 逐机场调查与待审核记录','']
    for i,c in enumerate(a['cases'],1):
        lines += [f"### {i}. {c['labelZh']}（{c['country']}，队列 {c['queue']}）",'',
            '核查年份／范围：'+', '.join(map(str,c['checkedYears']))+'；'+c['findingsZh'],'',
            '证据：','']
        for fid in c['factIds']:
            f=facts[fid];s=sources[f['sourceId']];span=f['citation'];where=('PDF 物理页 '+str(span['page'])) if span['page'] else '规范化 HTML'
            lines.append(f"- `{fid}`：[{s['title']}]({s['url']})；{where} 字符 {span['normalizedCharacterStart']}–{span['normalizedCharacterEnd']}；原件 SHA-256 `{s['originalSha256']}`。")
        lines += ['', '仍需补证：'+'；'.join(c['gapsZh']),'']
        for d in dossier:
            if d['siteKey'] in c['siteKeys'] or (c['caseKey']=='murcia' and d.get('revisesPendingOnly')):
                lines.append(f"- 待审核 `{d['recordId']}`：{d['recordType']}；pending；reviewer=null；"+'；'.join(d['approvalBlockers']))
        lines.append('')
    (output/'待审核清单.zh-CN.md').write_text('\n'.join(lines).rstrip()+'\n')
    (output/'RESULTS.zh-CN.md').write_text('\n'.join(lines[:lines.index('## 5. 逐机场调查与待审核记录')]).rstrip()+'\n\n完整逐条内容见 [集中待审核清单](待审核清单.zh-CN.md)。\n')


def validate(output=OUT):
    verify()
    manifest=read(output/'manifest.json')
    for name,h in manifest['inputs'].items():
        if gb.sha((ROOT/name).read_bytes())!=h:raise ValueError('Changed research input: '+name)
    for name,h in manifest['outputs'].items():
        if gb.sha((output/name).read_bytes())!=h:raise ValueError('Changed generated output: '+name)
    m=read(output/'metrics.json')
    if m['humanApproved'] or m['formalAdmissions'] or m['changedPublishedResolvedQueries']:raise ValueError('Approval or formal result changed')
    print('Priority-market excerpts, pending proposals and deterministic output hashes verified')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['build','verify','validate','fetch'])
    p.add_argument('--output',type=Path,default=OUT)
    p.add_argument('--source',action='append')
    p.add_argument('--recover',action='store_true')
    args=p.parse_args()
    if args.command=='build':build(args.output)
    elif args.command=='validate':validate(args.output)
    elif args.command=='verify':verify();print('Retained excerpts and original hash provenance verified')
    else:print(json.dumps(fetch(args.source,args.recover),ensure_ascii=False,indent=2))
