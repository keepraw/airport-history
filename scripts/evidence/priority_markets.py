"""Incremental priority-market research and isolated, unauthorized policy dry-runs.

This module has no authorization, admission, or production-data write operation.
Offline citation verification is deliberately distinct from original-byte checks.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import global_batch as gb

ROOT = gb.ROOT
BASE = ROOT / 'research/evidence/priority-markets'
OUT = BASE / 'generated'
CACHE = ROOT / 'work/priority-markets'
ADAPTERS = {
    'cn-site-code-association': 'cn_association_v1',
    'jp-operator-code-site': 'jp_operator_v1',
    'kr-molit-bounded-icao': 'kr_airac_v1',
    'us-faa-typed-identifier': 'us_faa_v1',
    'uk-nats-bounded-icao': 'uk_nats_v1',
    'es-enaire-bounded-icao': 'es_enaire_v1',
    'de-operator-event': 'de_operator_v1',
}


def load(path):
    return json.loads(path.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def executor_fingerprint():
    paths = ['scripts/evidence/priority_markets.py', 'scripts/evidence/priority_market_coverage.ts']
    files = {p: digest((ROOT / p).read_bytes()) for p in paths}
    return files, digest(encoded(files))


def representations(raw):
    extracted = gb.extract(raw)
    return extracted, {'normalized_text': ' '.join(extracted.split()),
                       'decoded_html': None if raw.startswith(b'%PDF-') else raw.decode('utf-8')}


def verify(*, originals=False, baseline=True):
    lock = load(BASE / 'source-lock.json')
    frozen = load(BASE / 'baseline-lock.json')
    if baseline:
        for path, expected in frozen['files'].items():
            require(digest((ROOT / path).read_bytes()) == expected, 'Protected baseline changed: ' + path)
        require(load(ROOT / 'package.json')['version'] == frozen['dataVersion'], 'Unrequested version bump')
        data = load(ROOT / 'data/airports.json')
        require(data['dataVersion'] == frozen['dataVersion'] and data['schemaVersion'] == frozen['schemaVersion'],
                'Published version changed')
    sources, citations = {}, {}
    for row in lock['sources']:
        sid = row['sourceId']
        require(sid not in sources, 'Duplicate source ID')
        path = (BASE / row['excerptPath']).resolve()
        require(path.is_relative_to((BASE / 'excerpts').resolve()), 'Unsafe excerpt path')
        raw_excerpt = path.read_bytes()
        require(digest(raw_excerpt) == row['excerptSha256'], 'Changed retained citation: ' + sid)
        excerpt = json.loads(raw_excerpt)
        for key in ['sourceId', 'originalSha256', 'extractedTextSha256', 'normalizedTextSha256']:
            require(excerpt[key] == row[key], 'Detached citation provenance: ' + sid)
        require(row['rights']['mode'] == 'metadata_and_short_excerpts' and
                row['rights']['fullRedistribution'] == 'not_established', 'Unreviewed rights mode')
        require(sum(len(s['quote']) for s in excerpt['spans']) <= 1800, 'Excessive source quotation')
        for span in excerpt['spans']:
            require(span['citationId'] not in citations, 'Duplicate citation')
            require(0 < len(span['quote']) <= 600 and span['characterStart'] >= 0 and
                    span['characterEnd'] - span['characterStart'] == len(span['quote']), 'Bad citation locator')
            require(span['representation'] in ['normalized_text', 'decoded_html'], 'Unknown representation')
            citations[span['citationId']] = span
        if originals:
            original = (CACHE / (sid + '.raw')).read_bytes()
            require(digest(original) == row['originalSha256'], 'Changed original bytes: ' + sid)
            extracted, texts = representations(original)
            require(digest(extracted.encode()) == row['extractedTextSha256'], 'Changed extraction: ' + sid)
            require(digest(texts['normalized_text'].encode()) == row['normalizedTextSha256'], 'Changed normalization')
            for span in excerpt['spans']:
                text = texts[span['representation']]
                require(text is not None and text[span['characterStart']:span['characterEnd']] == span['quote'],
                        'Citation not in original: ' + sid)
                if span['page'] is not None:
                    pages = extracted.split('\f')
                    require(0 < span['page'] <= len(pages) and span['quote'] in ' '.join(pages[span['page']-1].split()),
                            'Incorrect physical PDF page')
        sources[sid] = {**row, 'spans': excerpt['spans']}
    catalog = load(BASE / 'catalog.json')['sources']
    require({s['sourceId'] for s in catalog} == set(sources), 'Catalog/lock mismatch')
    for s in catalog:
        require(all(s[k] == sources[s['sourceId']][k] for k in s), 'Catalog provenance mismatch')
    if not originals:
        receipt = load(BASE / 'original-verification.json')
        require(receipt['mode'] == 'local_original_verification' and receipt['originalBytesRecheckedHere'] is True,
                'Missing separately labelled local verification receipt')
        require(receipt['sources'] == [{k: row[k] for k in ['sourceId','originalSha256','extractedTextSha256',
                                                          'normalizedTextSha256','excerptSha256']}
                                       for row in sources.values()], 'Original receipt is detached from source lock')
    assessments = load(BASE / 'assessments.json')
    require(assessments['decision'] == 'pending' and assessments['reviewer'] is None, 'Invented human review')
    old = load(ROOT / 'research/evidence/markets/assessments.json')
    prior_cases = {c['caseKey'] for c in old['cases']}
    prior_facts = {f['factId'] for f in old['facts']}
    cases = {c['caseKey']: c for c in assessments['cases']}
    require(len(cases) == len(assessments['cases']) and set(cases) <= prior_cases, 'Not an incremental case set')
    for c in cases.values():
        require(c['decision'] == 'pending' and c['reviewer'] is None and c['formalIdentityAction'] == 'none',
                'Research must not admit identities or synthesize review')
        require(set(c['newSourceIds']) <= set(sources) and set(c['priorFactIds']) <= prior_facts, 'Missing case evidence')
        for code in c['codes']:
            namespace, value = code.split(':')
            require(namespace in ['IATA', 'ICAO', 'FAA'] and bool(re.fullmatch('[A-Z0-9]{3,4}', value)), 'Untyped code')
    definitions = load(BASE / 'draft-policies.json')
    require(definitions['status'] == 'draft' and not definitions['productionAuthorizationInherited'] and
            not definitions['authorizationRequestIssued'], 'New-market authorization invented')
    policies = {p['policyId']: p for p in definitions['definitions']}
    require(set(policies) == set(ADAPTERS), 'Unbound research adapter')
    for pid, p in policies.items():
        require(p['status'] == 'draft' and p['authorization'] is None and not p['executor']['productionBound'],
                'Research policy must remain unauthorized')
        require(p['executor']['path'] == 'scripts/evidence/priority_markets.py' and
                p['executor']['adapter'] == ADAPTERS[pid] and
                p['executor']['sha256'] == executor_fingerprint()[1], 'Wrong or stale draft executor binding')
        require(set(p['scope']['caseKeys']) <= set(cases) and
                not p['scope']['newIataAdmission'] and not p['scope']['newPhysicalIdentityAdmission'] and
                not p['scope']['publishedCorrections'], 'Unexpected draft scope')
    return sources, cases, policies


def text(source):
    return ' '.join(s['quote'] for s in source['spans'])


def evaluate(sample, sources, policies):
    """Separate market adapters. All outputs are research-only, including positives."""
    pid = sample['policyId']
    p = policies[pid]
    rows = [sources[sid] for sid in sample['sourceIds']]
    reasons = []
    status = 'hold'
    result = {'sampleId': sample['sampleId'], 'policyId': pid, 'adapter': p['executor']['adapter'],
              'caseKey': sample['caseKey'], 'sourceIds': sample['sourceIds'],
              'authorization': None, 'productionEligible': False, 'reviewer': None}
    require(sample['caseKey'] in p['scope']['caseKeys'], 'Sample outside draft case scope')
    scope = p['scope']
    if (not set(sample['sourceIds']) <= set(scope['sourcesByCase'][sample['caseKey']]) or
            (sample.get('code') and sample.get('namespace', '') + ':' + sample['code'] not in scope['codesByCase'][sample['caseKey']])):
        reasons.append('source_or_code_outside_draft_case_scope')
    if any(urlsplit(s['url']).hostname not in scope['allowedOriginalHosts'] or
           s['sourceFamily'] not in scope['allowedPublisherFamilies'] for s in rows):
        reasons.append('publisher_or_original_host_outside_market_scope')
    if any(s['role'] not in p['scope']['sourceRoles'] for s in rows):
        reasons.append('source_role_outside_market_adapter')
    if any(s.get('documentEffectiveAt', '') and s['documentEffectiveAt'][:10] > '2026-10-30' for s in rows):
        reasons.append('future_effective_publication')
    body = ' '.join(text(s) for s in rows)
    request = sample['request']
    code = sample.get('code', '')
    if not reasons and pid == 'cn-site-code-association':
        if request == 'association' and sample.get('siteToken', '') in body and re.search(r'\b' + re.escape(code) + r'\b', body):
            status = 'association_only'
            reasons.append('no_date_validity_from_directory_or_capture')
        else:
            reasons.append('missing_named_site_or_administrative_date_original')
    elif not reasons and pid == 'jp-operator-code-site':
        if request == 'association' and sample.get('siteToken', '') in body and re.search(r'\b' + re.escape(code) + r'\b', body):
            status = 'association_only'
            reasons.append('undated_operator_profile_no_historical_interpolation')
        else:
            reasons.append('opening_or_physical_profile_is_not_code_allocation')
    elif not reasons and pid == 'kr-molit-bounded-icao':
        observations = [s for s in rows if s['role'] == 'aip_ad2']
        anchors = [s for s in rows if s['role'] == 'aip_issue_index']
        if request != 'bounded_icao' or sample.get('namespace') != 'ICAO' or len(observations) != 2 or len(anchors) != 1:
            reasons.append('requires_two_controlled_icao_observations_and_issue_index')
        elif any(s['sourceFamily'] != 'KR-MOLIT-AIP' for s in rows):
            reasons.append('wrong_publisher_family')
        elif any(not re.search(r'\b' + re.escape(code) + r' - SEOUL / ', text(s)) or
                 'ARP coordinates and site at AD ' + sample.get('arp', '') not in text(s) for s in observations):
            reasons.append('code_name_or_physical_arp_mismatch')
        elif len({s['originalSha256'] for s in observations}) != 2 or len({s['originalPublicationKey'] for s in observations}) != 2:
            reasons.append('two_components_are_not_two_editions')
        else:
            observations.sort(key=lambda s: s['documentEffectiveAt'])
            instants = [dt.datetime.fromisoformat(s['documentEffectiveAt'].replace('Z', '+00:00')) for s in observations]
            for s, instant in zip(observations, instants):
                date = instant.strftime('%d %b %Y').upper()
                pub = dt.date.fromisoformat(s['publicationDate']).strftime('%d %b %Y').upper() if s['publicationDate'] else None
                anchor = [span['quote'] for span in anchors[0]['spans'] if 'WEF 1600 UTC ' + date in span['quote']]
                if instant.hour != 16 or instant.minute or not pub or not any(pub in q for q in anchor):
                    reasons.append('publication_or_utc_effective_anchor_missing')
            gap = (instants[1] - instants[0]).total_seconds() / 86400
            if not 0 < gap <= p['proposedMaxObservationGapDays']:
                reasons.append('observation_gap_exceeds_independent_korean_draft_limit')
            if not reasons:
                zone = ZoneInfo('Asia/Seoul')
                start = instants[0].astimezone(zone).date() + dt.timedelta(days=1)
                end = instants[1].astimezone(zone).date()
                require(start < end, 'No complete local-date window')
                status = 'draft_window'
                result.update(code=code, namespace='ICAO', arp=sample['arp'], label=sample['label'],
                              simulationAirportId=sample['simulationAirportId'], observationGapDays=gap,
                              proposedWindow={'from': start.isoformat(), 'toExclusive': end.isoformat(), 'wholeLocalDates':(end-start).days},
                              timezoneCalculation='Asia/Seoul; 16:00 UTC = 01:00 next Korean date; exclude both partial edge dates',
                              independentIssuers=1, distinctEditionOriginals=2)
                reasons += ['draft_not_authorized', 'physical_identity_review_pending', 'intervening_amendment_and_notam_screening_pending']
    elif not reasons and pid == 'us-faa-typed-identifier':
        if request == 'identifier_semantics' and 'not associated with IATA codes' in body:
            status = 'typed_rule_only'
            reasons.append('national_rule_not_airport_specific_assignment')
        else:
            reasons.append('faa_identifier_is_not_iata_assignment')
    elif not reasons and pid == 'uk-nats-bounded-icao':
        if request == 'association' and all('EGCN' in text(s) and s['role'] == 'aip_ad2' for s in rows):
            status = 'association_only'
            reasons.append('airport_page_exists_after_service_stop_without_proving_service_or_withdrawal')
        else:
            reasons.append('documented_service_stop_requires_notam_and_licence_review_before_interpolation')
    elif not reasons and pid == 'es-enaire-bounded-icao':
        if request == 'association' and all(t in body for t in ['374811N 0010729W', '374630N 0004845W', 'LEMI (RMU)', 'LELC (MJV)']):
            status = 'association_only'
            reasons.append('distinct_physical_sites_current_associations_only')
        else:
            reasons.append('page_revision_plus_current_index_is_not_two_historical_edition_observations')
    elif not reasons and pid == 'de-operator-event':
        if request == 'event' and 'flight booking systems' in body and '4 May 2021' in body:
            status = 'event_only'
            reasons.append('booking_service_and_permit_events_are_not_administrative_code_withdrawal')
        else:
            reasons.append('service_stop_does_not_prove_code_withdrawal')
    result.update(status=status, reasons=reasons)
    return result


def decisions(sources, policies):
    samples = load(BASE / 'samples.json')['samples']
    require(len({s['sampleId'] for s in samples}) == len(samples), 'Duplicate dry-run sample')
    results = [evaluate(s, sources, policies) for s in samples]
    for sample, result in zip(samples, results):
        require(sample['expected'] == result['status'], 'Unexpected real-corpus decision: ' + sample['sampleId'])
    return {'mode': 'unauthorized_dry_run', 'productionEligibleRecords': 0, 'decisions': results}


def artifacts():
    sources, cases, policies = verify()
    evaluated = decisions(sources, policies)
    counts = {}
    for c in cases.values():
        counts[c['market']] = counts.get(c['market'], 0) + 1
    bindings = {}
    code_hashes, executor_hash = executor_fingerprint()
    for pid, p in policies.items():
        bindings[pid] = {'status': 'draft', 'policySha256': digest(encoded(p)), 'scopeSha256': digest(encoded(p['scope'])),
                         'adapter': p['executor']['adapter'], 'executorFiles': code_hashes,
                         'executorSha256': executor_hash, 'authorization': None,
                         'productionBound': False}
    summary = {'followedUpCases':len(cases), 'previousSurveyUnits':60, 'notReinvestigatedUnits':60-len(cases),
               'casesByMarket':counts, 'sourceComponents':len(sources),
               'distinctOriginalByteStreams':len({s['originalSha256'] for s in sources.values()}),
               'publisherFamilies':len({s['sourceFamily'] for s in sources.values()}),
               'shortCitations':sum(len(s['spans']) for s in sources.values()),
               'newFormalResolvedQueries':0, 'authorizedNewMarketPolicies':0,
               'dryRunRequests':len(evaluated['decisions']), 'dataVersion':'0.10.0', 'schemaVersion':'3.0.0',
               'offlineVerification':'Retained citations and frozen inputs only; this build did not reacquire originals.'}
    formal = load(ROOT / 'data/airports.json')
    dedup = {'basis':'actual published 0.10.0 dataset and pre-existing research IDs',
             'newPermanentPhysicalIdsAllocated':0, 'rows':[]}
    terms = {'qingdao':['Qingdao'], 'yantai':['Yantai'], 'williston':['Sloulin','Williston'],
             'murcia':['Murcia','San Javier'], 'berlin':['Berlin']}
    for key, names in terms.items():
        matched = [a for a in formal['airports'] if any(n in a['name']['value'] for n in names)]
        dedup['rows'].append({'caseKey':key, 'formalAirports':[{'airportId':a['airportId'], 'name':a['name']['value']} for a in matched],
                              'action':'preserve all IDs; no new identity and no merge'})
    dedup['pendingChinaSiteIds'] = {k:c['existingPendingSiteIds'] for k,c in cases.items() if c['market']=='中国大陆'}
    if 'murcia' in cases:
        # The formerly pending Murcia IDs were admitted in 0.9.0; never recreate them.
        require(len(next(r for r in dedup['rows'] if r['caseKey']=='murcia')['formalAirports']) == 2,
                'Murcia physical identities must be reused from latest formal baseline')
    lines = ['# 重点市场增量研究矩阵', '',
             '本轮追踪已有 60 组中的 14 组；其余 46 组未重新调查。所有判断 pending、reviewer=null。',
             '正式 0.10.0 / Schema 3.0.0 保持；来源组件数量不是历史覆盖率。完整本地日期窗口见独立 dry-run，不是批准。', '',
             '| 市场 | 案例 | 物理身份与代码证据 | 日期边界／下一步 |', '|---|---|---|---|']
    for c in cases.values():
        lines.append('| '+ ' | '.join([c['market'], c['labelZh'], '；'.join(c['directFindingsZh']), '；'.join(c['missingOriginalsZh'])])+' |')
    for c in cases.values():
        lines += ['', '## '+c['labelZh'], '', '**已直接读到的陈述**：'+'；'.join(c['directFindingsZh']), '',
                  '**推断限制**：'+'；'.join(c['inferenceZh']), '', '**未知边界**：'+'；'.join(c['unknownBoundariesZh']), '',
                  '**来源独立性**：'+c['independenceZh'], '', '**缺少原件**：'+'；'.join(c['missingOriginalsZh']), '',
                  '**既有待审物理 ID**：'+json.dumps(c['existingPendingSiteIds'],ensure_ascii=False), '',
                  '**资料及定位**：']
        for sid in c['newSourceIds']:
            s=sources[sid]
            locations=', '.join(span['citationId'] + (' (PDF p.'+str(span['page'])+')' if span['page'] else '') for span in s['spans'])
            lines.append(f'- [{s["title"]}]({s["retrievalUrl"]})：`{sid}`；{locations}。')
        lines += ['', '沿用事实：'+', '.join(c['priorFactIds'])+'。', '',
                  '未来政策：`'+c['draftPolicy']+'@0.1.0-draft`；正式新增 resolved=0。']
    return {'dry-run.json': evaluated, 'draft-bindings.json':bindings, 'summary.json':summary, 'identity-dedup.json':dedup,
            'MATRIX.zh-CN.md':'\n'.join(lines)+'\n'}


def build_or_validate(validate=False):
    OUT.mkdir(exist_ok=True)
    for name, value in artifacts().items():
        raw = value.encode() if isinstance(value, str) else encoded(value)
        path = OUT / name
        if validate:
            require(path.read_bytes() == raw, 'Stale generated artifact: ' + name)
        else:
            path.write_bytes(raw)
    subprocess.run(['node', 'scripts/evidence/priority_market_coverage.ts', 'validate' if validate else 'build'],
                   cwd=ROOT, check=True)


def fetch(only):
    """Recover cataloged originals privately and reject changed bytes; never alter a lock."""
    sources, _, _ = verify()
    require(not only or set(only) <= set(sources), 'Unknown source')
    CACHE.mkdir(parents=True, exist_ok=True)
    for sid, s in sources.items():
        if only and sid not in only:
            continue
        with urllib.request.urlopen(urllib.request.Request(s['retrievalUrl'], headers={
                'User-Agent':'Keepraw-Airport-History/1.0 (historical source verification)'}),timeout=35) as response:
            raw=response.read(32*1024*1024+1)
        require(len(raw)<=32*1024*1024 and digest(raw)==s['originalSha256'], 'Changed or oversized original: '+sid)
        (CACHE/(sid+'.raw')).write_bytes(raw)
        print('Recovered original hash:',sid)


def rights_audit():
    """Check complete ancestry and additions against old AND new original hashes."""
    import history_audit as audit
    sources, _, _ = verify()
    result = audit.verify()
    record = load(audit.AUDIT)
    blobs, commits, locators, content_hashes = audit.inventory(record)
    for source in sources.values():
        content_hashes.update(source[k] for k in ['originalSha256','extractedTextSha256','normalizedTextSha256'])
    baseline = load(BASE/'baseline-lock.json')['baseCommit']
    old_blobs = {oid for oid, _ in audit.tree(ROOT, baseline)}
    seen = set()
    for commit in audit.git(ROOT, 'rev-list', 'HEAD', '^'+baseline).decode().splitlines():
        for oid, path in audit.tree(ROOT, commit):
            if oid in old_blobs or oid in seen:
                continue
            require(not path.startswith('work/'), 'Private acquisition cache in history')
            audit.check_payload(audit.git(ROOT, 'cat-file', 'blob', oid), blobs, commits | locators, content_hashes)
            seen.add(oid)
    staged = audit.git(ROOT, 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z').decode().split('\0')
    count = 0
    for path in filter(None, staged):
        require(not path.startswith('work/'), 'Private acquisition cache staged')
        audit.check_payload(audit.git(ROOT, 'show', ':'+path), blobs, commits | locators, content_hashes)
        count += 1
    result.update(newMarketOriginalComponents=len(sources), newMarketHistoricalBlobsChecked=len(seen),
                  stagedFilesChecked=count, fullOriginalsAndExtractionsAdded=False,
                  legalScope='Mechanical content/ancestry gate plus source-specific short-quotation review; no full redistribution grant inferred.')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['verify','build','validate','fetch','rights'])
    parser.add_argument('--originals',action='store_true')
    parser.add_argument('--source',action='append')
    args=parser.parse_args()
    if args.command=='fetch':
        fetch(args.source)
    elif args.command=='rights':
        print(json.dumps(rights_audit(), ensure_ascii=False, sort_keys=True))
    elif args.command=='verify':
        s,_,_=verify(originals=args.originals)
        if args.originals:
            receipt = {'mode':'local_original_verification', 'verifiedOn':'2026-10-30',
                       'originalBytesRecheckedHere':True,
                       'sources':[{k:row[k] for k in ['sourceId','originalSha256','extractedTextSha256','normalizedTextSha256','excerptSha256']} for row in s.values()]}
            (BASE/'original-verification.json').write_bytes(encoded(receipt))
        print(f'Verified {len(s)} sources; originalBytesRecheckedHere={args.originals}')
    else:
        require(not args.originals, '--originals is a separate verify operation')
        build_or_validate(args.command=='validate')
