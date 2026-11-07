"""Rank the complete existing worldwide research corpus without fetching or rescanning Git.

Directory observations remain research leads. Scores select work; they do not certify
physical moves, code validity, source independence, copyright or admission authority.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISCOVERY = ROOT / 'research/discovery/generated'
REFERENCE = ROOT / 'reference/generated'
TRIAGE = ROOT / 'reference/triage'
OUT = ROOT / 'research/evidence/global-code-expansion'
RANKED_EVENT_INDEX = 'ranked-events.manifest.json'
RANKED_EVENT_MAX_BYTES = 8 * 1024 * 1024
MARKETS = ('asia', 'europe-middle-east', 'americas-africa-oceania-other')
SCREENING_OUTPUT_NAMES = {RANKED_EVENT_INDEX, 'ranked-code-links.jsonl.gz',
    'ranked-reuse-leads.jsonl.gz', 'high-value-queue.jsonl.gz', 'screening-summary.json',
    *(f'queue-{market}.json' for market in MARKETS)}
FAMILIES = {'airport-codes': 'ourairports', 'airport-codes-raw': 'ourairports',
            'airport-codes-initial': 'ourairports', 'airport-codes-legacy': 'ourairports',
            'ourairports': 'ourairports', 'mwgg': 'lineage_unestablished',
            'airportsdata': 'lineage_unestablished', 'airportsdata-city-codes': 'city_membership'}
ASIA = {'CN', 'JP', 'KR', 'KP', 'IN', 'PK', 'BD', 'TH', 'MY', 'ID', 'PH', 'VN',
        'KH', 'NP', 'LA', 'TW', 'LK', 'MM', 'BT', 'SG', 'BN', 'MO', 'HK', 'MV',
        'AF', 'KZ', 'KG', 'UZ', 'TJ', 'TM', 'TL', 'MN'}
EUROPE_MIDDLE_EAST = {'GB', 'DE', 'FR', 'ES', 'IT', 'NO', 'RU', 'TR', 'PT', 'GR',
                     'FI', 'SE', 'IE', 'NL', 'CH', 'IS', 'PL', 'IR', 'IQ', 'IL',
                     'SA', 'AE', 'OM', 'QA', 'BH', 'JO', 'LB', 'CY', 'AT', 'BE',
                     'CZ', 'DK', 'EE', 'HR', 'HU', 'LT', 'LU', 'LV', 'MT', 'RO',
                     'RS', 'SI', 'SK', 'UA', 'BG', 'AL', 'BA', 'ME', 'MK', 'BY',
                     'AM', 'AZ', 'GE', 'SY', 'YE', 'KW', 'PS', 'XK', 'KS', 'MD'}
OFFICIAL = {
    'CN': 'https://www.eaipchina.cn/', 'JP': 'https://aisjapan.mlit.go.jp/',
    'KR': 'https://aim.koca.go.kr/', 'IN': 'https://aim-india.aai.aero/',
    'PK': 'https://caapakistan.com.pk/', 'BD': 'https://caab.gov.bd/',
    'TH': 'https://aip.caat.or.th/', 'MY': 'https://aip.caam.gov.my/',
    'ID': 'https://aimindonesia.dephub.go.id/', 'PH': 'https://caap.gov.ph/',
    'VN': 'https://vnaic.vn/', 'US': 'https://www.faa.gov/air_traffic/publications/',
    'CA': 'https://www.navcanada.ca/', 'GB': 'https://nats-uk.ead-it.com/',
    'DE': 'https://aip.dfs.de/', 'FR': 'https://www.sia.aviation-civile.gouv.fr/',
    'ES': 'https://aip.enaire.es/', 'IT': 'https://www.enav.it/',
    'NO': 'https://avinor.no/en/ais/', 'TR': 'https://www.dhmi.gov.tr/',
    'RU': 'https://www.caiga.ru/', 'BR': 'https://aisweb.decea.mil.br/',
    'CL': 'https://aipchile.dgac.gob.cl/', 'ZA': 'https://www.caa.co.za/',
    'AU': 'https://www.airservicesaustralia.com/aip/',
    'NZ': 'https://www.aip.net.nz/', 'AR': 'https://ais.anac.gob.ar/',
    'CO': 'https://www.aerocivil.gov.co/', 'PE': 'https://www.corpac.gob.pe/',
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def write_rows(path, values):
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
            for value in values:
                stream.write((canonical(value) + '\n').encode())


def ranked_event_shard(name):
    return bool(re.fullmatch(r'ranked-events\.[0-9]{3,}\.jsonl\.gz', name))


def screening_output(name):
    return name in SCREENING_OUTPUT_NAMES or ranked_event_shard(name)


def write_ranked_event_shards(output, values):
    """Preserve the ranked JSONL stream, bounding each complete-record shard."""
    files, payload = [], bytearray()
    total_digest = hashlib.sha256()
    total_bytes = total_records = shard_records = 0
    first_rank = last_rank = None

    def flush():
        nonlocal payload, shard_records, first_rank, last_rank
        if not payload:
            return
        path = output / f'ranked-events.{len(files):03d}.jsonl.gz'
        with path.open('wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
                stream.write(payload)
        files.append({'path': path.name, 'sha256': sha(path), 'bytes': path.stat().st_size,
            'uncompressedSha256': hashlib.sha256(payload).hexdigest(),
            'uncompressedBytes': len(payload), 'recordCount': shard_records,
            'firstRank': first_rank, 'lastRank': last_rank})
        payload, shard_records, first_rank, last_rank = bytearray(), 0, None, None

    for value in values:
        line = (canonical(value) + '\n').encode()
        assert len(line) <= RANKED_EVENT_MAX_BYTES, f'Ranked event {value["rank"]} exceeds shard bound.'
        if len(payload) + len(line) > RANKED_EVENT_MAX_BYTES:
            flush()
        assert value['rank'] == total_records + 1, 'Ranked event order is not contiguous.'
        first_rank = value['rank'] if first_rank is None else first_rank
        last_rank = value['rank']
        payload.extend(line)
        shard_records += 1
        total_records += 1
        total_bytes += len(line)
        total_digest.update(line)
    flush()
    write_json(output / RANKED_EVENT_INDEX, {'formatVersion': 1,
        'eventGroups': total_records, 'recordCount': total_records,
        'ordering': 'priorityScore descending, eventGroupId ascending; rank is contiguous from 1.',
        'maxUncompressedBytesPerShard': RANKED_EVENT_MAX_BYTES,
        'totalUncompressedBytes': total_bytes, 'totalUncompressedSha256': total_digest.hexdigest(),
        'uncompressedSha256': total_digest.hexdigest(),
        'files': files})
    retained = {entry['path'] for entry in files}
    for path in output.iterdir():
        if path.name == 'ranked-events.jsonl.gz' or (ranked_event_shard(path.name) and path.name not in retained):
            path.unlink()


def valid(scheme, code):
    return (isinstance(code, str) and code not in {'XXX', 'XXXX', 'NONE', 'NULL'}
            and bool(re.fullmatch('[A-Z]{3}' if scheme == 'IATA' else '[A-Z]{4}', code)))


def classification(candidate):
    kinds, changes = set(candidate['types']), candidate['changes']
    events = {'iata_change', 'possible_relocation', 'possible_closure', 'possible_reopening', 'possible_rename'}
    if 'city_code_membership_change' in kinds:
        return 'city_membership_excluded'
    if not kinds & events and 'icao_change' in kinds and not any(changes.get('icao', [])):
        return 'empty_namespace_backfill_excluded'
    if not kinds & events and not ('icao_change' in kinds and any(changes.get('icao', []))):
        return 'non_event_revision_deferred'
    if (candidate.get('distanceKm') or 0) >= 5:
        return 'location_change_or_directory_correction'
    if kinds & {'iata_change', 'icao_change'}:
        return 'code_change_observation'
    if kinds & {'possible_closure', 'possible_reopening'}:
        return 'closure_or_reopening_observation'
    return 'name_label_observation'


def prior_corpus(groups, candidate_group):
    """Use exact research identifiers; code-only matches are labelled separately."""
    identifier_paths, code_paths = defaultdict(set), defaultdict(set)
    paths = [*sorted((ROOT / 'research/discovery/batches').glob('global-*.json'))]
    for directory in ['research/evidence/priority-markets',
                      'research/evidence/priority-market-batch-6',
                      'research/evidence/global-batch-5', 'research/admissions/0.11.0']:
        paths.extend(sorted((ROOT / directory).rglob('*.json')))
    def walk(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'code', 'codes'}:
                    for code in item if isinstance(item, list) else [item]:
                        if isinstance(code, str):
                            m = re.fullmatch('(IATA|ICAO):([A-Z]+)', code)
                            if m:
                                code_paths[(m[1], m[2])].add(path)
                walk(item, path)
        elif isinstance(value, list):
            for item in value:
                walk(item, path)
        elif isinstance(value, str):
            if value in groups:
                identifier_paths[value].add(path)
            elif value in candidate_group:
                identifier_paths[candidate_group[value]].add(path)
    for path in paths:
        walk(json.loads(path.read_text()), str(path.relative_to(ROOT)))
    return identifier_paths, code_paths, paths


def build(output=OUT):
    output.mkdir(parents=True, exist_ok=True)
    groups = {g['eventGroupId']: g for g in rows(TRIAGE / 'groups.jsonl.gz')}
    candidate_group = {cid: gid for gid, g in groups.items() for cid in g['candidateIds']}
    assert sum(len(g['candidateIds']) for g in groups.values()) == len(candidate_group), 'A selected candidate appears in multiple groups.'
    originals = json.loads((DISCOVERY / 'manifest.json').read_text())
    reference_lock = json.loads((REFERENCE / 'manifest.json').read_text())
    source_terms = {s['id']: {'license': s.get('license'), 'url': s['url'],
        'scope': 'Directory research facts only; no authority, independence or primary-source rights inherited.'}
        for s in json.loads((ROOT / 'research/discovery/sources.json').read_text())['sources']}
    inputs = [TRIAGE / 'groups.jsonl.gz', TRIAGE / 'code-reuse-leads.jsonl.gz',
              TRIAGE / 'metrics.json', DISCOVERY / 'manifest.json', REFERENCE / 'manifest.json',
              ROOT / 'test/curated-0.11.0.json', ROOT / 'research/discovery/reviews.json',
              ROOT / 'research/discovery/sources.json', DISCOVERY / 'summary.json']
    source_paths = sorted(DISCOVERY.glob('*.candidates.*.jsonl.gz'))
    source_paths = [p for p in source_paths if p.name != 'code-links.candidates.jsonl.gz']
    source_counts, classifications = Counter(), Counter()
    candidates = {}
    for path in source_paths:
        assert sha(path) == originals['files'][path.name]['sha256'], path
        inputs.append(path)
        for candidate in rows(path):
            source_counts[candidate['sourceId']] += 1
            classifications[classification(candidate)] += 1
            cid = candidate['candidateId']
            if cid in candidate_group:
                assert cid not in candidates, f'Duplicate source candidate ID: {cid}'
                candidates[cid] = {k: candidate[k] for k in ['candidateId', 'sourceId', 'sourceEntityId',
                    'changes', 'context', 'types', 'distanceKm', 'matches', 'time']}
                candidates[cid]['observationCount'] = len(candidate['observations'])
                candidates[cid]['sourceUrl'] = candidate['evidence'].get('sourceUrl')
    assert len(candidates) == len(candidate_group), (len(candidates), len(candidate_group))
    print(f'Inspected {sum(source_counts.values())} source revision candidates; joined {len(candidates)} selected candidates.', flush=True)
    references, code_references = {}, defaultdict(set)
    for path in sorted(REFERENCE.glob('records.*.jsonl.gz')):
        assert sha(path) == reference_lock['files'][path.name]['sha256'], path
        inputs.append(path)
        for reference in rows(path):
            references[reference['referenceId']] = {k: reference.get(k) for k in ['referenceId', 'name',
                'country', 'region', 'municipality', 'facilityType', 'identifiers', 'locations',
                'curatedAirportIds', 'sourceId', 'sourceEntityId', 'historicalIdentifiers']}
            for scheme in ['IATA', 'ICAO']:
                code = reference['identifiers'].get(scheme)
                if valid(scheme, code):
                    code_references[(scheme, code)].add(reference['referenceId'])
            for historic in reference['historicalIdentifiers']:
                scheme, code = historic.get('scheme'), historic.get('code')
                if scheme in ['IATA', 'ICAO'] and valid(scheme, code):
                    code_references[(scheme, code)].add(reference['referenceId'])
    formal = json.loads((ROOT / 'test/curated-0.11.0.json').read_text())
    formal_external = {str(a.get('externalIds', {}).get('ourAirports')): a['airportId'] for a in formal['airports']}
    formal_codes = defaultdict(list)
    for a in formal['assignments']:
        formal_codes[(a['scheme'], a['code'])].append({'airportId': a['airportId'], 'assignmentId': a['assignmentId']})
    reuse = {(r['scheme'], r['code']): r for r in rows(TRIAGE / 'code-reuse-leads.jsonl.gz')}
    cross_index_path = DISCOVERY / 'cross-source-code-index.jsonl.gz'
    legacy_path = DISCOVERY / 'legacy-links.jsonl.gz'
    cross_by_group, legacy_by_group = defaultdict(list), defaultdict(list)
    cross_index_count, cross_memberships = 0, 0
    for path in [cross_index_path, legacy_path]:
        assert sha(path) == originals['files'][path.name]['sha256'], path
        inputs.append(path)
    for association in rows(cross_index_path):
        cross_index_count += 1
        cross_memberships += len(association['candidateIds'])
        for gid in sorted({candidate_group[cid] for cid in association['candidateIds'] if cid in candidate_group}):
            cross_by_group[gid].append({'scheme': association['scheme'], 'code': association['code'],
                'relatedCandidateCount': len(association['candidateIds']),
                'meaning': 'Shared source string only; no physical or event equivalence or independent confirmation.'})
    legacy_count = 0
    for legacy in rows(legacy_path):
        legacy_count += 1
        for gid in sorted({candidate_group[cid] for cid in legacy['machineCandidateIds'] if cid in candidate_group}):
            legacy_by_group[gid].append({'legacyCandidateId': legacy['candidateId'],
                'label': legacy['label'], 'status': legacy.get('status'),
                'exclusionReason': legacy.get('exclusionReason'), 'meaning': legacy['linkMeaning']})
    prior, code_prior, prior_paths = prior_corpus(groups, candidate_group)
    inputs.extend(prior_paths)
    reviews = json.loads((ROOT / 'research/discovery/reviews.json').read_text())
    link_path = DISCOVERY / 'code-links.candidates.jsonl.gz'
    assert sha(link_path) == originals['files'][link_path.name]['sha256']
    inputs.append(link_path)
    links, group_links = [], defaultdict(list)
    for link in rows(link_path):
        gids = sorted({candidate_group[cid] for cid in link['relatedCandidateIds'] if cid in candidate_group})
        for gid in gids:
            group_links[gid].append(link['candidateId'])
        key = (link['scheme'], link['code'])
        refs = sorted(code_references[key])
        links.append({'candidateId': link['candidateId'], 'scheme': key[0], 'code': key[1],
            'codeSyntaxValid': valid(*key), 'eventGroupIds': gids,
            'countries': link['context']['countries'], 'airports': link['context']['airports'],
            'sourceId': link['sourceId'], 'sourceFamily': FAMILIES[link['sourceId']],
            'sourceObservationCount': len(link['sourceVersions']),
            'sourceEntityIds': link['sourceEntityIds'], 'referenceIds': refs,
            'geographicReuseLead': key in reuse, 'formalAssignmentsForCode': formal_codes[key],
            'classification': 'cross_site_reuse_or_duplicate_or_source_error_unverified' if key in reuse else 'multi_entity_code_association_unverified',
            'dateBounds': {'earliest': None, 'latest': None, 'precision': 'unknown'},
            'missingOriginals': ['Code-specific official allocation/withdrawal or controlled AIP records for each physical site.'],
            'historicallyVerified': False})
    ranking = []
    for gid, group in groups.items():
        members = [candidates[cid] for cid in group['candidateIds']]
        reference = references.get(group['physicalMatch']['referenceId'])
        codes, replacements, code_changes = {'IATA': set(), 'ICAO': set()}, set(), set()
        kinds = set()
        for c in members:
            kinds.update(c['types'])
            for scheme, field in [('IATA', 'iata'), ('ICAO', 'icao')]:
                values = c['changes'].get(field, [])
                codes[scheme].update(code for code in values if valid(scheme, code))
                if any(valid(scheme, v) for v in values):
                    code_changes.add(scheme)
                if len(values) == 2 and all(valid(scheme, v) for v in values) and values[0] != values[1]:
                    replacements.add(scheme)
        if reference:
            for scheme in codes:
                code = reference['identifiers'].get(scheme)
                if valid(scheme, code):
                    codes[scheme].add(code)
                for historic in reference['historicalIdentifiers']:
                    if historic.get('scheme') == scheme and valid(scheme, historic.get('code')):
                        codes[scheme].add(historic['code'])
        keys = [(s, c) for s, cs in codes.items() for c in sorted(cs)]
        reuse_keys = [key for key in keys if key in reuse]
        formal_ids = set(reference['curatedAirportIds'] or []) if reference else set()
        for c in members:
            if c['sourceId'] in {'ourairports', 'airport-codes-raw', 'airport-codes-initial'}:
                if c['sourceEntityId'] in formal_external:
                    formal_ids.add(formal_external[c['sourceEntityId']])
        formal_assignments = [a for a in formal['assignments'] if a['airportId'] in formal_ids]
        possible_assignments = [a for key in keys for a in formal_codes[key]]
        direct_prior = sorted(prior[gid])
        code_only_prior = sorted(set().union(*(code_prior[key] for key in keys))) if keys else []
        max_distance = max((c['distanceKm'] or 0 for c in members), default=0)
        excluded = [reviews[cid]['exclusionReason'] for cid in group['candidateIds'] if cid in reviews and reviews[cid].get('exclusionReason')]
        score, reasons = 0, []
        def add(points, reason):
            nonlocal score
            score += points
            reasons.append({'points': points, 'reason': reason})
        if keys: add(20, 'Explicit typed IATA/ICAO directory observation; still not primary allocation evidence.')
        if 'IATA' in replacements: add(35, 'Non-empty IATA replacement observation merits separate code chronology.')
        elif 'IATA' in code_changes: add(20, 'IATA addition/removal observation.')
        if 'ICAO' in replacements: add(30, 'Non-empty explicit ICAO replacement observation.')
        elif 'ICAO' in code_changes: add(15, 'Explicit ICAO addition/removal observation; GPS/IDENT alone is not ICAO.')
        if reuse_keys: add(25, 'Code occurs in existing geographically distinct association leads; reuse unproven.')
        if 5 <= max_distance <= 500 and code_changes: add(15, 'Code observation plus spatial difference merits site review; does not prove relocation.')
        if max_distance > 500: add(-30, 'Very large coordinate shift increases source-repurposing/correction risk.')
        if kinds & {'possible_closure', 'possible_reopening'} and keys: add(10, 'Coded closure/reopening observation; withdrawal date is independent.')
        if direct_prior: add(20, 'Exact candidate/event IDs already have reusable research; avoids duplicate acquisition.')
        elif code_only_prior: add(5, 'Existing research shares this code; reuse must be checked for the specific site.')
        if formal_ids: add(15, 'A physical airport already has a formal identity; code/date gaps remain separate.')
        if reference and reference['facilityType'] in {'large_airport', 'medium_airport'}:
            add(20 if reference['facilityType'] == 'large_airport' else 10, 'Passenger-airport reference type increases plausible flight-identification value.')
        if not code_changes and not reuse_keys: add(-30, 'No direct typed code change or geographically distinct association in this event.')
        if not keys: add(-50, 'No syntactically valid explicit IATA/ICAO observed; label/coordinate work has lower code yield.')
        if excluded: add(-150, 'Existing review excluded this interpretation; retain actual code follow-ups separately.')
        if re.search('duplicate|non.existent|unknown airport', group['name'] or '', re.I):
            add(-60, 'Directory label flags duplicate/unknown/nonexistent record; resolve source error first.')
        tags = []
        if code_changes: tags.append('same_site_code_change_or_source_correction_unverified')
        if reuse_keys: tags.append('cross_site_code_reuse_or_directory_error_unverified')
        if max_distance >= 5: tags.append('location_change_or_directory_correction_unverified')
        if 'possible_closure' in kinds: tags.append('closure_observation_not_code_withdrawal')
        if 'possible_reopening' in kinds: tags.append('reopening_observation_not_code_reallocation')
        if not code_changes and not reuse_keys: tags.append('label_coordinate_or_duplicate_observation_without_typed_code_change')
        if excluded: tags.append('prior_excluded_interpretation')
        country = group['country'] or next((c['context']['country'] for c in members if c['context']['country']), None)
        region = next((c['context'].get('region') for c in members if c['context'].get('region')), None)
        market = 'asia' if country in ASIA else 'europe-middle-east' if country in EUROPE_MIDDLE_EAST else 'americas-africa-oceania-other'
        sites = []
        if reference:
            sites = [{'referenceId': reference['referenceId'], 'name': reference['name'], 'locationId': p['locationId'],
                      'coordinates': p['coordinates'], 'physicalIdentityVerified': False} for p in reference['locations']]
        related_sites = []
        for rid in sorted({rid for key in reuse_keys for rid in reuse[key]['referenceIds']}):
            related = references[rid]
            related_sites.append({'referenceId': rid, 'country': related['country'], 'name': related['name'],
                'locations': [{'locationId': loc['locationId'], 'coordinates': loc['coordinates']} for loc in related['locations']],
                'physicalIdentityVerified': False})
        cluster_basis = [country, group['physicalMatch']['referenceId'] or (group['name'] or '').casefold(),
                         [(s, sorted(cs)) for s, cs in codes.items()]]
        cluster = 'cluster_' + hashlib.sha256(canonical(cluster_basis).encode()).hexdigest()[:24]
        ranking.append({'eventGroupId': gid, 'candidateId': group['candidateIds'][0], 'candidateIds': group['candidateIds'],
            'researchClusterKey': cluster,
            'researchClusterMeaning': 'Same reference/name and typed code set share acquisition work; eventGroupIds remain separate observations, not independent code-allocation events.',
            'country': country, 'region': region, 'researchMarket': market, 'airport': group['name'],
            'referenceId': group['physicalMatch']['referenceId'], 'candidatePhysicalSites': sites,
            'IATA': sorted(codes['IATA']), 'ICAO': sorted(codes['ICAO']),
            'sourceIds': sorted({c['sourceId'] for c in members}),
            'sourceFamilies': sorted({FAMILIES[c['sourceId']] for c in members}),
            'directorySourceUseTerms': {s: source_terms[s] for s in sorted({c['sourceId'] for c in members})},
            'primarySourceAvailability': 'Unassessed by directory machine pass; source/issuer discovery entry points are provided for batch acquisition.',
            'sourceIndependence': 'OurAirports derivatives count as one family; other directory lineage unestablished; independent historical confirmation not established.',
            'independentHistoricalConfirmationsFromDirectoryScreen': 0,
            'historicalCodeObservationCount': sum(c['observationCount'] for c in members if any(t in {'iata_change', 'icao_change'} for t in c['types'])),
            'sourceRevisionObservationCount': sum(c['observationCount'] for c in members),
            'directoryObservations': [{'candidateId': c['candidateId'], 'sourceId': c['sourceId'],
                'sourceEntityId': c['sourceEntityId'], 'sourceUrl': c['sourceUrl'],
                'changes': c['changes'], 'time': c['time'], 'observationCount': c['observationCount']} for c in members],
            'changeTypes': sorted(kinds), 'classifications': tags, 'originalTriageClassifications': group['classifications'],
            'maximumCoordinateDifferenceKm': max_distance, 'relocationProven': False,
            'crossPhysicalAirportCodeLeads': [reuse[k] for k in reuse_keys], 'relatedPhysicalSiteCandidates': related_sites,
            'codeAssociationCandidateIds': sorted(group_links[gid]),
            'crossSourceCodeIndexAssociations': cross_by_group[gid], 'legacyResearchLinks': legacy_by_group[gid],
            'existingFormalAirportIds': sorted(formal_ids),
            'existingFormalAssignmentIds': sorted(a['assignmentId'] for a in formal_assignments),
            'existingFormalAssignments': formal_assignments,
            'codeOnlyPossibleFormalAssignments': possible_assignments,
            'existingResearchExactIdPaths': direct_prior, 'existingResearchCodeOnlyPaths': code_only_prior,
            'existingResearchReuse': 'Exact-ID research may be reused; code-only overlap needs site/claim verification; no original was downloaded by screening.',
            'missingOriginals': ['IATA: dated allocation/transfer/withdrawal original tied to the physical site.' if codes['IATA'] else None,
                'ICAO: controlled AD 2 plus amendment/AIRAC/NOTAM and effective-version chronology tied to site.' if codes['ICAO'] else None,
                'Physical continuity versus relocation/correction evidence; source-family rights and applicable admission authorization.'],
            'officialSourceDiscoveryUrls': ([OFFICIAL[country]] if country in OFFICIAL else []) + ['https://www.iata.org/en/publications/directories/code-search/'],
            'codeValidityProof': {'status': 'new_candidate_claims_unproven_by_machine_screen', 'earliest': None, 'latest': None, 'precision': 'unknown',
                'note': 'Existing formal assignment bounds remain separately preserved. Revision, capture, publication and airport operating dates are not new code-validity bounds; no continuity inferred.'},
            'expectedNewResolvedQueries': {'value': None, 'status': 'unmeasured', 'basis': 'Needs code-specific admissible intervals and production resolveAirport differential.'},
            'expectedUncertainReduction': {'value': None, 'status': 'unmeasured', 'basis': 'No effective interval is manufactured by ranking.'},
            'priorityScore': score, 'priorityReasons': reasons, 'priorityTier': 'high' if score >= 65 and not excluded else 'follow_up' if score >= 20 else 'defer_or_correction',
            'priorExclusions': excluded, 'formalAdmission': False})
    ranking.sort(key=lambda r: (-r['priorityScore'], r['eventGroupId']))
    ranks = {}
    for rank, row in enumerate(ranking, 1):
        row['rank'] = rank
        row['missingOriginals'] = [x for x in row['missingOriginals'] if x]
        ranks[row['eventGroupId']] = rank
    links.sort(key=lambda r: (min((ranks[g] for g in r['eventGroupIds']), default=10**9), r['candidateId']))
    for rank, link in enumerate(links, 1): link['rank'] = rank
    reuse_ranked = []
    by_code = defaultdict(list)
    for r in ranking:
        for key in [(s, c) for s in ['IATA', 'ICAO'] for c in r[s]]: by_code[key].append(r['eventGroupId'])
    for key, lead in reuse.items():
        gids = by_code[key]
        reuse_ranked.append({**lead, 'eventGroupIds': gids, 'bestEventRank': min((ranks[g] for g in gids), default=None),
                            'formalAssignmentsForCode': formal_codes[key],
                            'priorityReason': 'Sort by best complete-event rank; no match remains in queue for original/source-error research.'})
    reuse_ranked.sort(key=lambda r: (r['bestEventRank'] or 10**9, r['scheme'], r['code']))
    high = [r for r in ranking if r['priorityTier'] == 'high']
    summary = {'formatVersion': 1, 'baselineCommit': '7d21ff6762e1569faa1be19c8203e577420cd1f2', 'formalDataVersion': formal['dataVersion'],
        'sourceRevisionCandidatesInspected': sum(source_counts.values()), 'sourceRevisionCandidatesBySource': dict(source_counts),
        'sourceRevisionClassifications': dict(classifications), 'selectedCandidatesJoined': len(candidates),
        'eventGroupsRanked': len(ranking), 'codeAssociationCandidatesRanked': len(links),
        'codeAssociationCandidatesByScheme': dict(Counter(r['scheme'] for r in links)),
        'countriesInCodeAssociationCandidates': len({country for r in links for country in r['countries']}),
        'crossSourceCodeIndexKeysInspected': cross_index_count, 'crossSourceCodeIndexCandidateMemberships': cross_memberships,
        'legacyResearchLinksInspected': legacy_count,
        'existingSourceTransitionLeadsAfterExactCrossSourceGrouping': json.loads((DISCOVERY / 'summary.json').read_text())['sourceTransitionLeadsAfterExactCrossSourceGrouping'],
        'geographicReuseLeadsRanked': len(reuse_ranked), 'referenceRecordsInspected': len(references),
        'countriesInEventGroups': len({r['country'] for r in ranking if r['country']}),
        'eventGroupsByCountry': dict(Counter(r['country'] or 'unknown' for r in ranking)),
        'priorityTiers': dict(Counter(r['priorityTier'] for r in ranking)),
        'highValueGroups': len(high), 'highValueGroupsByResearchMarket': dict(Counter(r['researchMarket'] for r in high)),
        'highValueResearchClusters': len({r['researchClusterKey'] for r in high}),
        'existingResearchExactIdGroups': sum(bool(r['existingResearchExactIdPaths']) for r in ranking),
        'sourceIndependence': 'Source counts and revisions are not independent corroboration.',
        'officialSourceUrlsMeaning': 'Discovery entry points only; access, control, original retrieval and rights are assessed by evidence batches.',
        'scoreMeaning': 'Deterministic research-yield heuristic, not evidence certainty or forecast resolved-query count.',
        'highValueThreshold': 65, 'numberOfAirportsCap': None,
        'formalNewIataAssignments': 0, 'formalNewIcaoAssignments': 0,
        'newResolvedQueriesFromScreening': 0, 'uncertainIntervalsReducedByScreening': 0,
        'noGitHistoryRescan': True, 'noOriginalDownloads': True,
        'classificationCaveat': 'No coordinate change is classified as a proven relocation. Cross-site reuse and same-site changes remain unverified alternatives; source corrections/duplicates are preserved.',
        'rankedEventOutput': RANKED_EVENT_INDEX, 'codeLinkOutput': 'ranked-code-links.jsonl.gz', 'reuseOutput': 'ranked-reuse-leads.jsonl.gz'}
    assert summary['sourceRevisionCandidatesInspected'] == 1240058, summary
    assert len(ranking) == 88330 and len(candidates) == 117356 and len(links) == 2484 and len(reuse_ranked) == 493
    assert len(references) == 86950
    assert len({r['candidateId'] for r in links}) == len(links), 'Duplicate code-link IDs.'
    assert len({(r['scheme'], r['code']) for r in reuse_ranked}) == len(reuse_ranked)
    triage_metrics = json.loads((TRIAGE / 'metrics.json').read_text())
    assert dict(classifications) == triage_metrics['candidateClassifications'], 'Existing triage dispositions changed.'
    write_ranked_event_shards(output, ranking)
    write_rows(output / 'ranked-code-links.jsonl.gz', links)
    write_rows(output / 'ranked-reuse-leads.jsonl.gz', reuse_ranked)
    write_rows(output / 'high-value-queue.jsonl.gz', high)
    for market in MARKETS:
        queue, seen = [], set()
        for row in high:
            if row['researchMarket'] == market and row['researchClusterKey'] not in seen:
                queue.append(row)
                seen.add(row['researchClusterKey'])
        write_json(output / f'queue-{market}.json', queue[:100])
    write_json(output / 'screening-summary.json', summary)
    outputs = sorted(p for p in output.iterdir() if screening_output(p.name))
    inputs = sorted(set(inputs + [Path(__file__)]))
    write_json(output / 'screening-manifest.json', {'formatVersion': 1,
        'inputs': {str(p.relative_to(ROOT)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in inputs},
        'outputs': {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in outputs}})
    print(canonical(summary), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--check', action='store_true', help='Rebuild in ignored work/ and require byte-identical outputs.')
    args = parser.parse_args()
    if args.check:
        (ROOT / 'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='global-code-screen-', dir=ROOT / 'work') as directory:
            build(Path(directory))
            expected = {path.name for path in Path(directory).iterdir()}
            actual = {path.name for path in args.output.iterdir() if screening_output(path.name)
                or path.name in {'screening-manifest.json', 'ranked-events.jsonl.gz'}}
            assert actual == expected, {'missing': sorted(expected - actual), 'unexpected': sorted(actual - expected)}
            for path in sorted(Path(directory).iterdir()):
                assert path.read_bytes() == (args.output / path.name).read_bytes(), path.name
        print('Complete global screening determinism verified.')
    else:
        build(args.output)
