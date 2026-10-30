"""Bounded Korean research custody and lifecycle replay; never an admission gate."""
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from zoneinfo import ZoneInfo

import global_batch as gb

ROOT = gb.ROOT
BASE = ROOT / 'research/evidence/code-dates/korea-readiness'
UTC = dt.timezone.utc
SEOUL = ZoneInfo('Asia/Seoul')
START = dt.datetime(2025, 4, 18, tzinfo=SEOUL).astimezone(UTC)
END = dt.datetime(2025, 5, 15, tzinfo=SEOUL).astimezone(UTC)


def load(path):
    return json.loads(path.read_text())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def instant(value):
    if not value or not re.fullmatch(r'\d{10}', value):
        return None
    return dt.datetime.strptime(value, '%y%m%d%H%M').replace(tzinfo=UTC)


def clocks(value):
    t = instant(value)
    return {'raw': value, 'utc': t.isoformat() if t else None,
            'asiaSeoul': t.astimezone(SEOUL).isoformat() if t else None}


def metadata(item, source_id, index):
    body = item['FULL_TEXT']
    kind = re.search(r'NOTAM([NRC])\b', body)
    target = re.search(r'NOTAM[RC]\s+([A-Z]\d{4}/\d{2})', body)
    c = re.search(r'C\)\s*([^\r\n]*?)(?=\s+[DEFG]\)|$)', body, re.M)
    return {'notamNo': item['NOTAM_NO'], 'serverRecordId': str(item['SEQ']),
            'seriesBaseNo': re.match(r'[A-Z]\d{4}/\d{2}', item['NOTAM_NO']).group(0),
            'sourceId': source_id, 'jsonPointer': '/DATA/' + str(index),
            'location': item['LOCATION'], 'qcode': item['QCODE'],
            'issued': clocks(item['ISSUE_TIME']), 'b': clocks(item.get('EFFECTIVESTART')),
            'c': clocks(item.get('EFFECTIVEEND')),
            'estimatedEnd': bool(c and 'EST' in c.group(1)),
            'noticeType': kind.group(1) if kind else None,
            'replacesOrCancels': target.group(1) if target else None,
            'fullTextSha256': sha(body.encode()),
            'explicitAirportMentions': sorted(set(re.findall(r'\bRKSI\b|\bRKSS\b', item['ECODE']))),
            'publicationReferences': sorted(set(re.findall(
                r'(?:AIRAC\s+)?AIP\s+(?:SUP|AMDT)\s+\d{1,3}/\d{2}', item['ECODE']))),
            'aircraftReferenceCodeOnly': bool(re.search(r'ICAO CODE\s+[CD]\b', item['ECODE'])),
            'identityChangeSignal': bool(re.search(
                r'LOCATION INDICATOR|AERODROME NAME|AIRPORT NAME|ARP COORD|RELOCAT', item['ECODE']))}


