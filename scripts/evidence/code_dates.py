"""Custody checks for the PR23 research dossier; no policy or admission executor."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import global_batch as gb

ROOT = gb.ROOT
BASE = ROOT / 'research/evidence/code-dates'
CACHE = ROOT / 'work/pr23/originals'


def load(path):
    return json.loads(path.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def require(value, message):
    if not value:
        raise ValueError(message)


def span_text(span, extracted, raw):
    if span['representation'] == 'normalized_text':
        return ' '.join(extracted.split())
    require(span['representation'] == 'json_pointer', 'Unsupported citation representation')
    value = json.loads(raw)
    for key in span['jsonPointer'].strip('/').split('/'):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return str(value)


def original(source):
    raw = (CACHE / (source['cacheKey'] + '.raw')).read_bytes()
    extracted = gb.extract(raw, encoding=source.get('encoding', 'utf-8'))
    for key, content in [('originalSha256', raw), ('extractedTextSha256', extracted.encode()),
                         ('normalizedTextSha256', ' '.join(extracted.split()).encode())]:
        require(digest(content) == source[key], 'Original or extraction changed: ' + source['sourceId'])
    return raw, extracted


def verify(*, originals=False, baseline=True):
    lock = load(BASE / 'source-lock.json')
    require(digest((ROOT / 'scripts/evidence/global_batch.py').read_bytes()) == lock['extractionImplementationSha256'],
            'Changed extraction implementation')
    if baseline:
        frozen = load(BASE / 'baseline-lock.json')
        for name, expected in frozen['files'].items():
            require(digest((ROOT / name).read_bytes()) == expected, 'Protected main input changed: ' + name)
    sources, citations = {}, set()
    for source in lock['sources']:
        sid = source['sourceId']
        require(sid not in sources, 'Duplicate source ID')
        path = (BASE / source['excerptPath']).resolve()
        require(path.is_relative_to((BASE / 'excerpts').resolve()), 'Unsafe excerpt path')
        retained = path.read_bytes()
        require(digest(retained) == source['excerptSha256'], 'Changed excerpt: ' + sid)
        excerpt = json.loads(retained)
        for key in ['sourceId', 'originalSha256', 'extractedTextSha256', 'normalizedTextSha256']:
            require(excerpt[key] == source[key], 'Detached provenance: ' + sid)
        require(source['rights']['mode'] == 'metadata_and_short_excerpts' and
                source['rights']['fullRedistribution'] == 'not_established', 'Unreviewed rights claim')
        require(sum(len(s['quote']) for s in excerpt['spans']) <= 600, 'Excessive retained quotation')
        raw, extracted = original(source) if originals else (None, None)
        for span in excerpt['spans']:
            require(span['citationId'] not in citations, 'Duplicate citation ID')
            citations.add(span['citationId'])
            require(0 < len(span['quote']) <= 300 and span['characterStart'] >= 0 and
                    span['characterEnd'] - span['characterStart'] == len(span['quote']), 'Bad citation span')
            if originals:
                text = span_text(span, extracted, raw)
                require(text[span['characterStart']:span['characterEnd']] == span['quote'], 'Citation not in original: ' + sid)
                if span['page'] is not None:
                    pages = extracted.split('\f')
                    require(0 < span['page'] <= len(pages) and
                            span['quote'] in ' '.join(pages[span['page'] - 1].split()), 'Wrong physical PDF page')
        sources[sid] = source
    require({p.name for p in (BASE / 'excerpts').glob('*.json')} ==
            {Path(s['excerptPath']).name for s in sources.values()}, 'Uncatalogued or missing excerpt')
    for reused in lock['reusedOriginalsRechecked']:
        prior = {r['sourceId']: r for r in load(ROOT / reused['sourceLockPath'])['sources']}[reused['sourceId']]
        require(all(reused[k] == prior[k] for k in ['originalSha256', 'extractedTextSha256', 'normalizedTextSha256']),
                'Reused original differs from PR22')
        if originals:
            original({**reused, 'encoding': prior.get('encoding', 'utf-8')})
    cases = load(BASE / 'assessments.json')
    require(cases['dataVersion'] == '0.10.0' and cases['schemaVersion'] == '3.0.0', 'Unexpected version')
    require(cases['decision'] == 'pending' and cases['reviewer'] is None and
            cases['newMarketAuthorization'] is None and not cases['productionEligible'], 'Invented approval')
    for case in cases['cases']:
        require(set(case['sourceIds']) <= sources.keys(), 'Unbound case source')
        require(case['reviewer'] is None and case['decision'] == 'pending' and
                case['formalIdentityAction'] == 'none' and case['approvedCompleteLocalDateWindow'] is None and
                case['firstAllocationOn'] is None and case['finalWithdrawalOn'] is None, 'Research promoted to approval')
        for observation in case['observations']:
            require(observation['sourceId'] in sources and observation['validityWindow'] is None and
                    not observation['allocationDateProved'], 'Observation promoted to validity')
    screening = load(BASE / 'korea-screening.json')
    require(not screening['productionEligible'] and screening['reviewer'] is None, 'Screening is not authorization')
    for group in screening['notamGroups']:
        require(len(group['records']) == group['totalReturned'] == group['recordsScreened'], 'Incomplete NOTAM result')
        require(len({r['serverRecordId'] for r in group['records']}) == len(group['records']), 'Duplicate server record')
        if originals:
            data = json.loads(original(sources[group['sourceId']])[0])
            require(data['Total'] == group['totalReturned'], 'Detached NOTAM total')
            for record in group['records']:
                item = data['DATA'][int(record['jsonPointer'].split('/')[-1])]
                require(item['SEQ'] == record['serverRecordId'] and item['NOTAM_NO'] == record['notamNo'] and
                        item['LOCATION'] == record['location'] and item['ISSUE_TIME'] == record['issuedUtcYYMMDDhhmm'] and
                        item.get('EFFECTIVESTART') == record['bUtc'] and item.get('EFFECTIVEEND') == record['cUtc'] and
                        item['QCODE'] == record['qcode'] and
                        digest(item['FULL_TEXT'].encode()) == record['fullTextSha256'], 'Detached NOTAM metadata')
    supplements = screening['supplementScreening']
    require(supplements['allSelectedUrlsRetrieved'] and
            all(r['sourceId'] in sources and r['originalSha256'] == sources[r['sourceId']]['originalSha256']
                for r in supplements['rows']), 'Unbound supplement screening')
    receipt = {'mode': 'local_original_verification', 'verifiedOn': '2026-10-30',
               'sources': [{k: row[k] for k in ['sourceId', 'originalSha256', 'extractedTextSha256',
                                                'normalizedTextSha256', 'excerptSha256']} for row in sources.values()],
               'reusedOriginalsRechecked': lock['reusedOriginalsRechecked'],
               'researchArtifactSha256': {name: digest((BASE / name).read_bytes()) for name in
                   ['assessments.json', 'korea-screening.json', 'MATRIX.zh-CN.md', 'baseline-lock.json']},
               'verificationImplementationSha256': digest(Path(__file__).read_bytes())}
    if originals:
        (BASE / 'original-verification.json').write_bytes(encoded(receipt))
    else:
        require(load(BASE / 'original-verification.json') == receipt, 'Detached original verification receipt')
    return {'sources': len(sources), 'citations': len(citations), 'cases': len(cases['cases']),
            'originalBytesRecheckedHere': originals, 'formalNewResolvedQueries': 0,
            'unchangedUnauthorizedHypotheticalResolvedQueries': 54}


def rights():
    import history_audit as audit
    import priority_markets as pm
    result = pm.rights_audit()
    blobs, commits, locators, hashes = audit.inventory(load(audit.AUDIT))
    for source in load(BASE / 'source-lock.json')['sources']:
        hashes.update(source[k] for k in ['originalSha256', 'extractedTextSha256', 'normalizedTextSha256'])
    baseline = load(BASE / 'baseline-lock.json')['baseCommit']
    old_blobs = {oid for oid, _ in audit.tree(ROOT, baseline)}
    checked = set()
    for commit in audit.git(ROOT, 'rev-list', 'HEAD', '^' + baseline).decode().splitlines():
        for oid, path in audit.tree(ROOT, commit):
            if oid not in old_blobs and oid not in checked:
                require(not path.startswith('work/'), 'Private acquisition in history')
                audit.check_payload(audit.git(ROOT, 'cat-file', 'blob', oid), blobs, commits | locators, hashes)
                checked.add(oid)
    staged = audit.git(ROOT, 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z').decode().split('\0')
    count = 0
    for path in filter(None, staged):
        require(not path.startswith('work/'), 'Private acquisition staged')
        audit.check_payload(audit.git(ROOT, 'show', ':' + path), blobs, commits | locators, hashes)
        count += 1
    result.update(codeDateHistoricalBlobsChecked=len(checked), codeDateStagedFilesChecked=count,
                  codeDateOriginalsAndFullExtractionsAdded=False,
                  scope='Mechanical reachable-history/hash gate and manual minimal-quotation review; no blanket redistribution licence inferred.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'originals', 'rights'])
    args = parser.parse_args()
    print(json.dumps(rights() if args.command == 'rights' else verify(originals=args.command == 'originals'), sort_keys=True))
