"""Finite Korean evidence evaluation. Offline custody is never original replay."""
import collections
import datetime as dt
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
import korea_readiness as research

PACKET = ROOT / 'research/evidence/code-dates/korea-readiness'
UTC = dt.timezone.utc


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def load(path):
    return json.loads(path.read_text())


def window(editions, maximum_gap):
    require(len(editions) >= 2 and editions[0]['kind'] == editions[-1]['kind'] == 'AIRAC',
            'Two controlled outer AIRAC anchors required')
    left, right = [dt.datetime.fromisoformat(e['effectiveUtc']) for e in (editions[0], editions[-1])]
    require(left.utcoffset() == right.utcoffset() == dt.timedelta(0) and
            0 < (right-left).total_seconds() <= maximum_gap * 86400, 'Unknown/reversed/excessive AIRAC gap')
    tz = ZoneInfo('Asia/Seoul')
    # Exclude both incomplete local observation days, including the first day.
    start = left.astimezone(tz).date() + dt.timedelta(days=1)
    end = right.astimezone(tz).date()
    for e in editions[1:-1]:
        require(e['kind'] == 'ordinary' and e['effectiveInstantUtc'] is None and
                e['effectiveOn'] == e['publicationOn'] and
                start <= dt.date.fromisoformat(e['effectiveOn']) < end and
                e['ad21Or22Replaced'] is False, 'Unknown intervening amendment or invented clock')
    require(start < end, 'No complete local dates')
    return {'from': start.isoformat(), 'toExclusive': end.isoformat(), 'timezone': 'Asia/Seoul'}


def notice_checks(rows, start, end):
    """Re-evaluate relationships, retaining duplicate byte identities and multipart parts."""
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r['notamNo']].append(r)
        require(r['noticeType'] in ('N', 'R', 'C') and research.instant(r['issued']['raw']),
                'Unknown NOTAM kind/issue clock')
    for same in groups.values():
        require(len({r['fullTextSha256'] for r in same}) == 1, 'Duplicate NOTAM number with different original bytes')
    multipart = collections.defaultdict(list)
    for r in rows:
        m = re.fullmatch(r'([A-Z]\d{4}/\d{2})([A-Z])(\d{2})', r['notamNo'])
        if m:
            multipart[m[1]].append((m[2], int(m[3])))
    for parts in multipart.values():
        n = parts[0][1]
        require(n > 0 and all(total == n for _, total in parts) and
                {label for label, _ in parts} == {chr(65+i) for i in range(n)}, 'Missing/conflicting multipart NOTAM')
    counts = collections.Counter()
    for row in rows:
        assessment = research.lifecycle(row, rows)
        # Research uses the same finite window; compare clocks before relying on it.
        require(start == research.START and end == research.END, 'Unsupported evidence window')
        relevant = assessment['disposition'] in ('overlap', 'unknown_lifecycle')
        if relevant:
            require(assessment['disposition'] != 'unknown_lifecycle' and not assessment['missingPredecessor'],
                    'Unresolved NOTAM lifecycle/predecessor')
            require(not row['identityChangeSignal'] and row['qcode'] != 'QFALC',
                    'Airport identity/whole-airport event requires manual review')
        counts[assessment['disposition']] += 1
    return dict(counts)


def original_notice(item):
    """Reject disagreement between API date/code fields and the actual notice text."""
    text = item['FULL_TEXT']
    header = re.search(r'\b([A-Z]\d{4}/\d{2}(?:[A-Z]\d{2})?)\s+NOTAM[NRC]\b', text)
    require(header and header[1] == item['NOTAM_NO'], 'Original NOTAM number/kind conflict')
    b = re.search(r'\bB\)\s*(\d{10})', text)
    require((b[1] if b else None) == (item.get('EFFECTIVESTART') or None), 'Original NOTAM B clock conflict')
    c = re.search(r'\bC\)\s*(PERM|\d{10})', text)
    require((c[1] if c else None) == (item.get('EFFECTIVEEND') or None), 'Original NOTAM C clock conflict')
    q = re.search(r'\bQ\)\s*[A-Z]{4}/([A-Z]{5})/', text)
    require(q and q[1] == item['QCODE'], 'Original NOTAM Q-code conflict')
    location = re.search(r'\bA\)\s*([^\r\n]*?)(?=\s+[BC]\)|$)', text, re.M)
    require(location and item['LOCATION'] in re.findall(r'\b[A-Z]{4}\b', location[1]), 'Original NOTAM location conflict')
    require(' '.join(item['ECODE'].split()) in ' '.join(text.split()), 'Original E text/API conflict')


def duplicate_bytes(rows):
    by_number = collections.defaultdict(set)
    for r in rows:
        by_number[r['notamNo']].add(r['fullTextSha256'])
    require(all(len(v) == 1 for v in by_number.values()), 'Different original bytes for duplicate FIR/airport number')