def lifecycle(row, rows):
    """Conservative effect envelope, including cancellation before activation.

    C notices are graph events, not open-ended operational restrictions. An EST
    is never a hard end; a missing predecessor remains explicitly unknown.
    Notices are deduplicated by number AND complete-text fingerprint, never ID.
    """
    successors = [s for s in rows if s['replacesOrCancels'] == row['seriesBaseNo']]
    successor_ids = sorted({s['serverRecordId'] for s in successors})
    known = {s['seriesBaseNo'] for s in rows}
    missing = row['replacesOrCancels'] is not None and row['replacesOrCancels'] not in known
    ends = []
    end = instant(row['c']['raw'])
    if end and not row['estimatedEnd']:
        ends.append(end)
    for s in successors:
        # Never backdate termination before the successor was transmitted.
        b, issued = instant(s['b']['raw']), instant(s['issued']['raw'])
        if b and issued:
            ends.append(max(b, issued))
    effective_end = min(ends) if ends else None
    start = instant(row['b']['raw'])
    if row['noticeType'] == 'C':
        disposition = 'cancellation_event'
    elif row['noticeType'] not in ('N', 'R') or start is None:
        disposition = 'unknown_lifecycle'
    elif start >= END:
        disposition = 'outside_window'
    elif effective_end is None:
        disposition = 'unknown_lifecycle'
    elif effective_end <= START:
        disposition = 'outside_window'
    else:
        disposition = 'overlap'
    peers = [s['serverRecordId'] for s in rows if s['notamNo'] == row['notamNo'] and
             s['fullTextSha256'] == row['fullTextSha256']]
    subject = row['qcode'][1:3]
    if row['noticeType'] == 'C':
        impact = 'cancellation_of_notice_not_withdrawal_of_airport_code'
    elif row['identityChangeSignal']:
        impact = 'manual_identity_review_required'
    elif row['aircraftReferenceCodeOnly']:
        impact = 'aircraft_stand_reference_code_not_airport_indicator'
    elif subject == 'GA':
        impact = 'predicted_navigation_availability'
    elif subject in ('MR', 'MX', 'MP', 'MG', 'MY'):
        impact = 'movement_area_facilities_or_operating_restriction'
    elif subject in ('OB', 'OL', 'WM', 'WL', 'WU', 'WA'):
        impact = 'temporary_obstacle_or_hazard'
    elif subject in ('PI', 'PU', 'PA', 'PF'):
        impact = 'procedure_or_flow_control'
    elif subject in ('RP', 'RT', 'RA', 'RR'):
        impact = 'regional_airspace_activity_or_restriction'
    else:
        impact = 'publication_trigger_equipment_or_other_operating_information'
    return {'disposition': disposition, 'effectiveEndUtc': effective_end.isoformat() if effective_end else None,
            'windowOverlap': True if disposition == 'overlap' else None if disposition == 'unknown_lifecycle' else False,
            'cancellationEventInWindow': bool(row['noticeType'] == 'C' and instant(row['issued']['raw']) and
                                            START <= instant(row['issued']['raw']) < END),
            'successorServerRecordIds': successor_ids, 'missingPredecessor': missing,
            'duplicateServerRecordIds': sorted(set(peers)), 'impact': impact,
            'codeAllocationChangeEstablished': False,
            'reason': ('Cancellation affects its named predecessor; not an airport withdrawal.' if row['noticeType'] == 'C'
                       else 'Identity-language signal requires separate source review.' if row['identityChangeSignal']
                       else 'B/C bounds and explicit successor transmissions determine the effect envelope; '
                            'the recorded subject is distinct from an administrative code allocation.')}


def source_bytes(source):
    path = (ROOT / source['cachePath']).resolve()
    require(path.is_relative_to((ROOT / 'work').resolve()), 'Original cache outside ignored work/')
    raw = path.read_bytes()
    text = gb.extract(raw, encoding=source.get('encoding', 'utf-8'))
    for key, data in [('originalSha256', raw), ('extractedTextSha256', text.encode()),
                      ('normalizedTextSha256', ' '.join(text.split()).encode())]:
        require(sha(data) == source[key], 'Original/extraction drift: ' + source['sourceId'])
    return raw, text


