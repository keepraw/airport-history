"""Offline cross-source linkage, baseline comparison and auditable coverage totals."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from core import canonical, distance, git, normalized, read_candidates, read_jsonl, rows_from_text, source_text, stable_id, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/discovery/generated'


def regional_coverage(config, out):
    result = []
    for source in config['sources']:
        by_year = {}
        for version in read_jsonl(out / (source['id'] + '.versions.jsonl.gz')):
            if version['afterBlob'] == '0' * 40 or version['afterRecords'] is None:
                continue
            year = version['observedAt'][:4]
            if year not in by_year or version['observedAt'] > by_year[year]['observedAt']:
                by_year[year] = version
        for year, version in sorted(by_year.items()):
            raw = git(ROOT / source['localRepository'], 'cat-file', 'blob', version['afterBlob']).decode('utf-8-sig')
            raw, _ = source_text(source, raw)
            _, rows = rows_from_text(raw, source['key'], source.get('format', 'csv'))
            countries = Counter(normalized(r).get('country') or 'unknown' for r in rows.values())
            result.append({'sourceId': source['id'], 'observationYear': year,
                           'representativeVersion': version, 'recordsByCountry': dict(sorted(countries.items())),
                           'meaning': 'Country presence in the latest available revision of this year; all intervening revisions scanned for changes.'})
    write_json(out / 'year-country-coverage.json', result)


def code_links(config, out):
    """All within-source multi-entity code associations, with no validity inference."""
    groups = defaultdict(dict)
    entities = {}
    candidate_codes = defaultdict(set)
    for source in config['sources']:
        sid = source['id']
        if sid.endswith('city-codes'):
            continue
        for record in read_jsonl(out / (sid + '.entities.jsonl.gz')):
            entity = record['sourceEntityId']
            entities[(sid, entity)] = record
            row = normalized(record['reference']['row'])
            for scheme in ('iata', 'icao'):
                if row.get(scheme):
                    groups[(sid, scheme, row[scheme])][entity] = set()
        for record in read_candidates(out, sid):
            entity = record['sourceEntityId']
            for scheme in ('iata', 'icao'):
                for code in record['changes'].get(scheme, []):
                    if code:
                        groups[(sid, scheme, code)].setdefault(entity, set()).add(record['candidateId'])
                        candidate_codes[(scheme, code)].add(record['candidateId'])
    links = []
    for (sid, scheme, code), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        pseudo = scheme == 'icao' and sid in ('mwgg', 'airportsdata')
        refs = [entities[(sid, e)] for e in sorted(members)]
        links.append({
            'candidateId': stable_id('link_', [sid, scheme, code]),
            'sourceId': sid, 'sourceEntityIds': sorted(members),
            'scheme': scheme.upper(), 'code': code,
            'codeSemantics': 'ICAO or pseudo identifier; not an official allocation ledger' if pseudo else 'source code field',
            'types': ['potential_historical_conflict', 'possible_code_transfer'],
            'observedChange': 'The same source code occurs on multiple source entities across inspected versions.',
            'possibleEvent': 'Possible code reuse/transfer, duplicate records or corrections; physical identity and overlap unverified.',
            'context': {'countries': sorted({normalized(r['reference']['row']).get('country', 'unknown') for r in refs}),
                        'airports': [normalized(r['reference']['row']).get('name') for r in refs]},
            'relatedCandidateIds': sorted(set().union(*members.values())),
            'sourceVersions': [{'entity': r['sourceEntityId'], **r['reference']} for r in refs],
            'time': {'eventDate': None, 'precision': 'unknown',
                     'observationFrom': min(r['firstObservedAt'] for r in refs),
                     'observationThrough': max(r['lastChangedAt'] for r in refs)},
            'matches': {'airportIds': sorted({a for r in refs for a in r['matches']['airportIds']}),
                        'assignmentIds': sorted({a for r in refs for a in r['matches']['codeOnlyPossibleAssignmentIds']}),
                        'nameIds': sorted({a for r in refs for a in r['matches']['nameIds']})},
            'evidence': {'sourceType': 'secondary', 'evidenceType': 'indirect', 'verificationStatus': 'pending'},
            'review': {'status': 'pending_investigation', 'conflicts': [], 'exclusionReason': None,
                       'evidenceGaps': ['Review separate physical identities, duplicate rows, simultaneous conflict and effective allocation dates.'],
                       'nextAction': 'Inspect all linked source revisions, then obtain code-specific primary evidence.'}})
    write_jsonl(out / 'code-links.candidates.jsonl.gz', links)
    # Same namespace/code is a research work queue across sources, NOT an event merge.
    write_jsonl(out / 'cross-source-code-index.jsonl.gz',
                ({'scheme': scheme.upper(), 'code': code, 'candidateIds': sorted(ids),
                  'relationship': 'shared code only; neither physical identity nor event equivalence established'}
                 for (scheme, code), ids in sorted(candidate_codes.items())))
    return links


def legacy_links(config, out):
    legacy = json.loads((ROOT / 'research/discovery/legacy.json').read_text())
    dataset = json.loads((ROOT / 'data/airports.json').read_text())
    codes = defaultdict(set)
    for source in config['sources']:
        for record in read_candidates(out, source['id']):
            for code in record['context']['codes']:
                codes[code].add(record['candidateId'])
    for lead in legacy:
        lead['machineCandidateIds'] = sorted({cid for code in lead['codes'] for cid in codes[code]})
        lead['linkMeaning'] = 'Shared code research lead only; manual event equivalence must be reviewed.'
        assignments = [a for a in dataset['assignments'] if a['code'] in lead['codes']]
        airports = sorted({a['airportId'] for a in assignments})
        lead['sourceId'] = 'legacy-research'
        lead['sourceEntityId'] = lead['candidateId']
        lead['types'] = ['preserved_manual_lead']
        lead['context'] = {'country': 'see_original_research', 'city': lead['label'],
                           'airport': lead.get('siteLead', lead['label']), 'codes': lead['codes']}
        lead['time'] = {'eventDate': None, 'eventDatePrecision': 'unknown',
                        'reportedDateLead': lead.get('reportedDateLead')}
        lead['observations'] = [{'sourceVersion': lead['sourceVersion'], 'path': lead['sourceDocument']}]
        lead['evidence'] = {'evidenceType': lead['evidenceType'],
                            'verificationStatus': 'see_existing_curated_review' if lead['status'] == 'already_curated' else 'pending'}
        lead['matches'] = {'airportIds': airports if lead['status'] == 'already_curated' else [],
                           'codeOnlyPossibleAirportIds': airports,
                           'assignmentIds': sorted(a['assignmentId'] for a in assignments),
                           'nameIds': sorted(n['nameId'] for n in dataset['names'] if n['airportId'] in airports)}
        lead['review'] = {'status': lead['status'], 'conflicts': lead['conflicts'],
                          'exclusionReason': lead['exclusionReason'], 'nextAction': lead['nextAction'],
                          'evidenceGaps': ['See original claim-specific evidence review; no new evidence promotion.']}
    write_jsonl(out / 'legacy-links.jsonl.gz', legacy)
    return legacy


def verification_queue(config, out):
    queue = []
    for source in config['sources']:
        for row in read_candidates(out, source['id']):
            changes = row['changes']
            has_iata = any(changes.get('iata', [])) or any(len(c) == 3 and c.isalpha() for c in row['context']['codes'])
            score, reasons = 0, []
            for field in ('iata', 'icao'):
                values = changes.get(field, [])
                if len(values) == 2 and all(values):
                    score += 60
                    reasons.append(field + '_replacement_observation')
            if has_iata and 'possible_relocation' in row['types']:
                score += 60
                reasons.append('coded_record_coordinate_shift_over_5km')
            if has_iata and 'possible_closure' in row['types']:
                score += 50
                reasons.append('coded_record_closure_observation')
            if has_iata and 'possible_reopening' in row['types']:
                score += 50
                reasons.append('coded_record_reopening_observation')
            if score < 50:
                continue
            if source['id'] in ('ourairports', 'airport-codes-raw'):
                score += 10
                reasons.append('numeric_external_entity_id_available')
            queue.append({'candidateId': row['candidateId'], 'sourceId': source['id'],
                          'sourceEntityId': row['sourceEntityId'], 'priorityScore': score,
                          'reasons': reasons, 'context': row['context'], 'types': row['types'],
                          'firstObservedAt': row['time']['firstObservedRevisionAt'],
                          'matches': row['matches'], 'status': row['review']['status']})
    queue.sort(key=lambda r: (-r['priorityScore'], r['firstObservedAt'], r['candidateId']))
    write_jsonl(out / 'verification-queue.jsonl.gz', queue)
    return {'count': len(queue), 'firstBatch': queue[:20],
            'meaning': 'Heuristic research priority only; source corrections and duplicates still require review.'}


def exact_duplicate_groups(config, out):
    identifiers = defaultdict(set)
    numeric_sources = {'ourairports', 'airport-codes-raw', 'airport-codes-initial'}
    for sid in sorted(numeric_sources):
        for row in read_jsonl(out / (sid + '.entities.jsonl.gz')):
            entity = row['sourceEntityId']
            ident = row['reference']['row'].get('ident')
            if entity.isdigit() and ident:
                identifiers[ident].add(entity)
    groups = defaultdict(list)
    for source in config['sources']:
        sid = source['id']
        if sid not in numeric_sources | {'airport-codes'}:
            continue
        for row in read_candidates(out, sid):
            entity = row['sourceEntityId']
            if sid == 'airport-codes':
                choices = identifiers.get(entity, set())
                if len(choices) != 1:
                    continue
                entity = next(iter(choices))
            if not entity.isdigit():
                continue
            gid = stable_id('dup_', ['ourairports-external-id', entity, row['changes']])
            groups[gid].append({'candidateId': row['candidateId'], 'sourceId': sid,
                                'sourceEntityId': row['sourceEntityId']})
    result = [{'eventGroupId': gid, 'members': sorted(members, key=lambda r:r['candidateId']),
               'basis': 'Same numeric OurAirports external identity and identical normalized raw field transition; derived ident mapped only when unique.',
               'meaning': 'Duplicate research transition, not a proven historical event. Recurring episodes retain their separate observations in member records.'}
              for gid, members in sorted(groups.items()) if len({m['sourceId'] for m in members}) > 1]
    write_jsonl(out / 'duplicate-groups.jsonl.gz', result)
    return {'groups': len(result), 'memberCandidates': sum(len(r['members']) for r in result),
            'duplicateCandidateExcess': sum(len(r['members'])-1 for r in result)}


def compare(out):
    baseline = json.loads((ROOT / 'research/discovery/keepraw-fly-baseline.json').read_text())
    raw = (ROOT / baseline['inputPath']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != baseline['sha256']:
        raise ValueError('Keepraw-Fly baseline checksum mismatch')
    fly = {r[0]: r for r in json.loads(raw)}
    oa = list(read_jsonl(out / 'ourairports.entities.jsonl.gz'))
    current = [normalized(r['reference']['row']) for r in oa if r['presentAtTarget']]
    codes = defaultdict(list)
    for row in current:
        if row.get('iata'):
            codes[row['iata']].append(row)
    shared = set(codes) & set(fly)
    differences = []
    for code in sorted(shared):
        row = fly[code]
        entries = codes[code]
        differences.append({'iata': code, 'ourAirportsIds': [r['id'] for r in entries],
                            'nameDiffers': any(r['name'] != row[1] for r in entries),
                            'countryDiffers': any(r.get('country') != row[3] for r in entries),
                            'distanceKm': [distance(r, {'lat': row[4], 'lon': row[5]}) for r in entries],
                            'closedInOurAirports': any(r.get('type') == 'closed' for r in entries)})
    write_jsonl(out / 'keepraw-fly-differences.jsonl.gz', differences)
    report = {k:v for k,v in baseline.items() if k != 'airports'}
    report.update({'sharedIataCodes': len(shared), 'ourAirportsUniqueIataCodes': len(codes),
                   'onlyOurAirportsIataCodes': sorted(set(codes)-set(fly)),
                   'onlyKeeprawFlyIataCodes': sorted(set(fly)-set(codes)),
                   'nameDifferences': sum(r['nameDiffers'] for r in differences),
                   'countryDifferences': sum(r['countryDiffers'] for r in differences),
                   'coordinateDifferencesOver5Km': sum(any(x is not None and x >= 5 for x in r['distanceKm']) for r in differences),
                   'sharedCodesWithClosedRows': sum(r['closedInOurAirports'] for r in differences),
                   'meaning': 'Current-directory comparison of different pinned snapshots, not validated historical events.'})
    write_json(out / 'keepraw-fly-comparison.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output
    config = json.loads((ROOT / 'research/discovery/sources.json').read_text())
    reports = [json.loads((out / (s['id'] + '.coverage.json')).read_text()) for s in config['sources']]
    regional_coverage(config, out)
    links = code_links(config, out)
    legacy = legacy_links(config, out)
    priority = verification_queue(config, out)
    duplicates = exact_duplicate_groups(config, out)
    comparison = compare(out)
    types, countries, years, statuses = (Counter() for _ in range(4))
    for report in reports:
        for counter, field in [(types, 'byType'), (countries, 'byCountry'), (years, 'byObservationYear'), (statuses, 'byStatus')]:
            counter.update(report['discovery'][field])
    summary = {'formatVersion': 1, 'sourceCount': len(reports),
               'sourceRevisionCandidates': sum(r['discovery']['candidates'] for r in reports),
               'rawSourceCandidateObservations': sum(r['discovery']['rawCandidateObservations'] for r in reports),
               'codeAssociationCandidates': len(links), 'preservedLegacyLeads': len(legacy),
               'sourceCandidatesByType': dict(sorted(types.items())),
               'sourceCandidatesByCountry': dict(sorted(countries.items())),
               'sourceCandidatesByObservationYear': dict(sorted(years.items())),
               'sourceCandidatesByStatus': dict(sorted(statuses.items())),
               'codeAssociationCandidatesBySource': dict(sorted(Counter(r['sourceId'] for r in links).items())),
               'codeAssociationCandidatesByScheme': dict(sorted(Counter(r['scheme'] for r in links).items())),
               'codeAssociationCandidatesByCountry': dict(sorted(Counter(c for r in links for c in r['context']['countries']).items())),
               'codeAssociationEventYearUnknown': len(links),
               'legacyLeadsByStatus': dict(sorted(Counter(r['status'] for r in legacy).items())),
               'warnings': ['Counts are research leads, not historical event totals or global completion percentages.',
                            'Sources overlap; cross-source-code-index groups work by code without claiming event equivalence.',
                            'Types are multi-label; year means first observed repository revision, not event year.',
                            'Country counts follow each source; continent may be unknown. No regional completeness is inferred.'],
               'sources': reports, 'currentDirectoryComparison': comparison}
    summary['verificationQueue'] = priority
    summary['exactCrossSourceDuplicateGroups'] = duplicates
    summary['sourceTransitionLeadsAfterExactCrossSourceGrouping'] = summary['sourceRevisionCandidates'] - duplicates['duplicateCandidateExcess']
    write_json(out / 'summary.json', summary)
    manifest = {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                for p in sorted(out.iterdir()) if p.is_file() and p.name != 'manifest.json'}
    inputs = [*sorted((ROOT / 'research/discovery').glob('*.json')),
              *sorted((ROOT / 'scripts/discovery').glob('*.py'))]
    write_json(out / 'manifest.json', {'formatVersion': 1, 'files': manifest,
                                      'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}})
    print(canonical({k: v for k, v in summary.items() if k not in ('sources', 'currentDirectoryComparison', 'verificationQueue')}))


if __name__ == '__main__':
    main()
