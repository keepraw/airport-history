"""Global batch 5 (kept outside scripts/, which legacy executors fingerprint wholesale): targeted original-document research over existing event groups.

fetch     acquire originals into ignored work/global-batch-5/ and record their hashes
validate  offline structural/rights checks of the committed research layer

No discovery scan, no bulk rebuild, no formal-data write. Originals, full extractions,
images and pages stay in ignored work/; only metadata, hashes and short anchors are public.
"""
import argparse
import datetime
import gzip
import hashlib
import html
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / 'research/evidence/global-batch-5'
PRIVATE = ROOT / 'work/global-batch-5/originals'
MAX_ANCHOR = 80
DISPOSITIONS = {'ready_to_admit', 'insufficient_evidence', 'excluded', 'pending_review'}
CLAIMS = {'physicalIdentity', 'iata', 'icao', 'historicalBoundary', 'historicalNames', 'closureAndReplacement'}
DATE_KEYS = {'openingDate', 'passengerServiceEndDate', 'physicalClosureDate', 'iataAssignmentDate', 'icaoAssignmentDate'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(text):
    return ' '.join(html.unescape(text).split())


def decode(raw):
    for encoding in ('utf-8', 'cp932', 'gb18030'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def extract(raw):
    if raw[:5] == b'%PDF-':
        result = subprocess.run(['pdftotext', '-layout', '-', '-'], input=raw, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
        return result.stdout.decode('utf-8', 'replace')
    text = decode(raw)
    text = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', ' ', text)
    return re.sub(r'<[^>]+>', ' ', text)


def fetch(only=None):
    catalog = load(BASE / 'catalog.json')
    PRIVATE.mkdir(parents=True, exist_ok=True)
    lock_path = BASE / 'source-lock.json'
    lock = load(lock_path) if lock_path.exists() else {'formatVersion': 1, 'sources': {}}
    for source in catalog['sources']:
        sid = source['sourceId']
        if only and sid not in only:
            continue
        request = urllib.request.Request(source['url'], headers={'User-Agent': 'Mozilla/5.0 (airport-history research)'})
        observed = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw, status, ctype = response.read(), response.status, response.headers.get('Content-Type', '')
        except Exception as error:  # Record the failure; never substitute another capture.
            lock['sources'][sid] = {'accessResult': 'failed', 'error': type(error).__name__ + ': ' + str(error)[:160],
                                    'observedAtUtc': observed, 'url': source['url']}
            print(sid, 'FAILED', error)
            continue
        if not raw:
            lock['sources'][sid] = {'accessResult': 'failed', 'error': f'HTTP {status} with empty body',
                                    'observedAtUtc': observed, 'url': source['url']}
            print(sid, 'EMPTY', status)
            continue
        key = digest(raw)
        (PRIVATE / key).write_bytes(raw)
        text = normalized(extract(raw))
        markup = normalized(decode(raw))  # attribute values in XML/HTML records
        anchors = {a: a in text or a in markup for a in source['anchors']}
        lock['sources'][sid] = {'accessResult': 'content_inspected', 'httpStatus': status, 'contentType': ctype.split(';')[0],
                                'originalBytes': len(raw), 'originalSha256': key,
                                'normalizedTextSha256': digest(text.encode()), 'textCharacters': len(text),
                                'anchorsLocated': anchors, 'imageOnly': bool(source.get('imageOnly')) or not text.strip(),
                                'observedAtUtc': observed, 'url': source['url']}
        print(sid, status, len(raw), key[:12], anchors)
    write(lock_path, lock)


def validate():
    catalog, lock = load(BASE / 'catalog.json'), load(BASE / 'source-lock.json')
    batch = load(BASE / 'batch.json')
    sources = {s['sourceId']: s for s in catalog['sources']}
    require(len(sources) == len(catalog['sources']), 'Duplicate source ID')
    require(set(lock['sources']) == set(sources), 'Source lock and catalog disagree')
    hashes = {}
    for sid, source in sources.items():
        require(source['url'].startswith('https://') and source['type'] in {'primary', 'secondary'}, 'Bad source ' + sid)
        require(source['supports'] and source['limitations'] and source['dateMeaning'], 'Missing source scope ' + sid)
        require(all(len(a) <= MAX_ANCHOR for a in source['anchors']), 'Anchor exceeds minimal citation size ' + sid)
        entry = lock['sources'][sid]
        if entry['accessResult'] == 'content_inspected':
            require(re.fullmatch('[0-9a-f]{64}', entry['originalSha256']), 'Bad original hash ' + sid)
            require(entry['imageOnly'] or all(entry['anchorsLocated'].values()), 'Unlocated anchor ' + sid)
            # Several captures of one byte stream are one original, never independent evidence.
            require(entry['originalSha256'] not in hashes, 'Duplicate original counted twice: ' + sid)
            hashes[entry['originalSha256']] = sid
    events = batch['events']
    require(0 < len(events) <= 12 and batch['selection']['eventCount'] == len(events), 'Batch must hold 1..12 events')
    groups = load_groups()
    seen_groups, seen_candidates = set(), set()
    mapped = existing_mappings()
    for event in events:
        require(event['status'] in DISPOSITIONS, 'Unknown disposition')
        for gid in event['eventGroupIds']:
            require(gid in groups and gid not in seen_groups, 'Unknown or duplicate event group ' + gid)
            seen_groups.add(gid)
            for cid in groups[gid]:
                require(cid not in seen_candidates and cid not in mapped, 'Candidate already mapped ' + cid)
                seen_candidates.add(cid)
        require(set(event['claims']) == CLAIMS, 'Missing claim review ' + event['caseKey'])
        for claim in event['claims'].values():
            require(claim['conclusion'] and set(claim['sourceIds']) <= set(sources), 'Dangling claim ' + event['caseKey'])
            if claim['evidenceType'] == 'primary_direct':
                require(any(sources[s]['type'] == 'primary' for s in claim['sourceIds']), 'Primary claim lacks primary source')
        require(set(event['dates']) == DATE_KEYS, 'Dates must keep every event kind separate ' + event['caseKey'])
        require(event['evidenceGaps'] and event['nextAction'], 'Missing gaps/next action ' + event['caseKey'])
        require(event['formalAdmission'] == {'airports': [], 'assignments': [], 'names': []}, 'Research layer cannot admit')
    proposals = load(BASE / 'proposals.json')
    require(proposals['authorization'] is None and proposals['formal'] is False, 'Proposal claims authority')
    formal = load(ROOT / 'data/airports.json')
    require(formal['dataVersion'] == '0.10.0' and [len(formal[k]) for k in ('airports', 'assignments', 'sources', 'names')] ==
            [37, 52, 101, 3], 'Formal data changed by research batch')
    subprocess.run(['node', 'research/evidence/global-batch-5/tools/coverage.ts', 'validate'], cwd=ROOT, check=True)
    print(f'Validated global batch 5: {len(events)} events, {len(seen_groups)} event groups, {len(sources)} sources, '
          f'{len(hashes)} distinct originals; formal data unchanged.')


def load_groups():
    result = {}
    with gzip.open(ROOT / 'reference/triage/groups.jsonl.gz', 'rt') as handle:
        for line in handle:
            group = json.loads(line)
            result[group['eventGroupId']] = group['candidateIds']
    return result


def existing_mappings():
    ids = set()
    for path in sorted((ROOT / 'research/discovery/batches').glob('*.json')):
        for event in load(path)['events']:
            ids.update(event['candidateIds'] + event['relatedCandidateIds'])
    return ids


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'validate'])
    parser.add_argument('--source', action='append')
    args = parser.parse_args()
    fetch(args.source) if args.command == 'fetch' else validate()
