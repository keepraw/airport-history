"""Reproduce the PR13 source-to-fact-to-pending-data demonstration.

Judgments are explicit Codex annotations in assessments.json, not parser verdicts
or human decisions. Reuses PR12 acquisition, locking, matching and review gates.
"""
import argparse
import copy
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import re
import resource
import subprocess
import time
from pathlib import Path

from pipeline import (ROOT, load_locked, load_reference, candidate_index,
                      match_observation, base_observation, finish, evidence_sources)
_spec = importlib.util.spec_from_file_location('primary_source_fetch', Path(__file__).with_name('fetch.py'))
_fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fetch)
get, save_source = _fetch.get, _fetch.save_source
from pipeline import plain_text
from common import checked, digest, distance, read_jsonl, research_baseline_path, stable_id, write_json, write_jsonl
from admissions import packets, validate_admission
from review import CLAIMS, validate_batch_series

BASE = ROOT / 'research/evidence/direct'
OUT = BASE / 'generated'
PROVIDERS = ('faa-order', 'faa-airspace', 'faa-fr', 'nws-tin')


def normalized(text):
    return ' '.join(text.split())


def extract(source, raw):
    if source['extractor'] == 'govinfo-pre':
        return plain_text(raw).encode()
    if not raw.startswith(b'%PDF-'):
        raise ValueError('Expected an original PDF, not an error page')
    return subprocess.run(['pdftotext', '-raw' if source['extractor'] == 'pdftotext-raw' else '-layout', '-', '-'], input=raw,
                          stdout=subprocess.PIPE, check=True).stdout