def make_ledger(location, sources):
    sid = 'notam-all-' + location.lower()
    raw, _ = source_bytes(sources[sid])
    data = json.loads(raw)
    require(data['Total'] == len(data['DATA']), 'Truncated airport response')
    all_rows = [metadata(r, sid, i) for i, r in enumerate(data['DATA'])]
    old = load(ROOT / 'research/evidence/code-dates/korea-screening.json')
    original = next(g for g in old['notamGroups'] if g['location'] == location)
    old_ids = {r['serverRecordId']: r['fullTextSha256'] for r in original['records']}
    require(all(r['location'] == location for r in all_rows), 'Wrong location filter')
    require({r['serverRecordId']: r['fullTextSha256'] for r in all_rows if r['serverRecordId'] in old_ids} == old_ids,
            'PR23 notices changed or disappeared')
    selected = [r for r in all_rows if r['serverRecordId'] in old_ids]
    # Only linked later successors, not a new all-airport pending queue.
    selected_numbers = {r['notamNo'] for r in selected}
    forward = [r for r in all_rows if r['serverRecordId'] not in old_ids and
               r['replacesOrCancels'] in selected_numbers]
    for r in selected:
        r['assessment'] = lifecycle(r, all_rows)
    counts = dict(collections.Counter(r['assessment']['disposition'] for r in selected))
    unique = {(r['notamNo'], r['fullTextSha256']): r for r in selected}
    return {'location': location, 'mode': 'research_not_authorization',
            'sourceId': sid, 'serverTotal': data['Total'], 'returnedRows': len(all_rows),
            'pr23RowsReconciled': len(old_ids), 'windowUtc': [START.isoformat(), END.isoformat()],
            'countsByServerRecord': counts,
            'uniqueNotices': len(unique),
            'uniqueOverlapNotices': sum(r['assessment']['disposition'] == 'overlap' for r in unique.values()),
            'oldestReturnedIssueUtc': min(r['issued']['utc'] for r in all_rows),
            'records': selected, 'laterLinkedSuccessors': forward,
            'archiveCompleteSince2001': False,
            'limits': ['Returned archive starts in 2023; bounded coverage additionally requires official outstanding-notice snapshots.',
                       'No notice absence is inferred from a query miss. C times bound an envelope; D schedules may narrow actual activity.',
                       'Fixed C, EST, PERM, cancellation, operational closure and allocation withdrawal are distinct.']}


def bindings():
    paths = ['scripts/evidence/korea_readiness.py', 'scripts/evidence/korea_readiness_coverage.ts',
             'scripts/evidence/global_batch.py', 'scripts/evidence/code_dates.py',
             'scripts/reference/admissions.py', 'scripts/reference/common.py', 'scripts/discovery/review.py',
             'src/resolve.ts', 'src/types.ts', 'src/validate.ts', 'src/time.ts', 'src/evidence.ts',
             'schema/dataset.schema.json',
             'pnpm-lock.yaml']
    files = {p: sha((ROOT / p).read_bytes()) for p in paths}
    # The existing admission rehearsal rewrites package.json key order while
    # preparing its disposable candidate. Bind every package value canonically;
    # executable source, schema and dependency-lock bytes remain exact hashes.
    canonical_json = {'package.json': sha(canonical(load(ROOT / 'package.json')))}
    manifest = {'formatVersion': 1, 'files': files, 'canonicalJsonInputs': canonical_json}
    policy = load(BASE / 'policy.json')
    return {'policyId': policy['policyId'], 'version': policy['version'],
            'policySha256': sha(canonical({k: v for k, v in policy.items() if k != 'status'})),
            'scopeSha256': sha(canonical(policy['scope'])), 'executorFiles': files,
            'canonicalJsonInputs': canonical_json, 'executorManifestFormatVersion': 1,
            'executorSha256': sha(canonical(manifest)), 'status': 'draft',
            'authorization': None, 'productionBound': False,
            'meaning': 'Research evaluator fingerprint only. No Korean production adapter, activation or admission authority.'}


def validate_draft(policy):
    require(policy['status'] == 'draft' and policy['authorization'] is None and not policy['productionBound'],
            'Korean research cannot record production authority')
    scope = policy['scope']
    require(scope['namespace'] == 'ICAO' and scope['codes'] == ['RKSI', 'RKSS'] and
            scope['originalHosts'] == ['aim.koca.go.kr'] and scope['issuerFamily'] == 'KR-MOLIT-AIP' and
            not scope['newPhysicalIdentities'] and not scope['newIataAssignments'] and not scope['publishedCorrections'],
            'Korean research scope enlarged')
    require(scope['window'] == {'from': '2025-04-18', 'toExclusive': '2025-05-15', 'timezone': 'Asia/Seoul'} and
            policy['evidencePredicates']['maxOuterAiracGapDays'] == 28, 'Untested Korean date budget')


