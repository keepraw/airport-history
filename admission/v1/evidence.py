"""Private immutable CAS and append-only evidence versions; public metadata only."""
import argparse
import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlparse

from runtime import ROOT, PUBLIC, PRIVATE, canonical, digest, load, private_path, require, sha, write
import kr_evidence as old

LOCK = ROOT / 'research/evidence/code-dates/korea-readiness/source-lock.json'
WINDOW = {'from': '2025-04-18', 'toExclusive': '2025-05-15', 'timezone': 'Asia/Seoul'}


class Store:
    def __init__(self, root=PRIVATE / 'cas'):
        self.root = private_path(root)

    def path(self, key):
        require(isinstance(key, str) and re.fullmatch('[0-9a-f]{64}', key), 'Invalid content address')
        return private_path(self.root / 'sha256' / key[:2] / key[2:])

    def put(self, raw):
        key = digest(raw)
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            require(path.read_bytes() == raw, 'Corrupt immutable CAS object')
        else:
            with os.fdopen(fd, 'wb') as f:
                f.write(raw)
        return key

    def read(self, key):
        raw = self.path(key).read_bytes()
        require(digest(raw) == key, 'Changed original: content-address mismatch')
        return raw


_EXTRACTIONS = {}


def extract(raw):
    key = digest(raw)
    if key in _EXTRACTIONS:
        return _EXTRACTIONS[key]
    if raw.lstrip().startswith((b'{', b'[')):
        text = raw.decode('utf-8')
    else:
        text = old.research.gb.extract(raw)
    _EXTRACTIONS[key] = text
    return text


def save_version(payload, directory=PRIVATE / 'versions'):
    """Each observation creates a new manifest. Earlier manifests are never rewritten."""
    key = sha(payload)
    path = private_path(Path(directory) / (key + '.json'))
    if path.exists():
        require(load(path) == payload, 'Evidence version collision')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as f:
            f.write(canonical(payload) + b'\n')
    return key, path


def fetch_one(source, store):
    url = source['url']
    require(urlparse(url).scheme == 'https', 'HTTPS originals required')
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    result = {'sourceId': source['sourceId'], 'url': url, 'observedAt': now,
              'previousOriginalSha256': source['originalSha256'], 'rights': 'metadata_and_minimal_citations_only'}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Keepraw-evidence/2.0'}), timeout=30) as response:
            require(urlparse(response.url).hostname == urlparse(url).hostname, 'Cross-host original redirect needs review')
            raw = response.read(192 * 1024 * 1024 + 1)
            require(len(raw) <= 192 * 1024 * 1024, 'Original exceeds bounded acquisition size')
            result.update(finalUrl=response.url, contentType=response.headers.get('Content-Type', ''))
        key = store.put(raw)
        result.update(originalSha256=key, originalBytes=len(raw),
                      kind='locked-original' if key == source['originalSha256'] else 'reobtained-official-evidence',
                      normalizedTextSha256=digest(' '.join(extract(raw).split()).encode()))
        # Only recovered EXACT bytes may populate the legacy cache. Drift never overwrites it.
        if key == source['originalSha256']:
            target = private_path(ROOT / source['cachePath'])
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as f: f.write(raw)
        return result
    except Exception as error:
        return {**result, 'kind': 'unavailable', 'errorType': type(error).__name__, 'reason': str(error)[:240]}


def acquire():
    sources = load(LOCK)['sources']
    store = Store()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda source: fetch_one(source, store), sources))
    packet = {'formatVersion': 2, 'sourceLockSha256': digest(LOCK.read_bytes()),
              'windowToReevaluate': WINDOW, 'sources': results,
              'claim': 'Acquisition only; new bytes carry no inherited historical conclusion.'}
    key, path = save_version(packet)
    print(json.dumps({'versionSha256': key, 'privateManifest': str(path),
                      'obtained': sum('originalSha256' in r for r in results), 'total': len(results)}))
    return path


def replay(packet, store):
    require(not packet.get('simulation'), 'Synthetic originals cannot enter production replay')
    require(packet['formatVersion'] == 2 and packet['sourceLockSha256'] == digest(LOCK.read_bytes()) and
            packet['windowToReevaluate'] == WINDOW, 'Wrong evidence lineage/window')
    sources = load(LOCK)['sources']
    require(len(packet['sources']) == len(sources) and
            {s['sourceId'] for s in packet['sources']} == {s['sourceId'] for s in sources}, 'Incomplete evidence version')
    raw = {}
    for entry in packet['sources']:
        require(entry['kind'] in ('locked-original', 'reobtained-official-evidence', 'derived-official-notam-set'),
                'Untrusted original provenance kind')
        require('originalSha256' in entry or entry.get('kind') == 'derived-official-notam-set', 'Necessary original unavailable: ' + entry['sourceId'])
        source = next(s for s in sources if s['sourceId'] == entry['sourceId'])
        require(entry['url'] == source['url'] and entry['previousOriginalSha256'] == source['originalSha256'] and
                urlparse(entry.get('finalUrl', entry['url'])).hostname == urlparse(source['url']).hostname, 'Detached source provenance')
        observed = dt.datetime.fromisoformat(entry['observedAt'])
        require(observed.utcoffset() is not None and observed <= dt.datetime.now(dt.timezone.utc), 'Invalid observation clock')
        data = source_data(entry, store)
        raw[entry['sourceId']] = data
    return raw