def acquire(output, recover=False):
    """Explicit online step; refuses overwrites and changed recovery originals."""
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty source destination')
    catalog = json.loads((BASE / 'catalog.json').read_text())
    old = json.loads((BASE / 'source-lock.json').read_text())
    locked = {s['sourceId']: s for s in old['sources']}
    sources = []
    for entry in catalog['sources']:
        raw, final = get(entry['retrievalUrl'])
        prior = locked[entry['sourceId']]
        if recover and hashlib.sha256(raw).hexdigest() != prior['originalSha256']:
            raise ValueError('Upstream original changed: ' + entry['sourceId'])
        extracted = extract(entry, raw)
        # Different Poppler versions may lay out irrelevant pages differently.
        # Recovery authenticates all cited spans against freshly extracted pages;
        # the committed, hash-locked extraction remains the offline build input.
        for fact in json.loads((BASE / 'assessments.json').read_text())['facts']:
            if fact['sourceId'] == entry['sourceId']:
                locate(fact, extracted.decode())
        source = save_source(output, raw, **{**entry, 'retrievalUrl': final},
                             accessedAt=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'))
        path = output / ('texts/' + entry['sourceId'] + '.txt.gz')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb') as stream:
            with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as z:
                z.write(extracted)
        source.update(textPath=str(path.relative_to(output)), textSha256=digest(path),
                      textOriginalSha256=hashlib.sha256(extracted).hexdigest(),
                      extractionTool=entry['extractor'])
        if recover and source['inputSha256'] != prior['inputSha256']:
            raise ValueError('Original compression changed')
        sources.append(source)
        print('Recovered' if recover else 'Acquired', entry['sourceId'], flush=True)
    write_json(output / 'source-lock.json', {**old, 'sources': sources,
               'acquisitionMode': 'hash_verified_recovery' if recover else 'new_snapshot'})


def locate(fact, text):
    """Whitespace normalization only; preserve an exact page and span for review."""
    for number, page in enumerate(text.split('\f'), 1):
        page = normalized(page)
        anchor = normalized(fact['anchor'])
        offset = page.find(anchor)
        while offset >= 0:
            before = page[max(0, offset - 300):offset]
            if (not fact.get('subject') or normalized(fact['subject']) in before) and all(
                    context in page for context in fact.get('requiredContext', [])):
                return {'extractedPage': number, 'normalizedOffset': offset,
                        'anchor': anchor, 'context': page[max(0, offset - 100):offset + len(anchor) + 140]}
            offset = page.find(anchor, offset + 1)
    raise ValueError('Missing or misbound original citation: ' + fact['factId'])


def coordinates(fact):
    if fact['kind'] != 'physical_location' or not fact.get('subject'):
        raise ValueError('Coordinates need an adjacent named physical-location fact')
    parts = re.split(r'long\.', fact['anchor'], flags=re.I)
    if len(parts) != 2:
        raise ValueError('Unrecognized coordinate layout')
    values = []
    for part, positive in zip(parts, ('N', 'E')):
        nums = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', part)]
        if len(nums) != 3 or nums[1] >= 60 or nums[2] >= 60:
            raise ValueError('Invalid DMS coordinate')
        values.append((nums[0] + nums[1] / 60 + nums[2] / 3600) * (1 if positive in part else -1))
    if not -90 <= values[0] <= 90 or not -180 <= values[1] <= 180:
        raise ValueError('Invalid physical position')
    return dict(latitude=values[0], longitude=values[1])


def international_indicator(fact, rule):
    if (fact['kind'] not in ('airport_identifier_row', 'retrospective_physical_transition')
            or fact.get('jurisdiction') != 'contiguous-US'
            or not re.fullmatch('[A-Z]{3}', fact.get('faaIdentifier', ''))
            or not re.search(r'\b(?:ARPT|airport|Jetport)\b', fact['anchor'], re.I)
            or not re.search(r'\b' + re.escape(fact.get('faaIdentifier', '')) + r'\b', fact['anchor'])
            or rule['kind'] != 'namespace_rule' or not rule.get('requiredContext')
            or rule['sourceId'] not in ('faa-2009', 'faa-2014')):
        raise ValueError('No explicit contiguous-US airport identifier and authority rule')
    return 'K' + fact['faaIdentifier']


def locked_sources(directory=BASE):
    result = {}
    for source, raw in load_locked(directory, providers=PROVIDERS):
        path = directory / source['textPath']
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('Extraction escapes source directory')
        checked(path, source['textSha256'])
        text = gzip.decompress(path.read_bytes())
        if hashlib.sha256(text).hexdigest() != source['textOriginalSha256']:
            raise ValueError('Changed extracted original text')
        if source['extractor'] == 'govinfo-pre' and extract(source, raw) != text:
            raise ValueError('GovInfo extraction does not reproduce')
        result[source['sourceId']] = (source, text.decode())
    return result


def build(output=OUT, source_directory=BASE):
    started = time.perf_counter()
    assessment = json.loads((BASE / 'assessments.json').read_text())
    if (assessment['humanReviewStatus'] != 'pending' or assessment['reviewer'] is not None
            or assessment['decision'] != 'proposed'):
        raise ValueError('Demonstration must not impersonate human acceptance')
    source_directory = source_directory.resolve()
    if not source_directory.is_relative_to(ROOT.resolve()):
        raise ValueError('Keep reproducible source snapshots inside the repository work directory')
    loaded = locked_sources(source_directory)
    sources = {sid: pair[0] for sid, pair in loaded.items()}
    facts = {}
    for fact in assessment['facts']:
        sid = fact['sourceId']
        if fact['factId'] in facts:
            raise ValueError('Duplicate fact ID')
        facts[fact['factId']] = {**fact, 'citation': locate(fact, loaded[sid][1]),
                                'originalSha256': sources[sid]['originalSha256'],
                                'judgmentStatus': 'codex_proposed_pending_human_review'}
    sites = {s['siteKey']: s for s in assessment['sites']}
    base = json.loads(research_baseline_path().read_text())
    proposed = copy.deepcopy(base)
    proposed['dataVersion'] = '0.8.0'
    proposed['sources'] += [{key: source[key] for key in ('sourceId', 'title', 'url', 'sourceType', 'license')} | {
        'accessedOn': source['accessedAt'][:10], 'verificationStatus': 'pending',
        'note': 'PR13 pending claim review. Original and citation hashes are in research/evidence/direct; this source is not human verified.'}
        for source in sources.values()]
    dossier = []
    def dossier_entry(record_id, ids, **more):
        return {'recordId': record_id, 'decision': 'pending', 'reviewer': None,
                'preparedBy': 'Codex', 'factIds': ids, 'observations': [
                    {'sourceId': facts[fid]['sourceId'], 'factId': fid,
                     'sourceFamily': sources[facts[fid]['sourceId']]['sourceFamily'],
                     'originalPublicationKey': sources[facts[fid]['sourceId']]['originalPublicationKey'],
                     'citation': facts[fid]['citation'], 'claimScope': facts[fid]['conclusion'],
                     'observedOn': facts[fid].get('observationDate') or sources[facts[fid]['sourceId']]['documentEffectiveDate'] or sources[facts[fid]['sourceId']]['publicationDate'],
                     'dateSemantics': 'Dated publication/edition observation, not an allocation or flight day.',
                     'independentOriginal': True, 'basis': facts[fid]['conclusion']}
                    for fid in ids], **more}
    for site in sites.values():
        fact = facts[site['coordinateFactId']]
        position = coordinates(fact)
        site['coordinates'] = position
        sid = fact['sourceId']
        proposed['airports'].append({
            'airportId': site['proposedAirportId'],
            'name': {'value': site['name'], 'status': 'reference', 'sourceIds': [sid],
                     'note': 'Display label only; no historical official-name interval proposed.'},
            'coordinates': {'value': position, 'status': 'reference', 'sourceIds': [sid],
                            'note': 'Named official regulatory location, pending human physical-site review; not an exact historical runway footprint.'},
            'timezone': {'value': None, 'status': 'unknown', 'sourceIds': [], 'note': 'No timezone inference in this proposal.'},
            'externalIds': {'ourAirports': site['ourAirports']}})
        dossier.append(dossier_entry(site['proposedAirportId'], [site['coordinateFactId']]))
    for assignment in assessment['assignments']:
        ids = assignment['factIds']
        rule = next(facts[fid] for fid in ids if facts[fid]['kind'] == 'namespace_rule')
        typed = [f for fid in ids if (f := facts[fid]).get('faaIdentifier')]
        if not typed or any(international_indicator(f, rule) != assignment['code'] for f in typed):
            raise ValueError('Proposed code is not supported by an explicit typed airport row')
        proposed['assignments'].append({key: assignment[key] for key in ('assignmentId', 'scheme', 'code', 'validFrom', 'validTo')} | {
            'airportId': sites[assignment['siteKey']]['proposedAirportId'],
            'verificationStatus': 'pending', 'verifiedOn': None, 'evidenceType': 'continuity_inference',
            'sourceIds': sorted({facts[fid]['sourceId'] for fid in ids}),
            'note': assignment['boundaryAssessment'] + ' ' + assignment['continuityAssessment']})
        dossier.append(dossier_entry(assignment['assignmentId'], ids,
                        boundaryAssessment=assignment['boundaryAssessment'],
                        continuityAssessment=assignment['continuityAssessment']))
    # Cleveland has no registered transition group, and its closure chronology
    # remains unresolved. Retain concrete drafts without including them in the
    # dataset proposed through the existing review workflow.
    blocked_sites = {sites[k]['proposedAirportId'] for case in assessment['cases'] if not case['groupIds'] for k in case['siteKeys']}
    blocked = {key: [r for r in proposed[key] if r.get('airportId') in blocked_sites] for key in ('airports', 'assignments')}
    for key in blocked:
        proposed[key] = [r for r in proposed[key] if r.get('airportId') not in blocked_sites]
    blocked_ids = blocked_sites | {r['assignmentId'] for r in blocked['assignments']}
    blocked['dossier'] = [d for d in dossier if d['recordId'] in blocked_ids]
    blocked['reason'] = 'No existing transition candidate ownership and unresolved closure chronology; no synthetic candidate or acceptance invented.'
    dossier = [d for d in dossier if d['recordId'] not in blocked_ids]
    used_sources = {sid for a in proposed['assignments'] for sid in a['sourceIds']}
    used_sources |= {sid for a in proposed['airports'] for key in ('name', 'coordinates', 'timezone') for sid in a[key]['sourceIds']}
    old_source_ids = {s['sourceId'] for s in base['sources']}
    proposed['sources'] = [s for s in proposed['sources'] if s['sourceId'] in used_sources | old_source_ids]
    # Reuse the actual many-to-many PR12 join, retaining wrong-site associations.
    records = load_reference()
    index = candidate_index(records)
    observations, links = [], []
    for assignment in assessment['assignments']:
        site = sites[assignment['siteKey']]
        fact = next(facts[fid] for fid in assignment['factIds'] if facts[fid].get('faaIdentifier'))
        source = sources[fact['sourceId']]
        observation = base_observation(source, json.dumps(fact['citation'], sort_keys=True), site['name'],
                                       'US', site['coordinates'], [{'scheme': 'ICAO', 'code': assignment['code']}])
        observation.update(supports=[fact['conclusion']],
                           identityFactId=site['coordinateFactId'], codeFactId=fact['factId'],
                           identityBinding='Codex proposed cross-publication binding, pending human review')
        observation = finish(observation)
        observations.append(observation)
        links.extend(match_observation(observation, index, records))
    by_group = {g['eventGroupId']: g for g in index[0].values()}
    selected_ids = {gid for case in assessment['cases'] for gid in case['groupIds']}
    for case in assessment['cases']:
        reference_ids = {stable_id('ref_', ['ourairports', sites[k]['ourAirports']]) for k in case['siteKeys']}
        if any(by_group[gid]['physicalMatch']['referenceId'] not in reference_ids for gid in case['groupIds']):
            raise ValueError('Case points to an unrelated existing candidate group')
    selected = [by_group[gid] for gid in sorted(selected_ids)]
    lock = json.loads((source_directory / 'source-lock.json').read_text())
    batches = list(packets(selected, lock['preparedOn'], lock['baseCommit']))
    for batch in batches:
        batch['batchId'] = batch['batchId'].replace('bulk-proposal', 'direct-fact-proposal')
        batch['sources'] = evidence_sources(sources, sources, lock['preparedOn'])
        for event in batch['events']:
            case = next(c for c in assessment['cases'] if event['eventGroupId'] in c['groupIds'])
            ids = sorted(set(case['factIds'] + [fid for a in assessment['assignments'] if a['siteKey'] in case['siteKeys'] for fid in a['factIds']])) + [s['coordinateFactId'] for s in sites.values() if s['siteKey'] in case['siteKeys']]
            sids = sorted({facts[fid]['sourceId'] for fid in ids})
            event['sourceIds'] = sids
            conclusions = {
                'physicalIdentity': (case['findings'], 'primary_direct'),
                'iata': ('No IATA allocation or interval established. Three-letter FAA identifiers are not IATA evidence.', 'indirect'),
                'icao': ('Explicit FAA airport rows plus the cited section 1-4-1 jurisdiction rule support the proposed indicators; see the per-record dossier. Continuous intervals still need human acceptance.', 'continuity_inference'),
                'historicalBoundary': ('Latest-start and earliest-end bounds are conservative observation limits, not first allocations or withdrawals. See each boundaryAssessment; do not replace them with TAF or rule effectiveness.', 'continuity_inference'),
                'historicalNames': ('Reference display labels only; no historical official-name interval is proposed.', 'indirect'),
                'closureAndReplacement': (case['findings'], 'indirect'),
            }
            event['claims'] = {key: {'conclusion': conclusions[key][0], 'evidenceType': conclusions[key][1],
                                     'sourceIds': sids} for key in sorted(CLAIMS)}
            event['proposalOwnerEventGroupId'] = case['groupIds'][0]
            event['proposedRecordIds'] = ([s['proposedAirportId'] for s in sites.values() if s['siteKey'] in case['siteKeys']] +
                [a['assignmentId'] for a in assessment['assignments'] if a['siteKey'] in case['siteKeys']]) if event['eventGroupId'] == case['groupIds'][0] else []
            event['evidenceFactIds'] = ids
            event['evidenceGaps'] = ['Independent human review/acceptance is missing.', *case['gaps']]
            event['conflicts'] = ['Association disagreement is not a confirmed historical code conflict.']
            event['nextAction'] = 'Review original citations, all six claims and the pending dataset/dossier. Preserve owning candidate mapping; record real human decisions through the unchanged admission gate.'
    existing = [json.loads(p.read_text()) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing, *batches])
    metrics = {
        'originalPublications': len(sources), 'usefulOriginalPublications': sum(s['role'] != 'rejected_sample' for s in sources.values()),
        'rejectedSamplePublications': sum(s['role'] == 'rejected_sample' for s in sources.values()),
        'sourceFamilies': sorted({s['sourceFamily'] for s in sources.values()}),
        'datedPhysicalCases': sum(any(facts[fid].get('date') for fid in c['factIds']) for c in assessment['cases']),
        'retrospectiveExactPhysicalDayFacts': sum(f['kind'] == 'retrospective_physical_transition' and f.get('precision', 'day') == 'day' and bool(f.get('date')) for f in facts.values()),
        'directCodeAllocationBoundaryFacts': 0, 'proposedPhysicalAirports': len(sites) - len(blocked_sites), 'blockedPhysicalAirportDrafts': len(blocked_sites),
        'proposedICAOIntervals': len(assessment['assignments']) - len(blocked['assignments']), 'blockedICAOIntervalDrafts': len(blocked['assignments']), 'proposedIATAIntervals': 0,
        'proposedSources': len(proposed['sources']) - len(base['sources']),
        'intervalDraftsWithUnresolvedCrossSiteOverlap': len({a['assignmentId']
            for a in proposed['assignments'] if a['assignmentId'].startswith('proposal-')
            for b in proposed['assignments'] if a['code'] == b['code'] and a['scheme'] == b['scheme'] and a['airportId'] != b['airportId']
            if max(a['validFrom']['earliest'] or '0001-01-01', b['validFrom']['earliest'] or '0001-01-01') <
               min(a['validTo']['latest'] or '9999-12-31', b['validTo']['latest'] or '9999-12-31')}),
        'existingCandidateGroupsInvestigated': len(selected_ids), 'candidateAssociations': len(links),
        'associationConflictGroups': len({a['eventGroupId'] for a in links if a['status'] == 'conflict'}),
        'identityAmbiguityGroups': len({a['eventGroupId'] for a in links if a['status'] == 'ambiguous'}),
        'unresolvedClosureChronologies': sum(f['kind'] == 'unresolved_chronology' for f in facts.values()),
        'sameSiteCoordinateRevisionContexts': sum(f['kind'] == 'directory_coordinate_revision' for f in facts.values()),
        'directoryUpdateContexts': sum(f['kind'] == 'directory_update_context' for f in facts.values()),
        'adjudicatedDirectoryCorrections': 0,
        'confirmedHistoricalCodeConflicts': 0, 'humanApprovedRecords': 0, 'formalAdmissions': 0,
        'formalHistoricalCoverageIncrease': 0}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'proposed-data.json', proposed)
    write_json(output / 'dossier.json', dossier)
    write_json(output / 'blocked-record-drafts.json', blocked)
    write_json(output / 'metrics.json', metrics)
    write_jsonl(output / 'facts.jsonl.gz', facts.values())
    write_jsonl(output / 'observations.jsonl.gz', observations)
    write_jsonl(output / 'matches.jsonl.gz', links)
    write_jsonl(output / 'review-packets.jsonl.gz', batches)
    write_json(output / 'cases.json', [{**case, 'siteDistanceKm': round(distance(sites[case['siteKeys'][0]]['coordinates'], sites[case['siteKeys'][1]]['coordinates']), 3)} for case in assessment['cases']])
    index_lines = ['# PR13 evidence index — pending human review', '',
        'Codex prepared these judgments. No human acceptance or formal admission is recorded.', '',
        '[Pending dataset](proposed-data.json) · [Record dossiers](dossier.json) · [Blocked drafts](blocked-record-drafts.json)', '',
        '## Original publications', '']
    for sid, source in sources.items():
        raw_path = (source_directory / source['inputPath']).relative_to(ROOT)
        text_path = (source_directory / source['textPath']).relative_to(ROOT)
        index_lines += [f"- **{sid}** — [{source['title']}]({source['url']}); role `{source['role']}`. "
            f"Original archive `{raw_path}`; extraction `{text_path}` (repository-relative paths). "
            f"SHA-256 `{source['originalSha256']}`; accessed {source['accessedAt']}."]
    index_lines += ['', '## Claim-specific proposed judgments', '']
    for fid, fact in facts.items():
        citation = fact['citation']
        index_lines += [f"### {fid}", '',
            f"Source `{fact['sourceId']}`, extracted page {citation['extractedPage']}, normalized offset {citation['normalizedOffset']}; "
            f"kind `{fact['kind']}`.", '', f"> {citation['anchor']}", '', fact['conclusion'], '']
        if fact.get('date'):
            index_lines += [f"Date: `{fact['date']}` ({fact.get('precision', 'day')}; `{fact['dateSemantics']}`).", '']
    (output / 'evidence-index.md').write_text('\n'.join(index_lines), encoding='utf-8')
    # Same formal schema/overlap validation; a pending dataset does not pass admission.
    subprocess.run(['node', '--input-type=module', '-e',
        'import {readFileSync} from "node:fs"; import {assertDataset} from "./src/validate.ts"; assertDataset(JSON.parse(readFileSync(process.argv[1], "utf8")));',
        str((output / 'proposed-data.json').resolve())], cwd=ROOT, check=True)
    try:
        validate_admission(base, proposed, batches, dossier)
    except ValueError as error:
        if 'Prepared packets' not in str(error):
            raise
    else:
        raise ValueError('Pending proposals unexpectedly passed human admission gate')
    inputs = [BASE / 'catalog.json', BASE / 'assessments.json', source_directory / 'source-lock.json',
              research_baseline_path(), ROOT / 'scripts/evidence/direct.py',
              ROOT / 'scripts/evidence/pipeline.py', ROOT / 'scripts/evidence/fetch.py',
              ROOT / 'scripts/reference/admissions.py', ROOT / 'scripts/discovery/review.py',
              ROOT / 'reference/generated/manifest.json', ROOT / 'reference/triage/manifest.json']
    inputs += [source_directory / s[key] for s in sources.values() for key in ('inputPath', 'textPath')]
    write_json(output / 'manifest.json', {'formatVersion': 1, 'status': 'pending_human_review',
        'sourceDirectory': str(source_directory.relative_to(ROOT)),
        'inputs': {str(p.relative_to(ROOT)): digest(p) for p in sorted(inputs)},
        'files': {p.name: digest(p) for p in sorted(output.iterdir()) if p.name != 'manifest.json'}})
    print(json.dumps({'metrics': metrics, 'elapsedSeconds': round(time.perf_counter() - started, 3),
                      'peakRssMiB': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)}))
    return metrics