def evidence_conditions():
    """Evaluate the finite research packet, without synthesizing any grant."""
    timeline = load(BASE / 'aip-timeline.json')
    checklists = load(BASE / 'checklist-reconciliation.json')
    ledgers = [load(BASE / ('notam-' + code + '.json')) for code in ('RKSI', 'RKSS')]
    fir = load(BASE / 'fir-screening.json')
    batch = load(BASE / 'identity-batch.json')
    policy = load(BASE / 'policy.json')
    left = dt.datetime.fromisoformat(timeline['editions'][0]['effectiveUtc'])
    right = dt.datetime.fromisoformat(timeline['editions'][2]['effectiveUtc'])
    return {
        'adjacentAiracAnchorsWithin28Days': (right - left).total_seconds() == 28 * 86400,
        'ordinaryEditionIncludedWithoutInventingClock': timeline['editions'][1]['effectiveInstantUtc'] is None and
            timeline['editions'][1]['effectiveOn'] == '2025-05-01',
        'officialSnapshotsReconciled': len(checklists['checklists']) == 6 and
            all(not c['missingFromChecklist'] and not c['missingFromLedger'] and c['allListedNumbersRecovered']
                for c in checklists['checklists']),
        'airportRelevantLifecyclesClosed': all(not l['countsByServerRecord'].get('unknown_lifecycle') for l in ledgers),
        'sharedFirLifecyclesClosed': not fir['selectedCounts'].get('unknown_lifecycle') and not fir['identitySignals'],
        'identityEvidenceBatchPrepared': len(batch['payload']['records']) == 2 and
            all(r['independentEvidenceDecision'].startswith('separate named physical site supported') for r in batch['payload']['records']),
        'identitiesOwnerApprovedAndFormallyAdmitted': False,
        'productionKoreanAdapterImplemented': False,
        'productionOwnerPolicyAuthorized': policy['authorization'] is not None,
        'productionBound': policy['productionBound'],
    }