def source_data(entry, store):
    if entry.get('kind') != 'derived-official-notam-set':
        raw = store.read(entry['originalSha256'])
        require(len(raw) == entry['originalBytes'], 'Original size mismatch')
        return raw
    from urllib.parse import parse_qs
    items = []
    require(entry['components'], 'Empty derived query set')
    for component in entry['components']:
        require('originalSha256' in component and urlparse(component['url']).hostname == 'aim.koca.go.kr' and
                urlparse(component['finalUrl']).hostname == 'aim.koca.go.kr', 'Unavailable/unofficial component original')
        observed = dt.datetime.fromisoformat(component['observedAt'])
        require(observed.utcoffset() is not None and observed <= dt.datetime.now(dt.timezone.utc), 'Invalid component observation')
        obj = json.loads(store.read(component['originalSha256']))
        requested = parse_qs(urlparse(component['url']).query)['sch_notam_no'][0]
        require(obj['Total'] == len(obj['DATA']) and obj['DATA'] and
                all(item['NOTAM_NO'] == requested for item in obj['DATA']), 'Incomplete single-notice recovery')
        items.extend(obj['DATA'])
    # Derived representation is deliberately not labelled as an original hash.
    return canonical({'Total': len(items), 'DATA': items})


def required_notices(sid):
    packet = old.PACKET
    rows = []
    if sid in ('notam-all-rksi', 'notam-all-rkss', 'kr-notam-rksi-available', 'kr-notam-rkss-available'):
        code = 'RKSI' if 'rksi' in sid else 'RKSS'
        ledger = load(packet / ('notam-' + code + '.json'))
        rows = ledger['records'] + ledger['laterLinkedSuccessors']
        if sid.startswith('kr-'):
            rows = [r for r in rows if r in ledger['records']]
    elif sid.startswith('notam-fir-'):
        rows = [r for r in load(packet / 'fir-screening.json')['records'] if r['sourceId'] == sid]
    # A replacement version reproves this window, not every expired record in
    # the earlier research ledger. Missing historical outstanding coverage is
    # independently blocked by the six official checklists.
    return [r for r in rows if r.get('assessment', {}).get('disposition') in ('overlap', 'unknown_lifecycle')]


def revalidate_source(entry, data):
    """Reprove only explicit facts. A present API response is never an archive snapshot."""
    sid = entry['sourceId']
    source = next(s for s in load(LOCK)['sources'] if s['sourceId'] == sid)
    normalized = ' '.join(extract(data).split())
    citations = [c for c in load(old.PACKET / 'citations.json')['citations'] if c['sourceId'] == sid]
    checked = 0
    for c in citations:
        if c.get('representation') == 'json_pointer':
            continue  # JSON record facts are checked by content identity below, not stale array offsets.
        require(c['quote'] in normalized, 'Citation fact missing/conflicting: ' + sid)
        checked += 1
    if data.lstrip().startswith(b'{'):
        obj = json.loads(data)
        if 'DATA' in obj:
            require(isinstance(obj['Total'], int) and obj['Total'] == len(obj['DATA']) or
                    sid == 'notam-all-rkrr' and len(obj['DATA']) == 9999 and obj['Total'] >= 9999,
                    'Truncated necessary NOTAM query: ' + sid)
            by_number = {}
            for item in obj['DATA']:
                old.original_notice(item)
                key = item['NOTAM_NO']
                by_number.setdefault(key, []).append(item)
            for row in required_notices(sid):
                items = by_number.get(row['notamNo'], [])
                require(items and all(digest(item['FULL_TEXT'].encode()) == row['fullTextSha256'] and
                        item['ISSUE_TIME'] == row['issued']['raw'] and item['QCODE'] == row['qcode'] and
                        item['LOCATION'] == row['location'] for item in items),
                        'Historical NOTAM changed/missing: ' + sid + '/' + row['notamNo'])
            if sid.startswith('checklist-'):
                checklist = next(c for c in load(old.PACKET / 'checklist-reconciliation.json')['checklists'] if c['lookupSourceId'] == sid)
                require(set(by_number) == set(checklist['listedNoticeNumbers']), 'Outstanding set incompletely recovered')
            return {'state': 'facts-revalidated', 'noticesParsed': len(obj['DATA']),
                    'historicalNoticesReproved': len(required_notices(sid)),
                    'historicalWindow': WINDOW if required_notices(sid) or sid.startswith('checklist-') else None,
                    'currentResponseIsHistoricalSnapshot': False}
    same_text = digest(normalized.encode()) == source['normalizedTextSha256']
    exact = digest(data) == source['originalSha256']
    require(exact or same_text or checked > 0, 'Changed original lacks a fact-specific replacement contract: ' + sid)
    return {'state': 'facts-revalidated', 'exactOriginal': exact, 'normalizedTextMatches': same_text,
            'citationsReproved': checked, 'historicalWindow': None,
            'meaning': 'Only cited facts revalidated; current site/UI/city pages do not prove historical allocation.'}


def assess(packet, store):
    results = []
    for entry in packet['sources']:
        try:
            require('originalSha256' in entry or entry.get('kind') == 'derived-official-notam-set', 'No recovered original')
            result = revalidate_source(entry, source_data(entry, store))
        except Exception as error:
            result = {'state': 'blocked', 'reason': str(error)[:240]}
        results.append({'sourceId': entry['sourceId'], **result})
    return {'formatVersion': 2, 'evidenceVersionSha256': sha(packet), 'sources': results,
            'originalBytesReadHere': True, 'fullHistoricalReplayPassed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['acquire', 'assess'])
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.command == 'acquire':
        acquire()
    else:
        require(args.manifest is not None, 'Evidence manifest required')
        result = assess(load(args.manifest), Store())
        write(PRIVATE / 'assessment.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'sources'}))
