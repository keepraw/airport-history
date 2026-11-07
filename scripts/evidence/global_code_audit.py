"""Audit the global research round offline; metadata is not source/admission authority.

Default builds three deterministic reports. --check reproduces their exact bytes.
--originals additionally replays retained private raw/extracted/normalized hashes;
private bytes are deliberately not required by offline CI and are never fetched.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'research/evidence/global-code-expansion'
BASE_COMMIT = '7d21ff6762e1569faa1be19c8203e577420cd1f2'
REGIONS = ('asia', 'europe', 'americas-africa')
HASH = re.compile(r'^[0-9a-f]{64}$')
OUTPUTS = ('research-summary.json', 'remaining-high-value-queue.jsonl.gz', 'validation.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def ranked_rows():
    manifest = load(DIRECTORY / 'ranked-events.manifest.json')
    require(manifest['formatVersion'] == 1 and manifest['maxUncompressedBytesPerShard'] <= 8 * 1024 * 1024,
            'Invalid bounded ranking manifest')
    seen, count, total = set(), 0, 0
    aggregate = hashlib.sha256()
    for entry in manifest['files']:
        name = entry['path']
        require(re.fullmatch(r'ranked-events\.\d{3}\.jsonl\.gz', name) and name not in seen,
                'Invalid or repeated ranking shard')
        seen.add(name)
        path = DIRECTORY / name
        require(digest(path) == entry['sha256'] and path.stat().st_size == entry['bytes'],
                'Changed ranking shard: ' + name)
        shard_hash, shard_bytes, shard_count = hashlib.sha256(), 0, 0
        first_rank = count + 1
        with gzip.open(path, 'rb') as stream:
            for line in stream:
                shard_hash.update(line); aggregate.update(line)
                shard_bytes += len(line); total += len(line)
                shard_count += 1; count += 1
                row = json.loads(line)
                require(row['rank'] == count, 'Ranking shard order or completeness changed')
                yield row
        require(shard_count == entry['recordCount'] and shard_bytes == entry['uncompressedBytes'] and
                shard_bytes <= manifest['maxUncompressedBytesPerShard'] and
                shard_hash.hexdigest() == entry['uncompressedSha256'] and
                first_rank == entry['firstRank'] and count == entry['lastRank'],
                'Invalid decompressed ranking shard receipt: ' + name)
    require(count == manifest['recordCount'] == 88330 and total == manifest['totalUncompressedBytes'] and
            aggregate.hexdigest() == manifest['uncompressedSha256'], 'Incomplete full ranking stream')


def root_path(value, relative=None):
    path = Path(value)
    if not path.is_absolute():
        path = (ROOT if value.startswith(('research/', 'work/', 'scripts/', 'test/')) else relative or ROOT) / path
    path = path.resolve()
    require(path.is_relative_to(ROOT), f'Path escapes repository: {value}')
    return path


def all_records(value, source_id):
    found = []
    if isinstance(value, dict):
        if value.get('sourceId') == source_id:
            found.append(value)
        if source_id in value and isinstance(value[source_id], dict):
            found.append({'sourceId': source_id, **value[source_id]})
        for item in value.values():
            found.extend(all_records(item, source_id))
    elif isinstance(value, list):
        for item in value:
            found.extend(all_records(item, source_id))
    return found


def first(record, *keys):
    return next((record[k] for k in keys if record.get(k) is not None), None)


def acquired(record):
    return record.get('accessResult') in ('content_inspected', 'original_acquired', 'acquired') and bool(record.get('originalSha256'))


def source_family(record):
    return first(record, 'sourceFamily', 'family', 'independenceKey') or 'family_not_established'


def validate_span(span, source_id):
    if 'quote' not in span:
        return
    start = first(span, 'characterStart', 'normalizedCharacterStart')
    end = first(span, 'characterEnd', 'normalizedCharacterEnd')
    if start is not None and end is not None:
        require(type(start) is int and type(end) is int and end - start == len(span['quote']), f'Bad citation span: {source_id}')
    if span.get('quoteSha256'):
        require(hashlib.sha256(span['quote'].encode()).hexdigest() == span['quoteSha256'], f'Bad quote hash: {source_id}')


def audit_source_files(region, originals):
    directory = DIRECTORY / region
    source_path = next((directory / name for name in ('source-lock.json', 'source-acquisition.json', 'sources.json') if (directory / name).exists()), None)
    require(source_path is not None, f'Missing source register: {region}')
    source_doc = load(source_path)
    sources = source_doc.get('sources', [])
    require(isinstance(sources, list), f'Invalid source register: {region}')
    source_map = {}
    counts = Counter()
    raw_hashes = set()
    private_replayed = 0
    for source in sources:
        sid = source['sourceId']
        require(sid not in source_map, f'Duplicate new source ID: {region}/{sid}')
        source_map[sid] = source
        counts[source.get('accessResult', 'unspecified')] += 1
        for key in ('originalSha256', 'textOriginalSha256', 'extractedTextSha256', 'normalizedTextSha256'):
            if source.get(key) is not None:
                require(bool(HASH.fullmatch(source[key])), f'Bad source hash: {sid}/{key}')
        if source.get('excerptPath'):
            path = root_path(source['excerptPath'], source_path.parent)
            require(path.exists() and digest(path) == source['excerptSha256'], f'Bad excerpt hash: {sid}')
            excerpt = load(path)
            for hash_key in ('originalSha256', 'textOriginalSha256', 'extractedTextSha256', 'normalizedTextSha256'):
                if source.get(hash_key) and excerpt.get(hash_key):
                    require(source[hash_key] == excerpt[hash_key], f'Detached excerpt source: {sid}/{hash_key}')
            for span in excerpt.get('spans', excerpt.get('citations', [])):
                validate_span(span, sid)
        for span in source.get('spans', source.get('citations', [])):
            validate_span(span, sid)
        if acquired(source):
            require(source.get('extractedTextSha256') or source.get('textOriginalSha256'), f'Missing extraction hash: {sid}')
            require(source.get('normalizedTextSha256'), f'Missing normalization hash: {sid}')
            require(source.get('rights') or source.get('license'), f'Missing rights assessment: {sid}')
            raw_hashes.add(source['originalSha256'])
            if originals:
                for path_key, hash_keys in (
                    ('privateOriginalPath', ('originalSha256',)),
                    ('privateExtractedTextPath', ('extractedTextSha256', 'textOriginalSha256')),
                    ('privateNormalizedTextPath', ('normalizedTextSha256',))):
                    value = source.get(path_key)
                    require(value, f'Missing private replay path: {sid}/{path_key}')
                    path = root_path(value)
                    require(path.is_relative_to(ROOT / 'work'), f'Private bytes outside ignored work: {sid}')
                    require(path.exists() and digest(path) == first(source, *hash_keys), f'Private hash mismatch: {sid}/{path_key}')
                private_replayed += 1
    reuse_path = next((directory / name for name in ('reuse-receipts.json', 'reused-evidence.json') if (directory / name).exists()), None)
    reused = []
    if reuse_path:
        reused = load(reuse_path).get('sources', [])
        for source in reused:
            sid = source['sourceId']
            receipt_path = root_path(first(source, 'sourceLockPath', 'receiptPath'))
            expected = first(source, 'sourceLockSha256', 'receiptFileSha256')
            require(expected and digest(receipt_path) == expected, f'Changed reused receipt: {region}/{sid}')
            matching = all_records(load(receipt_path), sid)
            require(matching, f'Reused source ID absent: {region}/{sid}')
            if source.get('sourceRecordSha256'):
                require(any(hashlib.sha256(canonical(row).encode()).hexdigest() == source['sourceRecordSha256'] for row in matching), f'Changed reused source record: {region}/{sid}')
            if source.get('originalSha256'):
                require(any(source['originalSha256'] in canonical(row) for row in matching), f'Detached reused original hash: {region}/{sid}')
            for reference_key in ('citationReference', 'catalogReference'):
                reference = source.get(reference_key)
                if reference:
                    path = root_path(reference['path'])
                    require(path.exists() and digest(path) == reference['sha256'], f'Changed reused {reference_key}: {region}/{sid}')
            if source.get('excerptPath'):
                path = root_path(source['excerptPath'], receipt_path.parent)
                require(path.exists() and digest(path) == source['excerptSha256'], f'Changed reused excerpt: {region}/{sid}')
            require(source.get('originalBytesReplayedHere') is not True and source.get('rawBytesReverifiedThisRun') is not True, f'Reuse falsely claims new raw replay: {region}/{sid}')
    return {'sourcePath': source_path.relative_to(ROOT).as_posix(), 'sourceSha256': digest(source_path),
            'reusePath': reuse_path.relative_to(ROOT).as_posix() if reuse_path else None,
            'reuseSha256': digest(reuse_path) if reuse_path else None,
            'accessResultCounts': dict(sorted(counts.items())), 'sources': sources, 'sourceMap': source_map,
            'reused': reused, 'rawHashes': raw_hashes, 'privateReplayed': private_replayed}


def protected_inputs():
    prefixes = ('scripts', 'src', 'schema', 'test', 'research', 'admission', 'pnpm-lock.yaml')
    listed = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', BASE_COMMIT, '--', *prefixes], cwd=ROOT).decode().rstrip('\0').split('\0')
    original = set(listed)
    changed = subprocess.check_output(['git', 'diff', '--name-only', '-z', BASE_COMMIT, '--', *prefixes], cwd=ROOT).decode().rstrip('\0').split('\0')
    allowed = {'scripts/evidence/current_project_admission.py'}
    forbidden = sorted(path for path in changed if path in original and path not in allowed)
    require(not forbidden, 'Protected published input changed: ' + ', '.join(forbidden))
    proposal = load(DIRECTORY / 'policy/proposal.json')
    checks = proposal.get('preservedAuthorityFiles', {})
    if isinstance(checks, list):
        checks = {row['path']: row['sha256'] for row in checks}
    for path, value in checks.items():
        expected = value.get('sha256') if isinstance(value, dict) else value
        require(digest(ROOT / path) == expected, f'Protected authority hash changed: {path}')
    return {'baselineCommit': BASE_COMMIT, 'preexistingProtectedInputs': len(original),
            'permittedCurrentVersionDispatchOnly': sorted(path for path in changed if path in original and path in allowed),
            'changedProtectedInputs': [], 'policyAuthorityFilesVerified': len(checks),
            'meaning': 'All pre-existing research, source, schema, tests, grants and executors remain byte-identical except the current-version dispatcher.'}


def formal_diff():
    base = load(ROOT / 'test/curated-0.11.0.json')
    candidate = load(ROOT / 'data/airports.json')
    for collection in ('airports', 'assignments', 'sources', 'names'):
        require(candidate[collection][:len(base[collection])] == base[collection], f'Published {collection} modified')
    additions = {collection: candidate[collection][len(base[collection]):] for collection in ('airports', 'assignments', 'sources', 'names')}
    return {'publishedMainBaseline': {'commit': BASE_COMMIT, 'dataVersion': base['dataVersion'], 'sha256': digest(ROOT / 'test/curated-0.11.0.json')},
            'reviewableWorkingTreeProposal': {'dataVersion': candidate['dataVersion'], 'sha256': digest(ROOT / 'data/airports.json'),
                'newIataAssignments': sum(a['scheme'] == 'IATA' for a in additions['assignments']),
                'newIcaoAssignments': sum(a['scheme'] == 'ICAO' for a in additions['assignments']),
                'newPhysicalAirports': len(additions['airports']), 'newSources': len(additions['sources']),
                'newHistoricalNames': len(additions['names']), 'assignmentIds': [a['assignmentId'] for a in additions['assignments']]},
            'mergedProductionGrowth': {'newIataAssignments': 0, 'newIcaoAssignments': 0, 'newResolvedQueries': 0,
                'newResolvedCrossSiteReuses': 0, 'uncertainIntervalsNarrowed': 0,
                'reason': 'No automatic merge is authorized. This report describes an unmerged PR proposal against the fixed published baseline.'}}


def audit_resolver(studied, aliases, ranking):
    path = DIRECTORY / 'resolver-input.json'
    require(path.exists(), 'Missing production resolver input matrix')
    matrix = load(path)
    require(matrix['baselinePath'] == 'test/curated-0.11.0.json' and
            matrix['baselineSha256'] == digest(ROOT / matrix['baselinePath']) and
            matrix['formalSha256'] == digest(ROOT / 'data/airports.json') and
            matrix['publishedBaselineCommit'] == BASE_COMMIT and
            matrix['publicationState'] == 'unmerged_data_PR_candidate',
            'Resolver input changes baseline or publication state')
    expected_inputs = {str((DIRECTORY / region / 'assessments.json').relative_to(ROOT)) for region in REGIONS}
    require(set(matrix['assessmentInputs']) == expected_inputs, 'Incomplete resolver assessment inputs')
    for name, sha in matrix['assessmentInputs'].items():
        require(digest(ROOT / name) == sha, f'Stale resolver assessment: {name}')
    primary_ids, assignment_ids = [], []
    batches = {}
    for batch in matrix['batches']:
        bid = batch['batchId']
        require(bid not in batches, f'Duplicate resolver batch: {bid}')
        ids = batch['eventGroupIds']
        require(0 < len(ids) <= 20 and len(ids) == len(set(ids)), f'Invalid resolver batch group count: {bid}')
        require(all(gid in studied for gid in ids), f'Resolver batch counts an alias as a primary case: {bid}')
        primary_ids.extend(ids)
        claims_path = root_path(batch['claimsPath'])
        claims = load(claims_path)
        new_ids = [a['assignmentId'] for a in claims['assignments']]
        require(len(new_ids) == len(set(new_ids)), f'Duplicate resolver assignment in {bid}')
        assignment_ids.extend(new_ids)
        for source in claims['sources']:
            require(source['verificationStatus'] == 'pending', f'Research candidate source falsely verified: {source["sourceId"]}')
        for assignment in claims['assignments']:
            require(assignment['verificationStatus'] == 'pending' and assignment['verifiedOn'] is None,
                    f'Research assignment falsely verified: {assignment["assignmentId"]}')
        for claim in claims.get('claims', []):
            gid = claim.get('eventGroupId')
            if gid is not None:
                require(gid in ids or any(parent in ids and ranking[gid].get('referenceId') is not None and ranking[gid].get('referenceId') == ranking[parent].get('referenceId') for parent in aliases.get(gid, [])),
                        f'Resolver candidate linked to wrong canonical batch/site: {bid}/{gid}')
        conditional = batch.get('conditionalReview')
        if conditional:
            require(set(conditional['assignmentIds']) <= set(new_ids) and conditional.get('remainingBlockers'),
                    f'Unqualified conditional review declaration: {bid}')
        batches[bid] = {'input': batch, 'claimsSha256': digest(claims_path)}
    require(len(primary_ids) == len(set(primary_ids)) and set(primary_ids) == set(studied),
            'Resolver matrix omits or duplicates canonical cases')
    require(len(assignment_ids) == len(set(assignment_ids)), 'Resolver candidate assignment reused across batches')
    diff_path = DIRECTORY / 'resolver-diff.json'
    report = load(diff_path)
    require(report['baseline']['sha256'] == matrix['baselineSha256'] and
            report['formal']['sha256'] == matrix['formalSha256'], 'Stale resolver data fingerprints')
    require({row['batchId'] for row in report['batches']} == set(batches), 'Resolver reports incomplete batch matrix')
    for row in report['batches']:
        expected = batches[row['batchId']]
        require(row['claimsSha256'] == expected['claimsSha256'] and
                row['eventGroupIds'] == expected['input']['eventGroupIds'] and
                set(row['comparisons']) == {'IATA', 'ICAO', 'IATA+ICAO'},
                f'Stale or incomplete resolver candidate comparison: {row["batchId"]}')
    formal = report['formalComparison']
    require(formal['changedResolvedAnswers'] == formal['changedExistingAnswers'] == formal['newConflicts'] == 0,
            'Proposed formal data changes published resolution or conflicts')
    coverage_path = ROOT / 'research/admissions/0.12.0/coverage.json'
    authoritative = load(coverage_path)
    require(formal['newResolved'] == authoritative['newResolvedQueries'] == 81 and
            formal['uncertainToResolved'] == authoritative['uncertainToResolved'] == 0 and
            formal['notFoundToResolved'] == authoritative['notFoundToResolved'] == 81 and
            formal['newlyResolvedCrossSiteReuseCodes'] == [],
            'Global resolver partition measurement differs from unchanged AAI daily gate measurement')
    return {'inputSha256': digest(path), 'reportSha256': digest(diff_path),
            'canonicalCases': len(primary_ids), 'batches': len(batches),
            'candidateAssignmentsPreservedPending': len(assignment_ids),
            'separateIataIcaoCombinedComparisonsComplete': True,
            'authoritativeAaiDailyCoverageSha256': digest(coverage_path),
            'proposedNewResolvedQueries': formal['newResolved'],
            'proposedUncertainToResolved': formal['uncertainToResolved'],
            'proposedNotFoundToResolved': formal['notFoundToResolved'],
            'newConflicts': formal['newConflicts'], 'changedExistingAnswers': formal['changedExistingAnswers'],
            'mainProductionNewResolvedUntilMerge': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--originals', action='store_true')
    args = parser.parse_args()
    screen = load(DIRECTORY / 'screening-summary.json')
    manifest = load(DIRECTORY / 'screening-manifest.json')
    for category in ('inputs', 'outputs'):
        for name, receipt in manifest[category].items():
            path = ROOT / name if category == 'inputs' else DIRECTORY / name
            require(path.exists() and digest(path) == receipt['sha256'] and path.stat().st_size == receipt['bytes'], f'Screening fingerprint changed: {name}')
    ranking = {row['eventGroupId']: row for row in ranked_rows()}
    require(len(ranking) == screen['eventGroupsRanked'] == 88330, 'Incomplete global event ranking')
    high = [r for r in ranking.values() if r['priorityTier'] == 'high']
    require(len(high) == screen['highValueGroups'], 'High-value ranking count changed')
    acquired_hashes, reused_hashes, issuer_families = set(), set(), set()
    studied, aliases = {}, defaultdict(list)
    airport_reference_units, possible_location_units, acquisition_clusters = set(), set(), set()
    regions = {}
    source_reports = {}
    evidence_ids = set()
    input_fingerprints = {}
    duplicate_incidents = []
    family_sources, family_new_hashes, family_access_results = defaultdict(set), defaultdict(set), defaultdict(Counter)
    for region in REGIONS:
        directory = DIRECTORY / region
        assessment_path = directory / 'assessments.json'
        require(assessment_path.exists(), f'Missing completed research assessments: {region}')
        document = load(assessment_path)
        events = document.get('cases', document.get('events', []))
        require(events, f'Empty research assessment: {region}')
        source_info = audit_source_files(region, args.originals)
        source_reports[region] = {key: value for key, value in source_info.items() if key not in ('sources', 'sourceMap', 'reused', 'rawHashes')}
        acquired_hashes.update(source_info['rawHashes'])
        for source in source_info['sources']:
            family = source_family(source)
            family_sources[family].add(source['sourceId'])
            family_access_results[family][source.get('accessResult', 'unspecified')] += 1
            if acquired(source):
                family_new_hashes[family].add(source['originalSha256'])
        for source in [*source_info['sources'], *source_info['reused']]:
            if source.get('originalSha256') and source in source_info['reused']:
                reused_hashes.add(source['originalSha256'])
            if acquired(source) or source in source_info['reused']:
                issuer_families.add(source_family(source))
            if source.get('accessResult', '').startswith('duplicate_retrieval') or source.get('duplicateRetrieval') or source.get('duplicateOf') or source.get('previouslyLockedOriginal'):
                duplicate_incidents.append({'region': region, 'sourceId': source['sourceId'],
                    'originalSha256': source.get('originalSha256'),
                    'detail': first(source, 'incident', 'duplicateRetrieval', 'duplicateOf', 'previouslyLockedOriginal')})
        counts = Counter()
        countries = set()
        regional_airport_units = set()
        regional_location_units = set()
        for event in events:
            gid = event['eventGroupId']
            require(gid in ranking and gid not in studied, f'Unknown or duplicated canonical group: {gid}')
            ranked = ranking[gid]
            airport_unit = ranked.get('referenceId') or f"unmatched:{ranked['country']}:{ranked['researchClusterKey']}"
            airport_reference_units.add(airport_unit); regional_airport_units.add(airport_unit)
            acquisition_clusters.add(ranked['researchClusterKey'])
            for site in ranked.get('candidatePhysicalSites', []):
                site_unit = site.get('locationId') or canonical([site.get('referenceId'), site.get('coordinates')])
                possible_location_units.add(site_unit); regional_location_units.add(site_unit)
            status = event.get('researchStatus', '')
            evidence = status in ('original_or_locked_evidence_inspected', 'official_original_or_locked_evidence_inspected')
            require(event.get('nextAction'), f'Missing concrete next action: {gid}')
            declared = event.get('globalRanking', {})
            if declared:
                require(declared['rank'] == ranked['rank'] and declared['priorityTier'] == ranked['priorityTier'], f'Stale ranking join: {gid}')
            if event.get('globalRank') is not None:
                require(event['globalRank'] == ranked['rank'], f'Stale Asia ranking join: {gid}')
            if evidence:
                require(event.get('sourceIds') or event.get('newSourceIds') or event.get('reusedSourceIds'), f'No inspected source linkage: {gid}')
                evidence_ids.add(gid)
            is_high = ranked['priorityTier'] == 'high'
            counts['canonicalEventGroupsInvestigated'] += 1
            counts['highValueEventGroupsInvestigated'] += is_high
            counts['originalOrLockedEvidenceCases'] += evidence
            counts['highValueOriginalOrLockedEvidenceCases'] += is_high and evidence
            counts['highValueAccessOrDirectoryOnlyCases'] += is_high and not evidence
            countries.add(event['country'])
            studied[gid] = {'region': region, 'event': event, 'evidence': evidence, 'ranked': ranked}
            for alias in event.get('relatedEventGroupIds', []):
                require(alias in ranking and alias != gid, f'Unknown/self related group: {gid}/{alias}')
                aliases[alias].append(gid)
        regions[region] = {**dict(counts), 'countries': sorted(countries), 'countryCount': len(countries),
            'candidateAirportReferenceUnits': len(regional_airport_units), 'candidateLocationHypotheses': len(regional_location_units),
            'assessmentPath': assessment_path.relative_to(ROOT).as_posix(), 'assessmentSha256': digest(assessment_path)}
        for path in sorted(directory.rglob('*.json')):
            input_fingerprints[path.relative_to(ROOT).as_posix()] = digest(path)
        batches_path = directory / 'review-batches.json'
        batches = load(batches_path).get('batches', [])
        batch_groups = []
        for batch in batches:
            ids = batch.get('eventGroupIds', [])
            require(0 < len(ids) <= 20, f'Invalid review batch size: {batch.get("batchId")}')
            batch_groups.extend(ids)
        require(len(batch_groups) == len(set(batch_groups)) and set(batch_groups) == {e['eventGroupId'] for e in events}, f'Incomplete or duplicated research batches: {region}')
    high_evidence = {gid for gid in evidence_ids if ranking[gid]['priorityTier'] == 'high'}
    high_investigated = {gid for gid in studied if ranking[gid]['priorityTier'] == 'high'}
    require(len(high_evidence) >= 50, f'First round requires at least50 high-value groups with inspected original/locked evidence, got{len(high_evidence)}')
    # Known accidental duplicate retrieval is disclosed once and never added to the new-original count.
    old_faa = load(ROOT / 'research/evidence/global-batch-5/source-lock.json')
    old_faa_rows = all_records(old_faa, 'b5-us-dtpp-2611')
    require(len(old_faa_rows) == 1, 'Missing prior FAA source receipt')
    old_faa_hash = old_faa_rows[0]['originalSha256']
    if old_faa_hash in acquired_hashes:
        duplicate_incidents = [row for row in duplicate_incidents if row.get('originalSha256') != old_faa_hash]
        duplicate_incidents.append({'region': 'americas-africa', 'sourceId': 'b5-us-dtpp-2611',
            'originalSha256': old_faa_hash, 'priorReceipt': 'research/evidence/global-batch-5/source-lock.json',
            'detail': 'One already-locked FAA2611 XML original was inadvertently downloaded again during source discovery; exact byte equality was checked, old provenance reused, and it is excluded from new-original counts.'})
        reused_hashes.add(old_faa_hash)
    new_hashes = acquired_hashes - reused_hashes
    proposal = formal_diff()
    resolver = audit_resolver(studied, aliases, ranking)
    proposal['reviewableWorkingTreeProposal']['resolverMeasurement'] = resolver
    candidate_codes = {a['code'] for a in load(ROOT / 'data/airports.json')['assignments'][len(load(ROOT / 'test/curated-0.11.0.json')['assignments']):]}
    queue = []
    states = Counter()
    for ranked in high:
        gid = ranked['eventGroupId']
        record = studied.get(gid)
        related = sorted(set(aliases.get(gid, [])))
        if record:
            event = record['event']
            state = 'evidence_researched_followup' if record['evidence'] else 'access_directory_or_discovery_blocked'
            next_action = event['nextAction']
            if candidate_codes.intersection(ranked['ICAO']):
                state = 'authorized_formal_data_proposal_pending_merge'
            canonical_groups = [gid]
        elif related:
            state = 'code_linked_observation_requires_distinct_event_review'
            next_action = 'Use the linked code-based research as navigation, without assuming the same event or physical site; inspect distinct claim ownership and reuse a receipt only when it actually supports that site/code.'
            canonical_groups = related
        else:
            state = 'not_yet_evidence_researched'
            next_action = 'Acquire the ranked missing originals by issuer/source cluster; establish physical site and independent namespace timing, then apply the applicable source-family policy.'
            canonical_groups = []
        states[state] += 1
        queue.append({'rank': ranked['rank'], 'eventGroupId': gid, 'candidateId': ranked['candidateId'],
            'country': ranked['country'], 'airport': ranked['airport'], 'researchClusterKey': ranked['researchClusterKey'],
            'IATA': ranked['IATA'], 'ICAO': ranked['ICAO'], 'priorityScore': ranked['priorityScore'],
            'queueState': state, 'canonicalResearchEventGroupIds': canonical_groups,
            'missingOriginals': ranked['missingOriginals'], 'officialSourceDiscoveryUrls': ranked['officialSourceDiscoveryUrls'],
            'nextAction': next_action, 'formalCoverageClaimed': False})
    protected = protected_inputs()
    public_paths = [p for p in DIRECTORY.rglob('*') if p.is_file()]
    disallowed = [str(p.relative_to(ROOT)) for p in public_paths if p.suffix.lower() in {'.pdf', '.html', '.htm', '.txt', '.xml', '.png', '.jpg'}]
    require(not disallowed, 'Original/extraction bytes in public research artifacts: ' + ', '.join(disallowed))
    countries = sorted({record['event']['country'] for record in studied.values()})
    evidence_countries = sorted({record['event']['country'] for record in studied.values() if record['evidence']})
    for path in (DIRECTORY / 'screening-summary.json', DIRECTORY / 'screening-manifest.json', DIRECTORY / 'policy/proposal.json', DIRECTORY / 'resolver-input.json', DIRECTORY / 'resolver-diff.json', ROOT / 'research/admissions/0.12.0/coverage.json', ROOT / 'data/airports.json', ROOT / 'test/curated-0.11.0.json', ROOT / 'scripts/evidence/global_code_audit.py'):
        input_fingerprints[path.relative_to(ROOT).as_posix()] = digest(path)
    summary = {'formatVersion': 1, 'reviewedOn': '2026-11-07',
        'screening': {key: screen[key] for key in ('sourceRevisionCandidatesInspected', 'selectedCandidatesJoined', 'eventGroupsRanked',
            'codeAssociationCandidatesRanked', 'geographicReuseLeadsRanked', 'highValueGroups', 'highValueResearchClusters')},
        'countingRule': 'One primary eventGroupId per substantively reviewed case. Related directory aliases are linked but never inflate researched counts. Directory-only and access/discovery-blocked cases are excluded from the50-group original/locked-evidence target.',
        'research': {'canonicalEventGroupsInvestigated': len(studied), 'highValueEventGroupsInvestigated': len(high_investigated),
            'highValueEventGroupsWithOriginalOrLockedEvidenceInspected': len(high_evidence),
            'originalOrLockedEvidenceCases': len(evidence_ids), 'relatedObservationGroupIds': len(aliases),
            'candidateAirportReferenceUnits': len(airport_reference_units), 'candidateLocationHypotheses': len(possible_location_units),
            'acquisitionClusters': len(acquisition_clusters),
            'airportUnitDefinition': 'Distinct primary referenceId among reviewed canonical cases; unmatched cases use country plus acquisition-cluster key. Directory reference records are research units, not verified physical-airport counts. Separate possible locationIds remain hypotheses and are not automatically treated as relocations.',
            'countries': countries, 'countryCount': len(countries),
            'countriesWithOriginalOrLockedEvidenceReview': evidence_countries, 'countryCountWithOriginalOrLockedEvidenceReview': len(evidence_countries),
            'countryCountingRule': 'Targeted countries include access-only or directory-only cases. Substantive-evidence countries require at least one canonical case with inspected official/carrier originals or locked evidence receipts.',
            'remainingHighValueGroupsWithoutCompletedPrimaryEvidenceReview': len(high) - len(high_evidence),
            'remainingHighValueGroupsNotYetInvestigatedAsCanonicalCases': len(high) - len(high_investigated),
            'byRegion': regions},
        'evidenceAcquisition': {'newDistinctOriginalByteSequences': len(new_hashes),
            'newSourceAcquisitionByFamily': {family: {'sourceRecords': len(family_sources[family]), 'distinctNewOriginalHashes': len(family_new_hashes[family] - reused_hashes), 'accessResultCounts': dict(sorted(family_access_results[family].items()))} for family in sorted(family_sources)},
            'sourceCountCaveat': 'New originals include source navigation/version-control documents as well as airport evidence. Original counts are acquisition accounting, not code coverage or independent confirmations.',
            'distinctReusedOriginalHashesAvailable': len(reused_hashes), 'issuerFamilyKeys': sorted(issuer_families),
            'issuerFamilyCountCaveat': 'Family keys preserve regional registries and are not a count of independent corroborating publishers. Different editions/URLs of one issuer remain one source family.',
            'newOriginalCountExcludesPreviouslyLockedByteSequences': True, 'duplicateRetrievalIncidents': duplicate_incidents,
            'originalCustody': 'Complete originals and extractions remain only in ignored work/. Offline CI checks receipts and citations without claiming fresh original retrieval.'},
        'formalData': proposal, 'remainingHighValueQueue': {'path': 'remaining-high-value-queue.jsonl.gz', 'eventGroups': len(queue),
            'states': dict(sorted(states.items())),
            'meaning': 'All high-value groups remain visible until formal production coverage is admitted and merged. Pending proposals, completed evidence reviews, aliases and unresearched groups have distinct progress states.'},
        'rightsAndPolicy': {'proposalPath': 'research/evidence/global-code-expansion/policy/proposal.json',
            'globalCodeAuthorityActivated': False, 'chinaPhysicalIdentityAuthorityUsedAsCodeAuthority': False,
            'aaiAndKoreanScopeExpanded': False, 'blanketThirdPartyRedistributionPermissionClaimed': False}}
    validation = {'formatVersion': 1, 'mode': 'offline_metadata_citation_and_integrity_audit',
        'networkRequests': 0, 'newOriginalBytesObtained': False,
        'screeningFingerprintsVerified': sum(len(manifest[k]) for k in ('inputs', 'outputs')),
        'minimum50HighValueEvidenceTargetPassed': True, 'protectedInputs': protected,
        'resolverMatrixAudit': resolver,
        'sourceRegisters': {region: {key: value for key, value in record.items() if key != 'privateReplayed'} for region, record in source_reports.items()},
        'privateOriginalReplay': 'Optional --originals checks current retained private bytes and prints a separate result; offline report does not imply private-byte possession.',
        'publicOriginalOrFullExtractionFiles': [], 'inputSha256': dict(sorted(input_fingerprints.items())),
        'ciAndResolverResults': 'See the separately recorded resolver differential, admission bundle and CI receipt; this metadata audit does not assert that unrelated tests or remote CI have run.'}
    data = {'research-summary.json': (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode(),
            'validation.json': (json.dumps(validation, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()}
    raw = (''.join(canonical(row) + '\n' for row in queue)).encode()
    buffer = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as stream:
        stream.write(raw)
    data['remaining-high-value-queue.jsonl.gz'] = buffer.getvalue()
    for name, content in data.items():
        path = DIRECTORY / name
        if args.check:
            require(path.exists() and path.read_bytes() == content, f'Stale global audit output: {name}')
        else:
            path.write_bytes(content)
    print(json.dumps({'canonicalCases': len(studied), 'highValueEvidenceCases': len(high_evidence),
        'countries': len(countries), 'newDistinctOriginals': len(new_hashes),
        'remainingHighWithoutCompletedPrimaryEvidence': len(high) - len(high_evidence),
        'privateSourcesReplayedThisRun': sum(r['privateReplayed'] for r in source_reports.values()) if args.originals else None,
        'mode': 'check' if args.check else 'build'}, sort_keys=True))


if __name__ == '__main__':
    main()