def verify(*, originals=False, baseline=True):
    if baseline:
        frozen = load(BASE / 'baseline-lock.json')
        for p, h in frozen['files'].items():
            require(sha((ROOT / p).read_bytes()) == h, 'Protected PR23/main bytes changed: ' + p)
    lock = load(BASE / 'source-lock.json')
    sources = {s['sourceId']: s for s in lock['sources']}
    require(len(sources) == len(lock['sources']), 'Duplicate source ID')
    reused_citations = 0
    for s in sources.values():
        require(s['rights'] == 'metadata_and_minimal_citations_only', 'Unreviewed rights')
        if s.get('reusedFrom'):
            ref = s['reusedFrom']
            prior = next(x for x in load(ROOT / ref['sourceLockPath'])['sources'] if x['sourceId'] == ref['sourceId'])
            require(all(s[k] == prior[k] for k in ('originalSha256', 'extractedTextSha256', 'normalizedTextSha256')),
                    'Reused source drift')
            excerpt_path = ROOT / Path(ref['sourceLockPath']).parent / prior['excerptPath']
            require(sha(excerpt_path.read_bytes()) == prior['excerptSha256'], 'Changed reused excerpt')
            reused_citations += len(load(excerpt_path)['spans'])
            if originals:
                import code_dates
                raw, extracted = source_bytes(s)
                for span in load(excerpt_path)['spans']:
                    text = raw.decode('utf-8') if span['representation'] == 'decoded_html' else code_dates.span_text(span, extracted, raw)
                    require(text[span['characterStart']:span['characterEnd']] == span['quote'], 'Reused citation drift')
                    if span.get('page'):
                        require(span['quote'] in ' '.join(extracted.split('\f')[span['page'] - 1].split()),
                                'Wrong reused physical PDF page')
        if originals:
            source_bytes(s)
    citations = load(BASE / 'citations.json')['citations']
    totals = collections.Counter()
    for c in citations:
        require(c['sourceId'] in sources and 0 < len(c['quote']) <= 300, 'Unbound/excessive citation')
        totals[c['sourceId']] += len(c['quote'])
        if originals:
            raw, text = source_bytes(sources[c['sourceId']])
            representation = c.get('representation', 'normalized_text')
            if representation == 'json_pointer':
                value = json.loads(raw)
                for key in c['jsonPointer'].strip('/').split('/'):
                    value = value[int(key)] if isinstance(value, list) else value[key]
                text = str(value)
            else:
                text = ' '.join(text.split())
            require(text[c['characterStart']:c['characterEnd']] == c['quote'], 'Citation drift: ' + c['citationId'])
            if c.get('page'):
                _, extracted = source_bytes(sources[c['sourceId']])
                require(c['quote'] in ' '.join(extracted.split('\f')[c['page'] - 1].split()), 'Wrong PDF physical page')
    require(all(n <= 600 for n in totals.values()), 'Excessive combined source quotation')
    for location in ('RKSI', 'RKSS'):
        ledger = load(BASE / ('notam-' + location + '.json'))
        rows = ledger['records'] + ledger['laterLinkedSuccessors']
        require(len(ledger['records']) == ledger['pr23RowsReconciled'], 'Incomplete lifecycle ledger')
        for row in ledger['records']:
            require(row['assessment'] == lifecycle(row, rows), 'Detached lifecycle decision')
        if originals:
            require(ledger == make_ledger(location, sources), 'Detached original NOTAM ledger')
    fir = load(BASE / 'fir-screening.json')
    if originals:
        responses = {}
        for row in fir['records']:
            sid = row['sourceId']
            if sid not in responses:
                responses[sid] = json.loads(source_bytes(sources[sid])[0])
            index = int(row['jsonPointer'].split('/')[-1])
            require({k: v for k, v in row.items() if k != 'assessment'} ==
                    metadata(responses[sid]['DATA'][index], sid, index), 'Detached FIR record')
        all_fir = []
        for segment in fir['segments']:
            sid = segment['sourceId']
            data = responses.get(sid) or json.loads(source_bytes(sources[sid])[0])
            require(len(data['DATA']) == data['Total'] == segment['total'] == segment['returned'], 'Truncated FIR segment')
            all_fir.extend(metadata(item, sid, i) for i, item in enumerate(data['DATA']))
        expected = []
        for row in all_fir:
            b, c = instant(row['b']['raw']), instant(row['c']['raw'])
            if row['noticeType'] == 'C' or (b and b >= END) or (c and not row['estimatedEnd'] and c <= START):
                continue
            result = lifecycle(row, all_fir)
            if result['disposition'] in ('overlap', 'unknown_lifecycle'):
                expected.append({**row, 'assessment': result})
        require(fir['records'] == expected, 'Incomplete or detached FIR lifecycle decisions')
        require(fir['selectedCounts'] == dict(collections.Counter(r['assessment']['disposition'] for r in expected)),
                'Detached FIR counts')
        for checklist in load(BASE / 'checklist-reconciliation.json')['checklists']:
            row = checklist['checklist']
            data = responses[row['sourceId']]
            item = data['DATA'][int(row['jsonPointer'].split('/')[-1])]
            require(row == metadata(item, row['sourceId'], int(row['jsonPointer'].split('/')[-1])), 'Detached official checklist')
            listed = []
            text = item['ECODE'].split('LATEST PUBLICATIONS')[0]
            for year, numbers in re.findall(r'YEAR=(\d{4})\s+(.*?)(?=YEAR=|$)', text, re.S):
                listed.extend(item['NOTAM_NO'][0] + n + '/' + year[-2:] for n in re.findall(r'\b\d{4}\b', numbers))
            require(checklist['listedNoticeNumbers'] == listed, 'Detached checklist enumeration')
            lookup = json.loads(source_bytes(sources[checklist['lookupSourceId']])[0])
            require(lookup['Total'] == len(lookup['DATA']) == len(listed) and
                    set(listed) == {r['NOTAM_NO'] for r in lookup['DATA']}, 'Missing listed NOTAM original')
    require(load(BASE / 'evidence-conditions.json') == evidence_conditions(), 'Stale evidence predicates')
    require(load(BASE / 'bindings.json') == bindings(), 'Stale Korean research fingerprints')
    batch = load(BASE / 'identity-batch.json')
    require(batch['batchSha256'] == sha(canonical(batch['payload'])), 'Identity batch changed')
    require(batch['authorization'] is None and all(r['proposedPermanentAirportId'] is None for r in batch['payload']['records']),
            'Research identity admitted')
    validate_draft(load(BASE / 'policy.json'))
    require(load(BASE / 'assessment.json')['productionDecision'] == 'no_go', 'Production authority invented')
    artifacts = {str(p.relative_to(BASE)): sha(p.read_bytes()) for p in sorted(BASE.rglob('*'))
                 if p.is_file() and p.name != 'original-verification.json'}
    receipt = {'mode': 'local_original_verification', 'originalSources': len(sources),
               'reusedCitationsVerified': reused_citations, 'newCitationsVerified': len(citations),
               'artifactsSha256': artifacts, 'implementationSha256': sha(Path(__file__).read_bytes()),
               'sourceBytesActuallyReadForReceipt': True,
               'limits': 'Mechanical source-byte/extraction/citation replay, not human review or authorization.'}
    if originals:
        write(BASE / 'original-verification.json', receipt)
    else:
        require(load(BASE / 'original-verification.json') == receipt, 'Detached original-verification receipt')
    return {'sources': len(sources), 'newCitations': len(citations), 'reusedCitations': reused_citations,
            'originalBytesObtainedHere': originals,
            'productionDecision': 'no_go', 'formalNewResolved': 0}