def evaluate(policy, *, originals=False):
    """Pinned metadata replay plus independent predicates; production also reads every raw source."""
    import hashlib
    for name, expected in policy['evidenceFiles'].items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                'Evidence artifact changed: ' + name)
    # This immutable research receipt is custody only; no research boolean authorizes admission.
    research.verify(baseline=False)
    sources = {s['sourceId']: s for s in load(PACKET / 'source-lock.json')['sources']}
    timeline = load(PACKET / 'aip-timeline.json')
    actual_window = window(timeline['editions'], policy['maximumAiracGapDays'])
    require(actual_window == policy['scope']['window'], 'Recomputed date scope differs')
    tz = ZoneInfo(actual_window['timezone'])
    start, end = [dt.datetime.fromisoformat(actual_window[k]).replace(tzinfo=tz).astimezone(UTC)
                  for k in ('from', 'toExclusive')]
    statements = {s['code']: s for s in timeline['identityStatements']}
    results = []
    for site in policy['scope']['sites']:
        code = site['code']
        require(statements[code]['arp'] == site['arpDms'], 'Conflicting AIP ARP')
        ledger = load(PACKET / ('notam-' + code + '.json'))
        require(ledger['serverTotal'] == ledger['returnedRows'] and not ledger['archiveCompleteSince2001'],
                'Truncated/unknown airport coverage')
        rows = ledger['records'] + ledger['laterLinkedSuccessors']
        counts = notice_checks(rows, start, end)
        results.append({'code': code, 'window': actual_window, 'arpDms': site['arpDms'],
                        'counts': counts, 'sourceIds': [e['ad2SourceIds'][i]
                          for e in timeline['editions'] for i, s in enumerate(policy['scope']['sites']) if s == site]})
    fir = load(PACKET / 'fir-screening.json')
    require(fir['segments'] and all(s['total'] == s['returned'] for s in fir['segments']), 'Truncated FIR coverage')
    for r in fir['records']:
        require(r['assessment']['disposition'] == 'overlap' and not r['identityChangeSignal'] and
                r['qcode'] != 'QFALC', 'Unresolved FIR/airport restriction')
        require(r['assessment']['effectiveEndUtc'] is not None, 'Unknown FIR end')
    # Parts may share base numbers but must not be silently collapsed.
    multipart = [r for r in fir['records'] if re.search(r'[A-Z]\d{2}$', r['notamNo'])]
    for r in multipart:
        total = int(r['notamNo'][-2:])
        require({x['notamNo'][-3] for x in multipart if x['seriesBaseNo'] == r['seriesBaseNo']} ==
                {chr(65+i) for i in range(total)}, 'Incomplete FIR multipart message')
    checks = load(PACKET / 'checklist-reconciliation.json')['checklists']
    require({(c['snapshot']['utc'][:10], c['checklist']['notamNo'][0]) for c in checks} ==
            {(d, s) for d in policy['snapshotDates'] for s in ('A', 'G', 'Z')}, 'Missing official snapshot')
    for c in checks:
        # Reconstruct the outstanding set from issue/successor times, including future B.
        snap = dt.datetime.fromisoformat(c['snapshot']['utc'])
        expected = set()
        for site in policy['scope']['sites']:
            ledger = load(PACKET / ('notam-' + site['code'] + '.json'))
            rows = ledger['records'] + ledger['laterLinkedSuccessors']
            for r in rows:
                if r['notamNo'][0] != c['checklist']['notamNo'][0] or r['noticeType'] == 'C':
                    continue
                issued = research.instant(r['issued']['raw'])
                termination = research.lifecycle(r, rows)['effectiveEndUtc']
                if issued <= snap and (termination is None or dt.datetime.fromisoformat(termination) > snap):
                    expected.add(r['notamNo'])
        actual = {r['notamNo'] for r in c['airportOutstandingNotices']}
        require(expected == actual and actual <= set(c['listedNoticeNumbers']), 'Official checklist/graph mismatch')
    publications = load(PACKET / 'publication-crosscheck.json')
    for s in publications['supplementOriginals']:
        require(s['sourceId'] in sources and s['originalSha256'] == sources[s['sourceId']]['originalSha256'],
                'Missing/changed SUP original')
        require(not s['codeOrArpChangeEstablished'], 'SUP identity conflict')
    raw = {}
    if originals:
        # No stored receipt or --offline option can replace this production condition.
        for sid, s in sources.items():
            raw[sid] = research.source_bytes(s)
        for site, result in zip(policy['scope']['sites'], results):
            for sid in result['sourceIds']:
                require(urlparse(sources[sid]['url']).hostname in policy['scope']['originalHosts'], 'Unofficial AIP host')
                text = ' '.join(raw[sid][1].split())
                require(site['code'] in text and site['arpDms'] in text and statements[site['code']]['name'] in text,
                        'Original AD code/name/ARP mismatch')
            require(load(PACKET / ('notam-' + site['code'] + '.json')) == research.make_ledger(site['code'], sources),
                    'Original NOTAM graph mismatch')
            for item in json.loads(raw['notam-all-' + site['code'].lower()][0])['DATA']:
                original_notice(item)
        all_fir = []
        for segment in fir['segments']:
            data = json.loads(raw[segment['sourceId']][0])
            require(data['Total'] == len(data['DATA']) == segment['total'], 'Raw FIR truncation')
            for item in data['DATA']:
                original_notice(item)
            all_fir.extend(research.metadata(item, segment['sourceId'], i) for i, item in enumerate(data['DATA']))
        duplicate_bytes(all_fir)
        selected = []
        for r in all_fir:
            b, c = research.instant(r['b']['raw']), research.instant(r['c']['raw'])
            if r['noticeType'] == 'C' or (b and b >= end) or (c and not r['estimatedEnd'] and c <= start):
                continue
            assessment = research.lifecycle(r, all_fir)
            if assessment['disposition'] in ('overlap', 'unknown_lifecycle'):
                selected.append({**r, 'assessment': assessment})
        require(selected == fir['records'], 'Omitted/unresolved raw FIR message')
        for r in fir['records']:
            item = json.loads(raw[r['sourceId']][0])['DATA'][int(r['jsonPointer'].split('/')[-1])]
            require(research.metadata(item, r['sourceId'], int(r['jsonPointer'].split('/')[-1])) ==
                    {k: v for k, v in r.items() if k != 'assessment'}, 'Raw FIR record mismatch')
        for c in checks:
            row = c['checklist']
            item = json.loads(raw[row['sourceId']][0])['DATA'][int(row['jsonPointer'].split('/')[-1])]
            require(research.metadata(item, row['sourceId'], int(row['jsonPointer'].split('/')[-1])) == row,
                    'Changed official checklist')
            listed = []
            for year, numbers in re.findall(r'YEAR=(\d{4})\s+(.*?)(?=YEAR=|$)', item['ECODE'].split('LATEST PUBLICATIONS')[0], re.S):
                listed.extend(item['NOTAM_NO'][0] + n + '/' + year[-2:] for n in re.findall(r'\b\d{4}\b', numbers))
            require(listed == c['listedNoticeNumbers'], 'Changed checklist enumeration')
            data = json.loads(raw[c['lookupSourceId']][0])
            require(data['Total'] == len(data['DATA']) == len(c['listedNoticeNumbers']) and
                    {r['NOTAM_NO'] for r in data['DATA']} == set(c['listedNoticeNumbers']), 'Missing listed original')
        import code_dates
        for sid, s in sources.items():
            if not s.get('reusedFrom'):
                continue
            ref = s['reusedFrom']
            prior = next(x for x in load(ROOT / ref['sourceLockPath'])['sources'] if x['sourceId'] == ref['sourceId'])
            spans = load(ROOT / Path(ref['sourceLockPath']).parent / prior['excerptPath'])['spans']
            for span in spans:
                original, extracted = raw[sid]
                text = original.decode('utf-8') if span['representation'] == 'decoded_html' else code_dates.span_text(span, extracted, original)
                require(text[span['characterStart']:span['characterEnd']] == span['quote'], 'Original citation drift')
                if span.get('page'):
                    require(span['quote'] in ' '.join(extracted.split('\f')[span['page']-1].split()), 'Citation PDF page mismatch')
        for citation in load(PACKET / 'citations.json')['citations']:
            original, extracted = raw[citation['sourceId']]
            if citation.get('representation') == 'json_pointer':
                value = json.loads(original)
                for key in citation['jsonPointer'].strip('/').split('/'):
                    value = value[int(key)] if isinstance(value, list) else value[key]
                text = str(value)
            else:
                text = ' '.join(extracted.split())
            require(text[citation['characterStart']:citation['characterEnd']] == citation['quote'], 'New citation drift')
            if citation.get('page'):
                require(citation['quote'] in ' '.join(extracted.split('\f')[citation['page']-1].split()), 'New citation PDF page mismatch')
        for s in publications['supplementOriginals']:
            text = ' '.join(raw[s['sourceId']][1].split())
            for statement in s['explicitSupersessionStatements']:
                require(statement in text, 'SUP supersession changed')
    return {'mode': 'original-byte-replay' if originals else 'offline-locked-evidence-replay',
            'originalBytesReadHere': originals, 'freshNetworkAcquisition': False,
            'candidates': results, 'daysPerAirport': (end-start).days,
            'archiveCompleteSince2001': False, 'ordinaryEffectiveInstantUtc': None}
