"""Hash-locked primary-publication observations and conservative candidate joins.

This layer prepares evidence for humans. It cannot admit historical facts.
Only PR #11 reference/triage outputs are read; source-transition history is not rescanned.
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import html
import io
import json
import re
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reference'))
from common import ROOT, OUTPUT, canonical, checked, digest, distance, position, read_jsonl, research_baseline_path, stable_id, write_json, write_jsonl
from admissions import packets
from review import CLAIMS, validate_batch_series

BASE = ROOT / 'research/evidence'
OUT = BASE / 'generated'
TRIAGE = ROOT / 'reference/triage'
LIMITATIONS = [
    'A publication observation is not an allocation ledger or proof of continuous validity.',
    'Publication, regulatory effectiveness, statistical attribute dates and physical event dates are distinct.',
    'Independent issuing authority does not establish independence of every underlying fact; lineage needs review.',
]


def normalized(value):
    return ' '.join(re.findall(r'[^\W_]+', (value or '').casefold(), re.UNICODE))


def tokens(value):
    return set(normalized(value).split()) - {'airport', 'international', 'regional', 'municipal', 'the', 'of', 'field', 'air', 'aerodrome', 'heliport', 'airstrip', 'airfield'}


def name_score(a, b):
    a, b = tokens(a), tokens(b)
    return len(a & b) / max(1, len(a | b))


def bts_date(value):
    return dt.datetime.strptime(value, '%m/%d/%Y %I:%M:%S %p').date().isoformat() if value else None


def base_observation(source, locator, name, country, coordinates, codes):
    return {
        'formatVersion': 1, 'sourceId': source['sourceId'], 'sourceFamily': source['sourceFamily'],
        'originalPublicationKey': source['originalPublicationKey'], 'locator': locator,
        'name': name, 'country': country, 'coordinates': coordinates, 'codes': codes,
        'publicationDate': source['publicationDate'], 'documentEffectiveDate': source['documentEffectiveDate'],
        'observedAt': source['accessedAt'], 'historicalObservationDate': None, 'eventDate': None,
        'attributeInterval': None, 'kind': 'publication_observation',
        'supports': [], 'doesNotEstablish': LIMITATIONS[:], 'qualityFlags': ['human_claim_review_required'],
        'historicallyVerified': False,
    }


def finish(observation):
    # Mirrors/retrieval timestamps cannot manufacture independent confirmations.
    observation['observationId'] = stable_id('obs_', [observation['originalPublicationKey'], observation['locator']])
    return observation


def parse_bts(source, raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    required = {'AIRPORT_SEQ_ID', 'AIRPORT_ID', 'AIRPORT', 'DISPLAY_AIRPORT_NAME', 'AIRPORT_COUNTRY_CODE_ISO',
                'LATITUDE', 'LONGITUDE', 'AIRPORT_START_DATE', 'AIRPORT_THRU_DATE', 'AIRPORT_IS_CLOSED'}
    if not required <= set(reader.fieldnames or []):
        raise ValueError('BTS field layout changed; inspect upstream before updating the parser')
    seen = set()
    for number, row in enumerate(reader, 2):
        seq = row['AIRPORT_SEQ_ID']
        if not seq.isdigit() or seq in seen:
            raise ValueError('Missing or duplicate BTS AirportSeqID')
        seen.add(seq)
        o = base_observation(source, f'T_MASTER_CORD.csv:record={number};AirportSeqID={seq}',
                             row['DISPLAY_AIRPORT_NAME'], row['AIRPORT_COUNTRY_CODE_ISO'] or None,
                             position(row['LATITUDE'], row['LONGITUDE']),
                             [{'scheme': 'USDOT', 'code': row['AIRPORT']}])
        o.update(kind='statistical_attribute', authorityRecordId=seq, authorityAirportId=row['AIRPORT_ID'],
                 attributeInterval={'from': bts_date(row['AIRPORT_START_DATE']), 'through': bts_date(row['AIRPORT_THRU_DATE']),
                                    'semantics': 'BTS statistical attribute interval; not physical-event or IATA allocation boundaries'},
                 reportedClosed=row['AIRPORT_IS_CLOSED'] == '1',
                 supports=['BTS associates the named airport, USDOT code and coordinates with this statistical attribute interval.'],
                 qualityFlags=['human_claim_review_required', 'namespace_usdot_not_iata', 'statistical_dates_not_event_dates'])
        o['doesNotEstablish'] += ['USDOT codes must not be silently promoted to IATA.',
                                 'AIRPORT_ID can span a relocation; it is not a permanent physical-site identity.',
                                 'UTC_LOCAL_TIME_VARIATION is an offset, not an IANA timezone or historical timezone rule.']
        if o['coordinates'] is None:
            o['qualityFlags'].append('missing_or_invalid_coordinates')
        yield finish(o)


def plain_text(raw):
    match = re.search(r'<pre\b[^>]*>(.*?)</pre>', raw.decode('utf-8'), re.I | re.S)
    if not match:
        raise ValueError('Expected a GovInfo Federal Register PRE original')
    return html.unescape(re.sub(r'<[^>]+>', '', match[1]))


DMS = re.compile(r'lat\.?\s*(\d+)\[deg\](\d+)\s*[\x27\u2032](\d+(?:\.\d+)?)\s*[\x27\u2032\u2033]+\s*([NS])\.?\s*,?\s*long\.?\s*(\d+)\[deg\](\d+)\s*[\x27\u2032](\d+(?:\.\d+)?)\s*[\x27\u2032\u2033]+\s*([EW])', re.I)


def dms_coordinates(match):
    d, m, s, ns, e, n, t, ew = match.groups()
    if max(float(m), float(n), float(s), float(t)) >= 60:
        return None
    return position((float(d) + float(m)/60 + float(s)/3600) * (-1 if ns.upper() == 'S' else 1),
                    (float(e) + float(n)/60 + float(t)/3600) * (-1 if ew.upper() == 'W' else 1))


def parse_faa(source, raw, names):
    text = plain_text(raw)
    document_normalized = ' ' + normalized(text) + ' '
    name_keys = [(name, ' ' + normalized(name) + ' ') for name in names]
    name_keys = [(name, key) for name, key in name_keys if key in document_normalized]
    # Bind coordinates only when the name immediately precedes the coordinate block.
    # Other names in the same document do not inherit the principal airport's position.
    paragraphs = list(re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', text))
    found = False
    for paragraph in paragraphs:
        prose = ' '.join(paragraph.group().split())
        norm = ' ' + normalized(prose) + ' '
        hits = [name for name, key in name_keys if key in norm]
        hits.sort(key=lambda n: (-len(n), n))
        kept = []
        for name in hits:
            if any(normalized(name) in normalized(other) for other in kept):
                continue
            kept.append(name)
        for name in kept:
            # A reference-name match is a retrieval clue, not proof of identity or official name.
            coordinate = None
            adjacent = re.search(re.escape(name) + r',?\s*(?:[A-Z]{2})?\s*\n\s*\(?(Lat\.[\s\S]{0,160})', paragraph.group(), re.I)
            if adjacent and (match := DMS.search(adjacent[1])):
                coordinate = dms_coordinates(match)
            flags = ['human_claim_review_required', 'no_code_namespace_asserted', 'name_mention_not_identity_confirmation']
            o = base_observation(source, f'pre:chars={paragraph.start()}:{paragraph.end()};name={name}',
                                 name, 'US', coordinate, [])
            o.update(kind='official_name_mention', excerpt=prose,
                     supports=['The FAA publication explicitly mentions this name in the cited paragraph.'], qualityFlags=flags)
            # Extract an assertion only when this named subject, rather than a nearby airport,
            # is explicitly said to have closed. Preserve the exact context for human review.
            closure = re.search(re.escape(name) + r',?\s+(?:(?:which|that)\s+)?(?:was\s+|is\s+|has\s+been\s+)?(?:now\s+)?(?:permanently\s+)?closed\b(?:\s+in\s+(\d{4}))?', prose, re.I)
            if closure and re.search(r'\b(?:if|once|would|could|should)\b', prose[:closure.start()].rsplit('.', 1)[-1], re.I):
                closure = None
            if closure:
                o['kind'] = 'closure_statement'
                o['supports'] = ['The FAA explicitly describes this named facility as closed; see the original paragraph.']
                year = closure[1]
                o['reportedEventBounds'] = {'earliest': f'{year}-01-01' if year else None,
                                            'latest': f'{year}-12-31' if year else source['publicationDate'],
                                            'precision': 'year' if year else 'unknown'}
                o['doesNotEstablish'].append('The rule effective date is not the airport closure date.')
            elif coordinate:
                o['kind'] = 'regulatory_location_observation'
                o['supports'].append('The adjacent regulatory location block gives these coordinates for this name.')
            if re.search(r'(?:updat|correct|reflect).{0,140}(?:coordinates|database)|coordinates.{0,140}(?:updat|correct|database)', prose, re.I):
                o['qualityFlags'].append('directory_update_context_not_relocation')
            found = True
            yield finish(o)
    if not found:
        # A publication with no recognized airport is retained, not silently dropped.
        o = base_observation(source, 'pre:unparsed-document', source['title'], 'US', None, [])
        o.update(kind='unparsed_document', supports=['Official publication retrieved; no indexed airport name parsed.'],
                 qualityFlags=['parser_review_required'])
        yield finish(o)


def load_locked(directory=BASE, providers=('bts-master', 'faa-fr')):
    lock = json.loads((directory / 'source-lock.json').read_text())
    sources = lock['sources']
    if len({s['sourceId'] for s in sources}) != len(sources):
        raise ValueError('Duplicate source ID')
    for source in sources:
        raw_path = directory / source['inputPath']
        if not raw_path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Evidence input escapes its locked directory')
        checked(raw_path, source['inputSha256'])
        raw = gzip.decompress(raw_path.read_bytes())
        if hashlib.sha256(raw).hexdigest() != source['originalSha256']:
            raise ValueError('Changed uncompressed original')
        if source['version'] != 'sha256:' + source['originalSha256']:
            raise ValueError('Source version must bind the actual original')
        if source['sourceType'] != 'primary' or not source['publisher'] or not source['license']['id']:
            raise ValueError('Missing primary publication provenance')
        if dt.datetime.fromisoformat(source['accessedAt']).tzinfo is None:
            raise ValueError('Source access timestamp needs a timezone')
        if not all(source[key].startswith('https://') for key in ['url', 'retrievalUrl']):
            raise ValueError('Missing concrete HTTPS publication URL')
        if source['provider'] not in providers:
            raise ValueError('Unknown primary provider')
        yield source, raw


def load_reference():
    lock = json.loads((OUTPUT / 'manifest.json').read_text())
    records = {}
    for shard in '0123456789abcdef':
        filename = f'records.{shard}.jsonl.gz'
        checked(OUTPUT / filename, lock['files'][filename]['sha256'])
        for r in read_jsonl(OUTPUT / filename):
            # Match only the compact identity clues; do not retain repeated transition
            # provenance already locked in PR #11's shards (over 1 GiB when expanded).
            records[r['referenceId']] = {
                'referenceId': r['referenceId'], 'country': r['country'], 'name': r['name'],
                'identifiers': r['identifiers'], 'locations': [{'coordinates': p['coordinates']} for p in r['locations']],
                'historicalNames': [{'name': n} for n in sorted({h['name'] for h in r['historicalNames'] if h['name']})],
                'historicalIdentifiers': [{'scheme': scheme, 'code': code} for scheme, code in sorted(
                    {(h['scheme'], h['code']) for h in r['historicalIdentifiers']})],
            }
    return records


def candidate_index(records):
    lock = json.loads((TRIAGE / 'manifest.json').read_text())
    for name in ['groups.jsonl.gz', 'code-reuse-leads.jsonl.gz']:
        checked(TRIAGE / name, lock['files'][name]['sha256'])
    groups = {g['eventGroupId']: g for g in read_jsonl(TRIAGE / 'groups.jsonl.gz')}
    by_reference, by_name, by_code = defaultdict(set), defaultdict(set), defaultdict(set)
    priority = {rid for lead in read_jsonl(TRIAGE / 'code-reuse-leads.jsonl.gz') for rid in lead['referenceIds']}
    for gid, g in groups.items():
        rid = g['physicalMatch']['referenceId']
        by_reference[rid].add(gid)
        by_name[normalized(g['name'])].add(gid)
        r = records.get(rid)
        if r:
            for scheme in ['IATA', 'ICAO']:
                if r['identifiers'][scheme]:
                    by_code[(scheme, r['identifiers'][scheme])].add(gid)
            for h in r['historicalIdentifiers']:
                by_code[(h['scheme'], h['code'])].add(gid)
    return groups, by_reference, by_name, by_code, priority


def match_observation(o, index, records):
    groups, by_reference, by_name, by_code, priority = index
    # USDOT is a lexical clue across namespaces, never an IATA assertion.
    candidates = set(by_name.get(normalized(o['name']), set()))
    for code in o['codes']:
        schemes = ['IATA'] if code['scheme'] == 'USDOT' else [code['scheme']]
        for scheme in schemes:
            candidates.update(by_code.get((scheme, code['code']), set()))
    # FR may mention a historical alias no longer used in group labels.
    for rid in o.get('referenceHints', []):
        candidates.update(by_reference.get(rid, set()))
    links = []
    for gid in sorted(candidates):
        g = groups[gid]
        r = records.get(g['physicalMatch']['referenceId'])
        country = r['country'] if r else g['country']
        flags = set(o['qualityFlags'])
        if country and o['country'] and country != o['country']:
            status, confidence = 'conflict', 'low'
            flags.add('country_conflict')
            nearest = None
        else:
            distances = [distance(o['coordinates'], loc['coordinates']) for loc in r['locations']] if r else []
            distances = [x for x in distances if x is not None]
            nearest = min(distances) if distances else None
            names = [g['name'], *([r['name']] + [h['name'] for h in r['historicalNames']] if r else [])]
            similarity = max(name_score(o['name'], name) for name in names)
            if nearest is not None and nearest > 5:
                status, confidence = 'conflict', 'low'
                flags.add('physical_location_conflict_or_missing_historical_site')
            elif nearest is not None and nearest <= 2 and similarity >= .3 and country == o['country']:
                status, confidence = 'supported_observation', 'high'
            else:
                status, confidence = 'ambiguous', 'low'
                flags.add('physical_identity_ambiguous')
            if r and len(r['locations']) > 1:
                flags.add('multiple_reference_location_hypotheses')
        if o['eventDate'] is None:
            flags.add('event_date_not_established')
        if o['kind'] == 'statistical_attribute':
            flags.add('attribute_interval_cannot_date_candidate_transition')
        links.append({'observationId': o['observationId'], 'eventGroupId': gid, 'sourceId': o['sourceId'],
                      'referenceId': g['physicalMatch']['referenceId'], 'status': status, 'confidence': confidence,
                      'distanceKm': round(nearest, 3) if nearest is not None else None,
                      'priorityCodeReuseLead': g['physicalMatch']['referenceId'] in priority,
                      'flags': sorted(flags), 'historicallyVerified': False,
                      'directoryCorrection': 'context_only' if 'directory_update_context_not_relocation' in flags else 'not_adjudicated'})
    return links


def evidence_sources(source_ids, sources, reviewed_on):
    return [{
        'sourceId': sid, 'url': sources[sid]['url'], 'sourceType': 'primary', 'accessedOn': reviewed_on,
        'supportedFacts': sources[sid]['supports'], 'limitations': sources[sid]['limitations'],
        'accessResult': 'Hash-checked original retrieval; source access timestamp is in source-lock.json. Packet generation is not human source review.',
        'license': sources[sid]['license'],
        'originalPublication': {key: sources[sid][key] for key in ['publisher', 'title', 'version', 'sourceFamily',
            'publicationDate', 'documentEffectiveDate', 'originalSha256', 'accessedAt', 'independence']},
    } for sid in sorted(source_ids)]


def review_packets(groups, links, observations, sources, reviewed_on, base_commit):
    by_group = defaultdict(list)
    for link in links:
        by_group[link['eventGroupId']].append(link)
    selected = [groups[gid] for gid in sorted(by_group) if groups[gid]['status'] != 'existing_review']
    for b in packets(selected, reviewed_on, base_commit):
        b['batchId'] = b['batchId'].replace('bulk-proposal', 'primary-evidence-proposal')
        sids = set()
        for event in b['events']:
            attached = by_group[event['eventGroupId']]
            ids = sorted({a['observationId'] for a in attached})
            event['sourceIds'] = sorted({observations[oid]['sourceId'] for oid in ids})
            sids.update(event['sourceIds'])
            event['evidenceObservationIds'] = ids
            event['evidenceSummary'] = [{'observationId': oid, 'locator': observations[oid]['locator'],
                                         **{key: observations[oid].get(key) for key in ['sourceId', 'name', 'codes', 'coordinates',
                                             'kind', 'attributeInterval', 'reportedEventBounds', 'curatedBoundaryWarnings']},
                                         'supports': observations[oid]['supports'],
                                         'doesNotEstablish': observations[oid]['doesNotEstablish']} for oid in ids]
            for key in CLAIMS:
                event['claims'][key] = {'conclusion': 'Pending human claim assessment; attached primary observations do not establish this whole claim.',
                                        'evidenceType': 'indirect', 'sourceIds': event['sourceIds']}
            event['conflicts'] = sorted({flag for a in attached for flag in a['flags']})
            event['nextAction'] = 'Inspect cited originals; adjudicate namespace, site identity, corrections and date bounds. No reviewer or acceptance has been recorded.'
        b['sources'] = evidence_sources(sids, sources, reviewed_on)
        validate_batch_series([b])
        yield b


def build(output=OUT):
    started = time.perf_counter()
    records = load_reference()
    index = candidate_index(records)
    us_names = defaultdict(set)
    for rid, r in records.items():
        if r['country'] == 'US':
            for name in [r['name'], *[h['name'] for h in r['historicalNames']]]:
                if len(tokens(name)) and len(normalized(name)) >= 7:
                    us_names[name].add(rid)
    sources, observations, duplicates = {}, {}, 0
    curated = json.loads(research_baseline_path().read_text())
    airports = {a['airportId']: a for a in curated['airports']}
    def compare_curated(o):
        if o['kind'] != 'statistical_attribute' or o['coordinates'] is None:
            return
        earlier = []
        for a in curated['assignments']:
            point = airports[a['airportId']]['coordinates']['value']
            bound = a['validFrom']['earliest']
            if (a['scheme'] == 'IATA' and o['codes'][0]['code'] == a['code'] and bound
                    and o['attributeInterval']['from'] and o['attributeInterval']['from'] < bound
                    and point and (distance(o['coordinates'], point) or 0) <= 2):
                earlier.append({'assignmentId': a['assignmentId'], 'statisticalFrom': o['attributeInterval']['from'],
                                'curatedFromEarliest': bound,
                                'meaning': 'Statistical attribute start precedes reviewed site interval. Different claims/namespaces; do not replace historical boundary.'})
        if earlier:
            o['curatedBoundaryWarnings'] = earlier
            o['qualityFlags'].append('statistical_start_precedes_curated_site_interval')
    for source, raw in load_locked():
        sources[source['sourceId']] = source
        parsed = parse_bts(source, raw) if source['provider'] == 'bts-master' else parse_faa(source, raw, us_names)
        for o in parsed:
            compare_curated(o)
            if source['provider'] == 'faa-fr':
                o['referenceHints'] = sorted(us_names.get(o['name'], []))
            oid = o['observationId']
            if oid in observations:
                duplicates += 1
                continue
            observations[oid] = o
    links, unmatched = [], []
    for oid in sorted(observations):
        o = observations[oid]
        matched = match_observation(o, index, records)
        links.extend(matched)
        if not matched:
            unmatched.append({'observationId': oid, 'reason': 'No indexed name or code candidate; retained for parser/identity review.', 'historicallyVerified': False})
    groups = index[0]
    write_jsonl(output / 'observations.jsonl.gz', [observations[k] for k in sorted(observations)])
    write_jsonl(output / 'matches.jsonl.gz', links)
    write_jsonl(output / 'unmatched.jsonl.gz', unmatched)
    lock = json.loads((BASE / 'source-lock.json').read_text())
    batches = list(review_packets(groups, links, observations, sources, lock['preparedOn'], lock['baseCommit']))
    existing = [json.loads(p.read_text()) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing, *batches])
    # Single compressed series avoids generating another thousands-of-files packet tree.
    write_jsonl(output / 'review-packets.jsonl.gz', batches)
    owned = {gid for gid in {a['eventGroupId'] for a in links} if groups[gid]['status'] == 'existing_review'}
    write_jsonl(output / 'existing-review-attachments.jsonl.gz', [
        {'eventGroupId': gid, 'observationIds': sorted({a['observationId'] for a in links if a['eventGroupId'] == gid}),
         'status': 'attachment_only', 'nextAction': 'Use existing follow-up ownership; this attachment does not alter its disposition.'} for gid in sorted(owned)])
    metrics = {'sources': len(sources), 'originalPublications': len({s['originalPublicationKey'] for s in sources.values()}),
               'sourceFamilies': sorted({s['sourceFamily'] for s in sources.values()}),
               'observations': len(observations), 'observationKinds': dict(Counter(o['kind'] for o in observations.values())),
               'sameOriginalDuplicatesRemoved': duplicates, 'matchedObservations': len(observations) - len(unmatched),
               'unmatchedObservations': len(unmatched), 'candidateLinks': len(links),
               'matchedCandidateGroups': len({a['eventGroupId'] for a in links}),
               'associationConflictGroups': len({a['eventGroupId'] for a in links if a['status'] == 'conflict'}),
               'identityAmbiguityGroups': len({a['eventGroupId'] for a in links if a['status'] == 'ambiguous'}),
               'priorityGroups': len({a['eventGroupId'] for a in links if a['priorityCodeReuseLead']}),
               'priorityCodeLeadsWithAttachments': sum(bool(set(lead['referenceIds']) & {a['referenceId'] for a in links})
                    for lead in read_jsonl(TRIAGE / 'code-reuse-leads.jsonl.gz')),
               'curatedBoundaryWarningObservations': sum('curatedBoundaryWarnings' in o for o in observations.values()),
               'directoryCorrectionContextGroups': len({a['eventGroupId'] for a in links if a['directoryCorrection'] == 'context_only'}),
               'adjudicatedDirectoryCorrections': 0, 'confirmedHistoricalCodeConflicts': 0, 'pendingReviewGroups': sum(len(b['events']) for b in batches),
               'reviewPackets': len(batches), 'existingReviewAttachments': len(owned),
               'newVerifiedHistoricalAdmissions': 0, 'eventDatesInferredFromDirectoryCommits': 0}
    write_json(output / 'metrics.json', metrics)
    inputs = [BASE / 'source-lock.json', *(BASE / s['inputPath'] for s in sources.values()),
              OUTPUT / 'manifest.json', TRIAGE / 'manifest.json', TRIAGE / 'groups.jsonl.gz', TRIAGE / 'code-reuse-leads.jsonl.gz',
              ROOT / 'scripts/evidence/pipeline.py', ROOT / 'scripts/reference/admissions.py', ROOT / 'scripts/discovery/review.py',
              research_baseline_path(),
              *sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    write_json(output / 'manifest.json', {'formatVersion': 1, 'evidenceStatus': 'pending_human_claim_review',
               'inputs': {str(p.relative_to(ROOT)): digest(p) for p in sorted(inputs)},
               'files': {name: {'sha256': digest(output / name), 'bytes': (output / name).stat().st_size}
                         for name in ['observations.jsonl.gz', 'matches.jsonl.gz', 'unmatched.jsonl.gz', 'review-packets.jsonl.gz', 'existing-review-attachments.jsonl.gz', 'metrics.json']}})
    elapsed = time.perf_counter() - started
    print(canonical({'metrics': metrics, 'elapsedSeconds': round(elapsed, 3), 'observationsPerSecond': round(len(observations) / elapsed, 2),
                     'peakRssMiB': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)}))
    return metrics


def validate(output=OUT):
    lock = json.loads((output / 'manifest.json').read_text())
    for path, sha in lock['inputs'].items():
        checked(ROOT / path, sha)
    for name, entry in lock['files'].items():
        checked(output / name, entry['sha256'])
    sources = {s['sourceId']: s for s, _ in load_locked()}
    obs = {o['observationId']: o for o in read_jsonl(output / 'observations.jsonl.gz')}
    if len(obs) != json.loads((output / 'metrics.json').read_text())['observations']:
        raise ValueError('Duplicate or missing observations')
    for o in obs.values():
        source = sources[o['sourceId']]
        if o['historicallyVerified'] is not False or o['eventDate'] is not None or not o['supports'] or not o['doesNotEstablish']:
            raise ValueError('Observation promoted or missing claim limits')
        if finish({k: v for k, v in o.items() if k != 'observationId'})['observationId'] != o['observationId']:
            raise ValueError('Observation identity mismatch')
        if (any(o[key] != source[key] for key in ['sourceFamily', 'originalPublicationKey', 'publicationDate', 'documentEffectiveDate'])
                or o['observedAt'] != source['accessedAt']):
            raise ValueError('Dangling source provenance')
    matched = set()
    gids = {g['eventGroupId'] for g in read_jsonl(TRIAGE / 'groups.jsonl.gz')}
    for a in read_jsonl(output / 'matches.jsonl.gz'):
        if a['observationId'] not in obs or a['eventGroupId'] not in gids or a['historicallyVerified'] is not False:
            raise ValueError('Dangling match or auto-admission')
        matched.add(a['observationId'])
    unmatched = {x['observationId'] for x in read_jsonl(output / 'unmatched.jsonl.gz')}
    if matched & unmatched or matched | unmatched != obs.keys():
        raise ValueError('Observation silently lost or both matched and unmatched')
    batches = list(read_jsonl(output / 'review-packets.jsonl.gz'))
    existing = [json.loads(p.read_text()) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing, *batches])
    if any(not b.get('preparationOnly') or any(e['status'] != 'pending_review' for e in b['events']) for b in batches):
        raise ValueError('Mechanical evidence packets cannot impersonate human acceptance')
    print(f'Validated {len(sources)} primary publications, {len(obs)} retained observations; no historical admissions.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'validate'])
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    (build if args.command == 'build' else validate)(args.output)