def fetch_originals():
    """Explicit recovery; changed dynamic responses fail rather than replacing pins."""
    for source in load(BASE / 'source-lock.json')['sources']:
        path = (ROOT / source['cachePath']).resolve()
        require(path.is_relative_to((ROOT / 'work').resolve()), 'Unsafe original recovery path')
        if path.exists() and sha(path.read_bytes()) == source['originalSha256']:
            continue
        raw = urllib.request.urlopen(source['url'], timeout=60).read()
        require(sha(raw) == source['originalSha256'], 'Remote bytes drifted; preserve lock and review a new source: ' + source['sourceId'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def rights():
    import code_dates
    import history_audit as audit
    result = code_dates.rights()
    blobs, commits, locators, hashes = audit.inventory(load(audit.AUDIT))
    for s in load(BASE / 'source-lock.json')['sources']:
        hashes.update(s[k] for k in ('originalSha256', 'extractedTextSha256', 'normalizedTextSha256'))
    baseline = load(BASE / 'baseline-lock.json')['baseCommit']
    old = {oid for oid, _ in audit.tree(ROOT, baseline)}
    checked = set()
    for commit in audit.git(ROOT, 'rev-list', 'HEAD', '^' + baseline).decode().splitlines():
        for oid, path in audit.tree(ROOT, commit):
            if oid not in old and oid not in checked:
                require(not path.startswith('work/'), 'Private original in Git history')
                audit.check_payload(audit.git(ROOT, 'cat-file', 'blob', oid), blobs, commits | locators, hashes)
                checked.add(oid)
    paths = audit.git(ROOT, 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z').decode().split('\0')
    for p in filter(None, paths):
        require(not p.startswith('work/'), 'Private original staged')
        audit.check_payload(audit.git(ROOT, 'show', ':' + p), blobs, commits | locators, hashes)
    result.update(koreaNewReachableBlobsChecked=len(checked), koreaStagedFilesChecked=sum(bool(p) for p in paths),
                  koreanFullResponsesOrExtractionsPublished=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'originals', 'rights', 'build-ledgers', 'fetch-originals'])
    command = parser.parse_args().command
    if command == 'fetch-originals':
        fetch_originals()
    elif command == 'build-ledgers':
        sources = {s['sourceId']: s for s in load(BASE / 'source-lock.json')['sources']}
        for location in ('RKSI', 'RKSS'):
            write(BASE / ('notam-' + location + '.json'), make_ledger(location, sources))
    else:
        print(json.dumps(rights() if command == 'rights' else verify(originals=command == 'originals'), sort_keys=True))
