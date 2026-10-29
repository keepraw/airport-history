"""Data-driven, resumable global evidence acquisition and offline research builds.

Never edits formal data or records a human decision. Catalogs and assessments
are reviewable data, not airport-specific branches in the collector.
"""
import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'research/evidence/global'
OUT = BASE / 'generated'
CUTOFF = '2026-10-29'
sys.path.insert(0, str(ROOT / 'scripts/reference'))
sys.path.insert(0, str(ROOT / 'scripts/discovery'))
from common import read_jsonl, write_jsonl, digest
from admissions import packets, validate_admission
from review import validate_batch_series


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def archive(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as z:
            z.write(raw)


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'div', 'br', 'tr', 'h1', 'h2', 'li'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def extract(raw, encoding='utf-8'):
    if raw.startswith(b'%PDF-'):
        return subprocess.run(['pdftotext', '-layout', '-', '-'], input=raw,
                              stdout=subprocess.PIPE, check=True).stdout.decode('utf-8')
    parser = Text()
    parser.feed(raw.decode(encoding))
    return '\n'.join(' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip())


def locked(directory):
    lock = json.loads((directory / 'source-lock.json').read_text())
    ids = set()
    for s in lock['sources']:
        if s['sourceId'] in ids:
            raise ValueError('Duplicate source component')
        ids.add(s['sourceId'])
        if s.get('retention') == 'metadata_and_cited_excerpts':
            path = (directory / s['retainedPath']).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise ValueError('Source path escapes snapshot')
            if sha(path.read_bytes()) != s['retainedSha256']:
                raise ValueError('Changed retained source: ' + s['sourceId'])
            excerpt = json.loads(path.read_text())
            if excerpt['originalSha256'] != s['originalSha256'] or excerpt['textOriginalSha256'] != s['textOriginalSha256']:
                raise ValueError('Detached original hash changed')
            s = {**s, 'retainedSpans': excerpt['spans']}
            yield s, '\n'.join(x['quote'] for x in excerpt['spans'])
            continue
        for field, digest in [('inputPath', 'inputSha256'), ('textPath', 'textSha256')]:
            path = (directory / s[field]).resolve()
            if not path.is_relative_to(directory.resolve()):
                raise ValueError('Source path escapes snapshot')
            compressed = path.read_bytes()
            if sha(compressed) != s[digest]:
                raise ValueError('Changed compressed source: ' + s['sourceId'])
            raw = gzip.decompress(compressed)
            expected = s['originalSha256' if field == 'inputPath' else 'textOriginalSha256']
            if sha(raw) != expected:
                raise ValueError('Changed original source: ' + s['sourceId'])
            if field == 'inputPath':
                original = raw
            else:
                text = raw.decode()
        if not original.startswith(b'%PDF-') and extract(original, s.get('encoding', 'utf-8')) != text:
            raise ValueError('HTML extraction does not reproduce')
        yield s, text


def fetch(output, only=None, limit=None, retry_failures=False, recover=False):
    output.mkdir(parents=True,exist_ok=True)
    with (output/'.acquisition.lock').open('w') as checkpoint:
        try:
            fcntl.flock(checkpoint,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another collector owns this source snapshot')
        return acquire(output,only,limit,retry_failures,recover)


def acquire(output, only=None, limit=None, retry_failures=False, recover=False):
    catalog = json.loads((BASE / 'catalog.json').read_text())
    catalog_ids = [s['sourceId'] for s in catalog['sources']]
    if len(catalog_ids)!=len(set(catalog_ids)) or any(not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,100}',sid) for sid in catalog_ids):
        raise ValueError('Catalog needs unique safe source IDs')
    if any(not s['url'].startswith('https://') for s in catalog['sources']):
        raise ValueError('Original acquisition requires an explicit HTTPS URL')
    expected = {s['sourceId']: s for s in json.loads((BASE / 'source-lock.json').read_text())['sources']} if recover else {}
    if recover and output.resolve() == BASE.resolve():
        raise ValueError('Recovery needs a separate destination')
    path = output / 'source-lock.json'
    lock = json.loads(path.read_text()) if path.exists() else {'formatVersion': 1, 'preparedOn': CUTOFF, 'sources': [], 'attempts': []}
    # Authenticate checkpoints before resuming, including every original byte.
    if path.exists():
        list(locked(output))
    done = {s['sourceId'] for s in lock['sources']}
    failed = {s['sourceId'] for s in lock['attempts'] if s['status'] == 'failed'}
    count = 0
    for entry in catalog['sources']:
        sid = entry['sourceId']
        if sid in done or (only and sid not in only) or (sid in failed and not retry_failures):
            continue
        if limit is not None and count >= limit:
            break
        count += 1
        attempt = {'sourceId': sid, 'requestedUrl': entry['url'], 'accessedAt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}
        try:
            raw = None
            for n in range(3):
                try:
                    request = urllib.request.Request(entry['url'], headers={'User-Agent': 'Keepraw-Airport-History/1.0 (public historical research)'})
                    with urllib.request.urlopen(request, timeout=25) as response:
                        raw, final = response.read(32 * 1024 * 1024 + 1), response.geturl()
                    break
                except urllib.error.HTTPError as error:
                    if error.code not in (429, 502, 503, 504) or n == 2:
                        raise
                    time.sleep(1 + n)
            if len(raw) > 32 * 1024 * 1024:
                raise ValueError('Publication exceeds bounded acquisition size')
            text = extract(raw, entry.get('encoding', 'utf-8'))
            if len(text) < 100 or any(x in text.lower() for x in ['verify you are human', 'just a moment...', 'access denied', 'request rejected', 'aeroporto não encontrado']):
                raise ValueError('Not an accessible original publication')
            normalized = ' '.join(text.split())
            if any(' '.join(x.split()) not in normalized for x in entry.get('expectedText', [])):
                raise ValueError('Required publication fingerprint absent')
            if recover and (sid not in expected or sha(raw) != expected[sid]['originalSha256']):
                raise ValueError('Original changed; recovery cannot adopt changed bytes')
            original_path, text_path = 'inputs/' + sid + '.gz', 'texts/' + sid + '.txt.gz'
            # Public access is not a licence to redistribute full articles/AIPs.
            archive(ROOT / 'work/global-originals' / (sid + '.gz'), raw)
            spans = []
            for quote in entry.get('expectedText', []):
                quote = ' '.join(quote.split())
                for page, part in enumerate(text.split('\f'), 1):
                    start = ' '.join(part.split()).find(quote)
                    if start >= 0:
                        spans.append({'page':page if '\f' in text else None,
                                      'normalizedCharacterStart':start,'normalizedCharacterEnd':start+len(quote),
                                      'quote':quote})
                        break
            retained_path = 'excerpts/' + sid + '.json'
            write(output / retained_path, {'originalSha256':sha(raw), 'textOriginalSha256':sha(text.encode()), 'spans':spans})
            source = {**entry, 'retrievalUrl': final, 'accessedAt': attempt['accessedAt'],
                      'originalPublicationKey': entry.get('originalPublicationKey', entry['url']),
                      'sourceType': 'primary', 'contentStatus': 'original', 'inputPath': original_path, 'textPath': text_path,
                      'originalSha256': sha(raw), 'originalBytes': len(raw),
                      'retention':'metadata_and_cited_excerpts','retainedPath':retained_path,
                      'retainedSha256':sha((output/retained_path).read_bytes()),
                      'inputSha256': None, 'textSha256': None, 'textOriginalSha256': sha(text.encode()),
                      'extractionTool': 'pdftotext-layout' if raw.startswith(b'%PDF-') else 'stdlib-HTMLParser-v1',
                      'independence': 'One original publication. Mirrors, indexes and repeated issuer statements do not constitute independent corroboration.'}
            source['sameOriginalContentAs'] = [s['sourceId'] for s in lock['sources'] if s['originalSha256']==source['originalSha256']]
            # Identical component bytes can persist across distinct AIP editions;
            # report content duplication without inventing publication lineage.
            if source['sameOriginalContentAs'] and 'originalPublicationKey' not in entry:
                prior=next(s for s in lock['sources'] if s['sourceId']==source['sameOriginalContentAs'][0])
                source['originalPublicationKey']=prior['originalPublicationKey']
            lock['sources'].append(source)
            attempt.update(status='acquired', originalSha256=sha(raw))
            print(sid, 'acquired', len(raw), flush=True)
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            attempt.update(status='failed', error=str(error), nextAction='Inspect the official endpoint or add an authorized alternative to the catalog; do not bypass access controls.')
            print(sid, 'FAILED', str(error)[:160], flush=True)
        lock['attempts'].append(attempt)
        write(path, lock)
        time.sleep(.35)


def registry():
    """Compact projection only: never reruns source history discovery."""
    records = {}
    for path in sorted((ROOT / 'reference/generated').glob('records.*.jsonl.gz')):
        for r in read_jsonl(path):
            if r['sourceId'] == 'ourairports':
                records[r['referenceId']] = {k: r[k] for k in ('referenceId', 'sourceEntityId', 'name', 'country', 'facilityType', 'identifiers', 'locations')}
    groups = {g['eventGroupId']: g for g in read_jsonl(ROOT / 'reference/triage/groups.jsonl.gz')}
    return records, groups


def select(records, groups, cases, limit=100):
    scores = {r['candidateId']: r['priorityScore'] for r in read_jsonl(ROOT / 'research/discovery/generated/verification-queue.jsonl.gz')}
    reviewed = {c['eventGroupId'] for c in cases}
    ranked = []
    for g in groups.values():
        r = records.get(g['physicalMatch']['referenceId'])
        if not r or not (r['identifiers']['IATA'] or any('IATA' in str(x) for x in g.get('classifications', []))):
            continue
        if r['facilityType'] not in ('large_airport', 'medium_airport', 'closed'):
            continue
        score = max((scores.get(cid, 0) for cid in g['candidateIds']), default=0)
        score += 40 * (r['facilityType'] == 'large_airport') + 25 * (r['facilityType'] == 'medium_airport')
        score += 30 * ('location_change_or_directory_correction' in g['classifications'])
        score += 20 * ('code_change_observation' in g['classifications'])
        ranked.append((-score, g['eventGroupId']))
    # One lead per external physical hypothesis; several events at one site stay
    # discoverable in the existing registry and explicit relatedGroupIds.
    chosen, seen = set(reviewed), {groups[g]['physicalMatch']['referenceId'] for g in reviewed}
    for _, gid in sorted(ranked):
        ref = groups[gid]['physicalMatch']['referenceId']
        if ref not in seen and len(chosen) < limit:
            chosen.add(gid); seen.add(ref)
    return [groups[g] for g in sorted(chosen)]


def citation(fact, loaded):
    source, text = loaded[fact['sourceId']]
    if source.get('contentStatus', 'original') != 'original':
        raise ValueError('Error response cannot support a fact')
    if source.get('retention') == 'metadata_and_cited_excerpts':
        matches = [s for s in source['retainedSpans'] if s['quote']==' '.join(fact['quote'].split())
                   and (not fact.get('page') or s['page']==fact['page'])]
        if len(matches)!=1:
            raise ValueError('Citation absent or ambiguous in retained original span: '+fact['factId'])
        return {**matches[0], 'locator':fact['locator'], 'originalSha256':source['originalSha256']}
    pages = text.split('\f')
    quote = ' '.join(fact['quote'].split())
    matches = []
    for n, page in enumerate(pages, 1):
        normalized = ' '.join(page.split())
        start = normalized.find(quote)
        if start >= 0:
            matches.append({'page': n if len(pages) > 1 else None, 'normalizedCharacterStart': start,
                            'normalizedCharacterEnd': start + len(quote), 'quote': quote,
                            'locator': fact['locator'], 'originalSha256': source['originalSha256']})
    if not matches:
        raise ValueError('Citation absent from original extraction: ' + fact['factId'])
    if fact.get('page'):
        matches = [m for m in matches if m['page'] == fact['page']]
    if len(matches) != 1:
        raise ValueError('Ambiguous citation needs explicit page: ' + fact['factId'])
    return matches[0]


def check_binding(assignment, facts):
    target = {'siteKey':assignment['siteKey'],'scheme':assignment['scheme'],'code':assignment['code']}
    if not any(target in facts[f]['codeBindings'] for f in assignment['factIds']):
        raise ValueError('No explicitly adjudicated physical-site/namespace/code binding')


def existing_identity(site, existing):
    record=existing.get(site['ourAirports'])
    if record and site.get('existingAirportId')!=record['airportId']:
        raise ValueError('Existing external reference needs an explicit permanent physical identity judgment; no automatic merge')
    return record


def prepare(output=OUT, source_directory=BASE):
    if not source_directory.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Source snapshots must stay inside the repository work directory')
    assessment = json.loads((BASE / 'assessments.json').read_text())
    if assessment['decision'] != 'pending' or assessment['reviewer'] is not None:
        raise ValueError('Research builder cannot record human approval')
    base_raw = (ROOT / 'test/curated-0.8.0.json').read_bytes()
    base = json.loads(base_raw)
    if sha(base_raw) != assessment['formalBaselineSha256']:
        raise ValueError('Formal baseline changed: explicitly rebase judgments and deduplication first')
    records, groups = registry()
    loaded = {s['sourceId']: (s, t) for s, t in locked(source_directory)}
    facts = {}
    for f in assessment['facts']:
        if f['factId'] in facts:
            raise ValueError('Duplicate fact')
        facts[f['factId']] = {**f, 'citation': citation(f, loaded)}
    proposed = json.loads(base_raw)
    proposed['dataVersion'] = assessment['proposalDataVersion']
    sites, dossiers, new_ids = {}, [], []
    existing = {a['externalIds'].get('ourAirports'): a for a in base['airports'] if a['externalIds'].get('ourAirports')}
    reserved = {s['ourAirports']: s['proposedAirportId'] for s in json.loads((ROOT / 'research/evidence/direct/assessments.json').read_text())['sites']}
    used_sources = set()
    for site in assessment['sites']:
        sid, oa = site['siteKey'], site['ourAirports']
        record = existing_identity(site,existing)
        ref = next(r for r in records.values() if r['sourceEntityId'] == oa)
        if ref['country'] != site['country']:
            raise ValueError('Cross-country physical match')
        if record:
            sites[sid] = record
            continue
        airport_id = reserved.get(oa, site['proposedAirportId'])
        fs = [facts[fid] for fid in site['factIds']]
        primary = sorted({f['sourceId'] for f in fs})
        coordinates = site.get('coordinates')
        coordinate_sources = [facts[site['coordinateFactId']]['sourceId']] if site.get('coordinateFactId') else ['global-ourairports-reference']
        if coordinates is None:
            coordinates = next((loc['coordinates'] for loc in ref['locations'] if loc['kind'] == 'snapshot'), None)
        record = {'airportId': airport_id,
                  'name': {'value': site['name'], 'status': 'reference', 'sourceIds': primary,
                           'note': 'Display label only; no official-name timeline is asserted.'},
                  'coordinates': {'value': coordinates, 'status': 'reference' if coordinates else 'unknown',
                                  'sourceIds': coordinate_sources if coordinates else [],
                                  'note': 'Reference point only, not a runway footprint or an identity inferred from coordinate displacement. ' + site['identityAssessment']},
                  'timezone': {'value': None, 'status': 'unknown', 'sourceIds': [], 'note': 'No historical IANA timezone claim.'},
                  'externalIds': {'ourAirports': oa}}
        proposed['airports'].append(record); sites[sid] = record; new_ids.append(airport_id)
        used_sources.update(primary); used_sources.update(coordinate_sources)
        dossiers.append({'recordId': airport_id, 'recordType': 'physicalAirport', 'siteKey': sid, 'decision': 'pending', 'reviewer': None,
                         'observations': observations(fs, loaded), 'identityAssessment': site['identityAssessment'],
                         'approvalBlockers': [] if site.get('coordinateFactId') else ['Primary physical reference-point evidence is missing; reference coordinates cannot satisfy the existing admission gate.']})
    for a in assessment['assignments']:
        check_binding(a,facts)
        airport_id = sites[a['siteKey']]['airportId']
        if any(x['scheme'] == a['scheme'] and x['code'] == a['code'] and x['airportId'] == airport_id for x in base['assignments']):
            raise ValueError('Already published physical/code fact; do not duplicate or extend frozen history')
        fs = [facts[f] for f in a['factIds']]
        source_ids = sorted({f['sourceId'] for f in fs})
        used_sources.update(source_ids)
        record = {k: a[k] for k in ('assignmentId', 'scheme', 'code', 'validFrom', 'validTo', 'evidenceType')}
        record.update(airportId=airport_id, sourceIds=source_ids, verificationStatus='pending', verifiedOn=None,
                      note=a['boundaryAssessment'] + ' ' + a['continuityAssessment'])
        proposed['assignments'].append(record); new_ids.append(a['assignmentId'])
        dossiers.append({'recordId': a['assignmentId'], 'recordType': 'assignment', 'siteKey': a['siteKey'],
                         'decision': 'pending', 'reviewer': None, 'observations': observations(fs, loaded),
                         'boundaryAssessment': a['boundaryAssessment'], 'continuityAssessment': a['continuityAssessment'],
                         'approvalBlockers': a.get('approvalBlockers', [])})
    old_sids = {s['sourceId'] for s in base['sources']}
    for sid in sorted(used_sources - old_sids):
        if sid == 'global-ourairports-reference':
            source = next(s for s in base['sources'] if s['sourceId']=='ourairports-20261025')
            proposed['sources'].append({**source,'sourceId':sid,'verificationStatus':'pending',
                'note':'Additional reference rows from the same pinned OurAirports publication, reused through the committed reference projection. Not primary historical identity or code evidence; not independent corroboration.'})
            continue
        s = loaded[sid][0]
        proposed['sources'].append({'sourceId': sid, 'title': s['title'], 'url': s['url'], 'accessedOn': s['accessedAt'][:10],
                                    'verificationStatus': 'pending', 'sourceType': 'primary', 'license': s['license'],
                                    'note': 'Original SHA-256 ' + s['originalSha256'] + '; claim scope, dependencies and exact citations are in the global research dossier.'})
    cases = assessment['cases']
    selected = select(records, groups, cases, assessment['selectionLimit'])
    queue = []
    for group in selected:
        c = next((c for c in cases if c['eventGroupId'] == group['eventGroupId']), None)
        ref = records[group['physicalMatch']['referenceId']]
        fs = [facts[f] for f in c['factIds']] if c else []
        sids = sorted({f['sourceId'] for f in fs})
        queue.append({'eventGroupId': group['eventGroupId'], 'country': group['country'], 'airport': group['name'],
                      'codes': ref['identifiers'], 'expectedTypes': c['types'] if c else group['classifications'],
                      'eventDate': c['eventDate'] if c else None, 'candidateIds': group['candidateIds'],
                      'candidateSources': sorted({m['sourceId'] for m in group['members']}),
                      'formalAirportIds': [a['airportId'] for a in base['airports'] if a['externalIds'].get('ourAirports') == ref['sourceEntityId']],
                      'sourceIds': sids, 'acquisitionStatus': 'originals_acquired' if sids else 'not_acquired',
                      'additionalDatedFacts': [{'factId':f['factId'],'eventDate':f['eventDate']} for f in fs if f.get('eventDate')],
                      'researchStatus': c['status'] if c else 'screened_only',
                      'blockers': c['gaps'] if c else ['No claim-specific primary investigation has been performed.'],
                      'nextEvidence': c['nextEvidence'] if c else 'Find original authority and code-specific historical observations; event year remains unknown.',
                      'decision': 'pending', 'reviewer': None})
    selected_groups = [groups[c['eventGroupId']] for c in cases if c.get('siteKeys')]
    batches = list(packets(selected_groups, CUTOFF, assessment['baseCommit']))
    ownership = []
    for n, batch in enumerate(batches, 1):
        batch['batchId'] = 'global-evidence-proposal-' + str(n)
        all_sids = set()
        for event in batch['events']:
            c = next(c for c in cases if c['eventGroupId'] == event['eventGroupId'])
            fs = [facts[f] for f in c['factIds']]
            sids = sorted({f['sourceId'] for f in fs}); all_sids.update(sids)
            ids = [sites[k]['airportId'] for k in c['siteKeys'] if sites[k]['airportId'] in new_ids]
            ids += [a['assignmentId'] for a in assessment['assignments'] if a['siteKey'] in c['siteKeys']]
            event.update(sourceIds=sids, proposedRecordIds=ids, evidenceFactIds=c['factIds'],
                         claims={key: {'conclusion': c['claimFindings'][key], 'evidenceType': 'continuity_inference' if key in ('iata','icao','historicalBoundary') else 'indirect', 'sourceIds': sids} for key in event['claims']},
                         evidenceGaps=['Explicit human approval is missing.', *c['gaps']],
                         conflicts=['Source dependence, temporal limits and counterevidence remain in each factual assessment.'],
                         nextAction=c['nextEvidence'])
            ownership.extend(ids)
        batch['sources'] = [{'sourceId': sid, 'url': loaded[sid][0]['url'], 'sourceType': 'primary', 'accessedOn': CUTOFF,
                             'supportedFacts': ['Only the exact scoped facts cited in assessments.json.'],
                             'limitations': ['Publication, document effectiveness, physical events and allocation boundaries are independent.', loaded[sid][0]['independence']],
                             'accessResult': 'Original bytes and extraction hash-verified offline; actual acquisition timestamp remains in source-lock.json.',
                             'license': loaded[sid][0]['license']} for sid in sorted(all_sids)]
    validate_batch_series(batches)
    if len(ownership) != len(set(ownership)) or set(ownership) != set(new_ids):
        raise ValueError('Every proposed record needs exactly one real candidate owner')
    try:
        validate_admission(base, proposed, batches, dossiers)
    except ValueError as error:
        if 'explicit claim review' not in str(error):
            raise
    else:
        raise ValueError('Pending research passed the human admission gate')
    write(output / 'proposed-data.json', proposed)
    write(output / 'facts.json', list(facts.values()))
    write(output / 'dossier.json', dossiers)
    write_jsonl(output / 'queue.jsonl.gz', queue)
    write_jsonl(output / 'review-packets.jsonl.gz', batches)
    for batch in batches:
        write(output / 'batches' / (batch['batchId'] + '.json'), batch)
    write(output / 'coverage-by-country-year.json', coverage_table(queue, cases, assessment['assignments'],facts))
    write(output / 'metrics.json', {'screenedEvents': len(queue), 'investigatedEvents': len(cases),
          'investigatedCountries': sorted({c['country'] for c in cases}), 'queueCountries': sorted({q['country'] for q in queue}),
          'datedClaimYears': sorted({int(c['eventDate']['earliest'][:4]) for c in cases if c['eventDate']} | {int(f['eventDate']['earliest'][:4]) for f in facts.values() if f.get('eventDate')}),
          'originalPublications': len({s['originalPublicationKey'] for s,t in loaded.values() if s.get('contentStatus','original') == 'original'}),
          'acquiredComponents': sum(s.get('contentStatus','original') == 'original' for s,t in loaded.values()),
          'rejectedResponses': sum(s.get('contentStatus','original') != 'original' for s,t in loaded.values()),
          'citedOriginalPublications': len({loaded[f['sourceId']][0]['originalPublicationKey'] for f in facts.values()}),
          'factAssessedEvents': sum(c['status'] in ('facts_assessed','proposal_pending') for c in cases),
          'recommendedScopedProposalEvents': sum(c.get('recommendApproval',False) for c in cases),
          'judgedFacts': len(facts), 'proposedPhysicalAirports': len(proposed['airports'])-len(base['airports']),
          'proposedIntervals': dict(Counter(a['scheme'] for a in assessment['assignments'])),
          'intervalCertaintyPolicies':dict(Counter(a['certaintyPolicy'] for a in assessment['assignments'])),
          'proposalEvents': len(selected_groups), 'batches': len(batches), 'humanApproved': 0, 'formalAdmissions': 0,
          'exactExecutedEventDates': sum(c['eventDate'] is not None and c['eventDate']['precision']=='exact' and c['eventDate']['basis']=='executed' for c in cases),
          'observationOnlyProposalEvents': sum(bool(c.get('siteKeys')) and (not c['eventDate'] or c['eventDate']['basis']!='executed') for c in cases)})
    review_documents(output,assessment,facts,loaded,proposed,base)
    inputs = ['test/curated-0.8.0.json','research/evidence/global/assessments.json','research/evidence/global/catalog.json',
              str((source_directory/'source-lock.json').relative_to(ROOT)),'reference/triage/groups.jsonl.gz',
              'research/discovery/generated/verification-queue.jsonl.gz','scripts/evidence/global_batch.py',
              'scripts/evidence/global_coverage.ts','research/evidence/direct/assessments.json']
    inputs += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'reference/generated').glob('records.*.jsonl.gz'))]
    inputs += ['scripts/reference/admissions.py','scripts/discovery/review.py','scripts/reference/common.py',
               'src/resolve.ts','src/time.ts','src/evidence.ts','src/validate.ts','schema/dataset.schema.json']
    write(output / 'manifest.json', {'formalBaselineSha256': sha(base_raw), 'baseCommit': assessment['baseCommit'],
          'inputs': {p:digest(ROOT/p) for p in inputs},
          'outputs': {str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name not in ('manifest.json','query-coverage.json')},
          'sourceDirectory': str(source_directory.relative_to(ROOT))})


def observations(fs, loaded):
    return [{'sourceId':f['sourceId'], 'observedOn': f['observedOn'], 'sourceFamily':loaded[f['sourceId']][0]['sourceFamily'],
             'independentOriginal':True, 'claimScope':f['supports'], 'basis':'Exact original citation ' + f['factId'],
             'factId':f['factId'], 'eventDate':f.get('eventDate'), 'notSupported':f['doesNotSupport']} for f in fs if f.get('observedOn') is not None]


def review_documents(output,assessment,facts,loaded,proposed,base):
    rows=['# 本轮集中待审核清单', '',
          '全部记录均为 pending，reviewer 为 null。本清单不是人工批准。建议仅针对列出的物理身份和代码观察区间；不代表整组迁场历史已完整核实。', '',
          '代码区间采用半开区间。下面的窗口是拟议的“确定覆盖”部分；首次分配与最终撤销的开放边界见 proposed-data.json。空窗口和未解冲突不得人工压缩。', '']
    for n,c in enumerate(assessment['cases'],1):
        rows.extend([f"## {n}. {c['country']} · {c.get('labelZh',c['caseKey'])}", '', f"事件组：`{c['eventGroupId']}`；研究状态：`{c['status']}`。", ''])
        if c.get('reviewSummaryZh'):
            rows.extend([c['reviewSummaryZh'],''])
        ed=c['eventDate']
        rows.append('事件时间：'+(f"{ed['earliest']} 至 {ed['latest']}（{ed['precision']}，{ed['basis']}）" if ed else '未知；不得使用候选发现年份代替。'))
        rows.extend(['', '建议：'+('可逐记录审核下列有限事实；不是批准整个事件或未知边界。' if c.get('recommendApproval') else '仍有下列证据缺口；保持 pending，补证后再决定。'), ''])
        keys=set(c['siteKeys']);site_map={s['siteKey']:s for s in assessment['sites']}
        for key in sorted(keys):
            site=site_map[key]
            actual=next(r for r in proposed['airports'] if r['externalIds'].get('ourAirports')==site['ourAirports'])
            rows.append(f"- 物理身份：{site['name']}，`{actual['airportId']}`。坐标状态仍为 reference。")
            for a in assessment['assignments']:
                if a['siteKey']==key:
                    start,end=a['validFrom']['latest'],a['validTo']['earliest']
                    window=f'[{start}, {end})' if start and end and start<end else '无确定的完整本地日；仅保留不确定边界/关联'
                    rows.append(f"- `{a['assignmentId']}`：{a['scheme']} `{a['code']}`；拟议确定窗口 `{window}`；{a['evidenceType']}。")
        rows.extend(['', '原件事实定位：', ''])
        for fid in c['factIds']:
            f=facts[fid];s=loaded[f['sourceId']][0];cit=f['citation'];where=('PDF 物理页 '+str(cit['page'])) if cit['page'] else 'HTML 规范化文本定位'
            rows.append(f"- `{fid}`：[{s['title']}]({s['url']})，{where}，字符 {cit['normalizedCharacterStart']}–{cit['normalizedCharacterEnd']}。{f['supports']}")
        if not c['factIds']:rows.append('- 未取得可用于该事件事实的原件；失败响应不充当证据。')
        rows.extend(['', '仍需决定/补证：', '', '- 对每条记录单独判断物理身份、命名空间、边界和连续性；实际人工批准尚缺。'])
        rows.extend('- '+gap for gap in c['gaps']);rows.append('')
    (output/'待审核清单.md').write_text('\n'.join(rows).rstrip()+'\n')
    index=['# Original publication archive', '',
           'Components with one originalPublicationKey count as one publication. AIP indices, reverse indices and AD pages from the same edition are not independent originals. Rejected HTTP responses are retained for audit and support no historical fact.', '',
           'Original SHA-256 provenance, retrieval timestamps, date distinctions and rights notes remain in source-lock.json. Protected full originals and full extractions are withheld from this branch tree. Minimal cited spans retain the original PDF page and normalized-text offsets and have their own offline-verified hashes. Re-fetch an original separately to verify its full SHA-256; excerpts cannot reconstruct the full publication.', '']
    for sid,(s,t) in sorted(loaded.items()):
        index.extend([f'## {sid}', '', f"[{s['title']}]({s['url']}) · {s['publisher']}", '',
                      f"Publication: `{s['originalPublicationKey']}`; content status: `{s.get('contentStatus','original')}`.", '',
                      f"Original provenance SHA-256: `{s['originalSha256']}`.", '',
                      f"Retained: `../{s.get('retainedPath',s['inputPath'])}`; retention: `{s.get('retention','full_original')}`; retrieved: `{s['accessedAt']}`.", '',
                      f"Published: `{s.get('publicationDate')}`; document effective: `{s.get('documentEffectiveDate')}`. These are not airport event/allocation dates.", '',
                      s['license']['note'], ''])
    (output/'evidence-index.md').write_text('\n'.join(index).rstrip()+'\n')


def coverage_table(queue, cases, assignments, facts):
    rows = []
    for country in sorted({q['country'] for q in queue}):
        for year in [*range(2015,2027),None]:
            qs = [q for q in queue if q['country']==country and (int(q['eventDate']['earliest'][:4]) if q['eventDate'] else None)==year]
            cs = [c for c in cases if c['country']==country and (int(c['eventDate']['earliest'][:4]) if c['eventDate'] else None)==year]
            rows.append({'country':country,'year':year,'discovered':len(qs),'originalEvidenceEvents':sum(bool(q['sourceIds']) for q in qs),
                         'factJudgedEvents':sum(c['status'] in ('facts_assessed','proposal_pending') for c in cs),
                         'recommendedForHumanApproval':sum(c.get('recommendApproval',False) for c in cs),
                         'humanApproved':0,'formallyAdmitted':0,'blockedOrMissingEvidence':sum(bool(q['blockers']) for q in qs),
                         'eventTypes':dict(Counter(t for c in cs for t in c['types'])),
                         'namespaces':dict(Counter(a['scheme'] for c in cs for a in assignments if a['siteKey'] in c.get('siteKeys',[]))),
                         'scope':'Selected research queue only; zero is not evidence of no historical change.'})
    dated_facts=[]
    for c in cases:
        for fid in c['factIds']:
            f=facts[fid]
            if f.get('eventDate'):
                dated_facts.append({'country':c['country'],'caseKey':c['caseKey'],'factId':fid,
                                    'eventDate':f['eventDate'],'namespaces':sorted({b['scheme'] for b in f['codeBindings']}),
                                    'humanApproved':0,'formallyAdmitted':0})
    return {'period':['2015-01-01',CUTOFF],'uncollectedCountries':'not_assessed, never no_changes',
            'unknownYearPolicy':'Candidate revision/discovery dates are never event years. Null is retained.',
            'datedFactClaims':dated_facts,
            'dateScope':'Rows count main case events. datedFactClaims separately retains additional administrative/physical phases (for example Ramon ICAO approval in 2016 versus civil replacement in 2019). Do not add those two units together.',
            'rows':rows}


def validate(output=OUT):
    manifest = json.loads((output / 'manifest.json').read_text())
    for p,h in manifest['inputs'].items():
        if digest(ROOT/p) != h:
            raise ValueError('Research input changed: ' + p)
    for p,h in manifest['outputs'].items():
        if digest(output/p) != h:
            raise ValueError('Research output changed: ' + p)
    assessment = json.loads((BASE/'assessments.json').read_text())
    proposed = json.loads((output/'proposed-data.json').read_text())
    base = json.loads((ROOT/'test/curated-0.8.0.json').read_text())
    dossiers = json.loads((output/'dossier.json').read_text())
    loaded = {s['sourceId']:(s,t) for s,t in locked(ROOT/manifest['sourceDirectory'])}
    for f in json.loads((output/'facts.json').read_text()):
        if f['citation'] != citation(f,loaded):
            raise ValueError('Unreproducible citation')
    # Independent extraction from originals, rather than trusting both a stored
    # extraction and its lock. Compare cited text/pages, not Poppler whitespace.
    fresh = {}
    for f in assessment['facts']:
        sid = f['sourceId']
        s,_ = loaded[sid]
        if s.get('retention') == 'metadata_and_cited_excerpts':
            # Full independent extraction requires a separately recovered original.
            continue
        if sid not in fresh:
            raw = gzip.decompress((ROOT/manifest['sourceDirectory']/s['inputPath']).read_bytes())
            fresh[sid] = (s,extract(raw,s.get('encoding','utf-8')))
        if citation(f,fresh)['page'] != citation(f,loaded)['page']:
            raise ValueError('Citation page differs in independent extraction')
    for collection, field in [('airports','airportId'),('assignments','assignmentId'),('sources','sourceId'),('names','nameId')]:
        old = {r[field]:r for r in base[collection]}; new = {r[field]:r for r in proposed[collection]}
        if len(new)!=len(proposed[collection]) or any(new.get(k)!=v for k,v in old.items()):
            raise ValueError('Changed permanent record or duplicate identity')
        if collection in ('assignments','sources') and any(new[k]['verificationStatus']!='pending' for k in new.keys()-old.keys()):
            raise ValueError('Research impersonates verified history')
    if any(d['decision']!='pending' or d['reviewer'] is not None for d in dossiers):
        raise ValueError('Research impersonates human approval')
    batches = list(read_jsonl(output/'review-packets.jsonl.gz'))
    # Include the actual earlier review owners; a new research series cannot
    # silently duplicate a completed or still-blocked older candidate mapping.
    earlier = [json.loads(p.read_text()) for p in sorted((ROOT/'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*earlier,*batches])
    try:
        validate_admission(base,proposed,batches,dossiers)
    except ValueError as e:
        if 'explicit claim review' not in str(e):
            raise
    else:
        raise ValueError('Unauthorized proposal passed admission')
    report = json.loads((output/'query-coverage.json').read_text())
    if report['formalNewResolvedQueries'] or report['changedPublishedResolvedQueries'] or report['changedPendingResolvedQueries']:
        raise ValueError('Published query history changed')
    print('Validated global originals, citations, current-baseline deduplication, pending records and unchanged admission rejection.')


def build(output=OUT, source_directory=BASE):
    prepare(output,source_directory)
    subprocess.run(['node','scripts/evidence/global_coverage.ts',str(output)],cwd=ROOT,check=True)
    manifest = json.loads((output/'manifest.json').read_text())
    manifest['outputs']['query-coverage.json'] = digest(output/'query-coverage.json')
    write(output/'manifest.json',manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'verify', 'build', 'validate'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--sources', type=Path, default=BASE)
    parser.add_argument('--source', action='append')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--retry-failures', action='store_true')
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    if args.command == 'fetch':
        fetch(args.output or BASE, args.source, args.limit, args.retry_failures, args.recover)
    elif args.command == 'verify':
        print('Verified', sum(1 for _ in locked(args.output or BASE)), 'retained records and original hash provenance; full protected originals require separate recovery')
    elif args.command == 'build':
        build(args.output or OUT,args.sources)
    else:
        validate(args.output or OUT)