def validate(output=OUT):
    lock = json.loads((output / 'manifest.json').read_text())
    for path, sha in lock['inputs'].items():
        checked(ROOT / path, sha)
    for name, sha in lock['files'].items():
        checked(output / name, sha)
    source_directory = (ROOT / lock['sourceDirectory']).resolve()
    if not source_directory.is_relative_to(ROOT.resolve()):
        raise ValueError('Source snapshot escapes repository')
    loaded = locked_sources(source_directory)
    assessment = json.loads((BASE / 'assessments.json').read_text())
    facts = {f['factId']: f for f in read_jsonl(output / 'facts.jsonl.gz')}
    if len(facts) != len(assessment['facts']):
        raise ValueError('Missing or duplicate fact judgments')
    for fact in assessment['facts']:
        result = facts[fact['factId']]
        source, text = loaded[fact['sourceId']]
        if (result['citation'] != locate(fact, text) or result['originalSha256'] != source['originalSha256']
                or any(result[key] != value for key, value in fact.items())):
            raise ValueError('Untraceable fact judgment')
    dossier = json.loads((output / 'dossier.json').read_text())
    if any(d['reviewer'] is not None or d['decision'] != 'pending' for d in dossier):
        raise ValueError('Prepared dossier claims human approval')
    if assessment['humanReviewStatus'] != 'pending':
        raise ValueError('Unexpected review status')
    base = json.loads(research_baseline_path().read_text())
    proposed = json.loads((output / 'proposed-data.json').read_text())
    record_ids = set()
    for collection, key in [('sources', 'sourceId'), ('airports', 'airportId'), ('assignments', 'assignmentId'), ('names', 'nameId')]:
        old = {r[key]: r for r in base[collection]}
        new = {r[key]: r for r in proposed[collection]}
        if len(new) != len(proposed[collection]) or any(new.get(k) != r for k, r in old.items()):
            raise ValueError('Pending proposal changed frozen history')
        for identifier in new.keys() - old.keys():
            row = new[identifier]
            if collection in ('assignments', 'sources') and row['verificationStatus'] != 'pending':
                raise ValueError('Proposed record impersonates verified history')
            if collection in ('airports', 'assignments'):
                record_ids.add(identifier)
    if record_ids != {d['recordId'] for d in dossier} or len(record_ids) != len(dossier):
        raise ValueError('Proposal/dossier record coverage mismatch')
    batches = list(read_jsonl(output / 'review-packets.jsonl.gz'))
    existing = [json.loads(p.read_text()) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing, *batches])
    mapped = [record_id for b in batches for e in b['events'] for record_id in e['proposedRecordIds']]
    if set(mapped) != record_ids or len(mapped) != len(record_ids):
        raise ValueError('Proposals need unique existing review-event ownership')
    for b in batches:
        if not b['preparationOnly'] or any(e['status'] != 'pending_review' for e in b['events']):
            raise ValueError('Prepared packet claims acceptance')
    print('Validated direct-source originals, citations, pending proposal and unchanged admission gate.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'build', 'validate'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--sources', type=Path, default=BASE,
                        help='Locked source snapshot consumed by build; default is the committed corpus')
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    if args.command == 'fetch':
        if args.output is None:
            parser.error('Online acquisition requires an explicit empty --output')
        acquire(args.output, args.recover)
    elif args.command == 'build':
        build(args.output or OUT, args.sources)
    else:
        validate(args.output or OUT)
