"""Small deterministic policy evaluator. A classification is never an authorization.

Only metadata, factual notes and minimal citations are public. Originals are private.
The legacy discovery/research builders retain their own immutable baselines.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/reference'))
from common import canonical, digest, read_jsonl, write_json
from query import lookup

DIRECTORY = ROOT / 'research/policy'
ENGINE = '1.0.0'
STAGES = ('global', 'markets', 'transfers', 'direct')


def load(path):
    return json.loads(Path(path).read_text())


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def policy_hash(policy):
    # Lifecycle status is governed separately by the owner authorization registry.
    return sha({k: v for k, v in policy.items() if k not in ('policySha256', 'status')})


def validate_policy(p):
    require(set(p) == {'formatVersion', 'engineVersion', 'policyId', 'policyVersion', 'policySha256',
                       'status', 'scope', 'parameters', 'mandatoryEscalation'}, 'Unknown policy fields')
    require(p['formatVersion'] == 1 and p['engineVersion'] == ENGINE and
            re.fullmatch(r'[a-z][a-z0-9-]+', p['policyId']) and
            re.fullmatch(r'\d+\.\d+\.\d+', p['policyVersion']),
            'Unsupported policy/engine version')
    require(p['status'] in ('draft', 'authorized', 'disabled') and p['policySha256'] == policy_hash(p),
            'Invalid policy hash/status')
    s, v = p['scope'], p['parameters']
    require(set(s) == {'schemaVersion', 'scheme', 'sourceFamilies', 'publisher', 'urlPrefix', 'claims', 'excludedCodes'},
            'Unknown policy scope')
    require(s['schemaVersion'] == '3.0.0' and s['scheme'] == 'ICAO' and s['sourceFamilies'] == ['aai-aip'] and
            s['publisher'] == 'Airports Authority of India' and
            s['urlPrefix'] == 'https://aim-india.aai.aero/eAIP_Archive/' and
            s['claims'] == ['physicalIdentityReference', 'boundedCodeContinuity'] and
            set(s['excludedCodes']) >= {'LEMI', 'RMU', 'MJV', 'TAG', 'LYG', 'YBP'}, 'Unsupported policy scope')
    integers = {'minimumObservations', 'minimumDistinctOriginals', 'maximumGapDays', 'maximumWindowDays',
                'mediumMaximumGapDays', 'mediumMaximumWindowDays', 'maximumEventsPerBatch'}
    flags = {'excludeFirstObservationLocalDay', 'excludeLastObservationLocalDay', 'unknownOuterBoundsRequired',
             'requireEditionAnchor', 'requireStableOfficialNameAndArp', 'requireOriginalReplayForAdmission'}
    require(set(v) == integers | flags | {'arpToleranceDegrees'}, 'Unknown risk parameters')
    require(all(type(v[k]) is int and v[k] > 0 for k in integers) and all(v[k] is True for k in flags),
            'Invalid or unsafe risk parameters')
    require(v['minimumObservations'] >= 2 and v['minimumDistinctOriginals'] >= 2 and
            0 < v['maximumGapDays'] <= v['mediumMaximumGapDays'] and
            0 < v['maximumWindowDays'] <= v['mediumMaximumWindowDays'] and
            v['maximumEventsPerBatch'] <= 20 and type(v['arpToleranceDegrees']) in (int, float) and
            0 < v['arpToleranceDegrees'] <= 1e-8, 'Invalid risk limits')
    require(set(p['mandatoryEscalation']) == {'competing_physical_sites', 'identity_unestablished',
            'material_conflict', 'opening_date_substitution', 'published_record_change', 'unknown_conflict'},
            'Missing mandatory escalation')


def pinned(path, expected):
    path = ROOT / path
    require(path.resolve().is_relative_to(ROOT) and digest(path) == expected, f'Changed pinned input: {path}')
    return load(path)


def inputs():
    """Read only existing research products and the reference indexes; never rescan discovery."""
    policy = load(DIRECTORY / 'policy.json')
    validate_policy(policy)
    lock = load(DIRECTORY / 'input-lock.json')
    for path, expected in lock['files'].items():
        require(digest(ROOT / path) == expected, f'Changed pinned input: {path}')
    base = pinned(lock['baseline']['path'], lock['baseline']['sha256'])
    require(base['dataVersion'] == lock['baseline']['dataVersion'] and
            base['schemaVersion'] == policy['scope']['schemaVersion'], 'Incompatible baseline')
    sources, dossiers, records, airports = {}, {}, {}, {}
    def add_source(s, directory):
        old = sources.get(s['sourceId'])
        require(old is None or (old['originalSha256'], old['textOriginalSha256']) ==
                (s['originalSha256'], s['textOriginalSha256']), 'Inconsistent original source hashes across pipelines')
        sources[s['sourceId']] = {**s, '_directory': directory}
    competitors = defaultdict(set)
    for stage in STAGES:
        directory = ROOT / f'research/evidence/{stage}'
        data = load(directory / 'generated/proposed-data.json')
        for a in data['assignments']:
            competitors[(a['scheme'], a['code'])].add(a['airportId'])
            if a['verificationStatus'] == 'pending':
                records[a['assignmentId']] = a
        airports.update({p['airportId']: p for p in data['airports']})
        for d in load(directory / 'generated/dossier.json'):
            dossiers[d['recordId']] = d
        for s in load(directory / 'source-lock.json')['sources']:
            add_source(s, str(directory.relative_to(ROOT)))
    for a in base['assignments']:
        competitors[(a['scheme'], a['code'])].add(a['airportId'])
    for s in load(ROOT / 'research/evidence/first-admission/source-lock.json')['sources']:
        add_source(s, 'research/evidence/first-admission')
    for s in load(DIRECTORY / 'source-lock.json')['sources']:
        add_source(s, 'research/policy')
    for d in load(ROOT / 'research/admissions/0.9.0/dossier.json'):
        if d.get('recordType') != 'assignment' or d['scheme'] != 'ICAO' or not d['code'].startswith('V'):
            continue
        names = {n['sourceId']: n['officialName'] for n in d['officialNameObservations']}
        for o in d['observations']:
            sid = o['sourceId']
            anchors = sorted(s['sourceId'] for s in sources.values() if s.get('editionEffectiveDate') ==
                             o['editionEffectiveDate'] == s.get('componentEffectiveDate'))
            sources[sid].update(code=d['code'], scheme='ICAO', airportId=d['airportId'],
                officialName=names[sid], sourceType='primary', originalVerified=True,
                editionAnchorSourceId=anchors[0] if anchors else None)
    selection = load(ROOT / 'research/evidence/first-admission/selection.json')
    formal_keys = {(a['scheme'], a['code'], a['airportId']) for a in base['assignments']}
    records = {rid: a for rid, a in records.items() if (a['scheme'], a['code'], a['airportId']) not in formal_keys}
    # Formal 0.9.0 records provide exact positive scopes, never policy grants.
    for a in base['assignments']:
        if any(x['recordId'] == a['assignmentId'] for x in selection['assignments']):
            records[a['assignmentId']] = a
    return policy, lock, base, records, airports, dossiers, sources, competitors


def citation(s):
    path = Path(s['_directory']) / s.get('excerptPath', s.get('retainedPath', 'missing'))
    expected = s.get('excerptSha256', s.get('retainedSha256'))
    e = pinned(path, expected)
    require(e['originalSha256'] == s['originalSha256'] and e['textOriginalSha256'] == s['textOriginalSha256'],
            'Detached original citation')
    require(e['spans'] and all(len(q['quote']) == q.get('characterEnd', q.get('normalizedCharacterEnd')) -
            q.get('characterStart', q.get('normalizedCharacterStart')) for q in e['spans']), 'Malformed citation')
    return e


def arp(text):
    m = re.search(r'(\d{2})(\d{2})(\d{2})([NS]) (\d{3})(\d{2})(\d{2})([EW])', text)
    if not m:
        return None
    a, b, c, ns, d, e, f, ew = m.groups()
    if not (int(b) < 60 and int(c) < 60 and int(e) < 60 and int(f) < 60):
        return None
    return {'latitude': (int(a) + int(b)/60 + int(c)/3600) * (-1 if ns == 'S' else 1),
            'longitude': (int(d) + int(e)/60 + int(f)/3600) * (-1 if ew == 'W' else 1)}


def deduplicate_observations(rows):
    unique = {}
    for s in sorted(rows, key=lambda s: s['sourceId']):
        key = (s['publisher'], s['editionEffectiveDate'], s['originalPublicationKey'])
        old = unique.get(key)
        require(old is None or (old['originalSha256'], old['textOriginalSha256']) ==
                (s['originalSha256'], s['textOriginalSha256']), 'Conflicting originals for one edition observation')
        if old is None: unique[key] = s
    return sorted(unique.values(), key=lambda s: (s['editionEffectiveDate'], s['sourceId']))


def observations(a, sources):
    rows = []
    for s in sources.values():
        if s.get('code') != a['code'] or s.get('scheme') != a['scheme'] or s.get('airportId') != a['airportId']:
            continue
        e = citation(s)
        anchor = sources.get(s.get('editionAnchorSourceId'))
        require(anchor is not None, 'Missing edition anchor')
        anchor_text = ' '.join(q['quote'] for q in citation(anchor)['spans'])
        printed = date.fromisoformat(s['editionEffectiveDate']).strftime('%d %b %Y').upper()
        require(f"name='EM.effectiveDateStart' content='{printed}'" in anchor_text and anchor['publisher'] == s['publisher'] and
                anchor.get('componentEffectiveDate') == s['editionEffectiveDate'], 'Uncontrolled edition anchor')
        rows.append({**s, 'spans': e['spans']})
    # sourceIds repeated through research stages do not multiply observations.
    return deduplicate_observations(rows)


def classify(a, physical, obs, rivals, reference, policy, safety=None):
    """Pure hard predicates. No AI score; absence of a flag is not conflict clearance."""
    v, scope = policy['parameters'], policy['scope']
    reasons, high, missing = [], [], []
    safety = safety or {}
    if a['code'] in scope['excludedCodes']:
        high.append('explicit_exception_scope')
    if len(rivals) != 1 or reference['totalMatches'] > 1 or reference['possibleLocationCount'] > 1:
        high.append('competing_physical_sites')
    for k in policy['mandatoryEscalation']:
        if safety.get(k):
            high.append(k)
    if safety.get('scopeScreened') is not True:
        high.append('unknown_conflict')
    if a['scheme'] != scope['scheme']:
        reasons.append('outside_automatic_scope')
    if len(obs) < v['minimumObservations']:
        missing.append('too_few_dated_aip_observations')
    if len({s['originalSha256'] for s in obs}) < v['minimumDistinctOriginals']:
        reasons.append('too_few_distinct_originals')
    valid = []
    for s in obs:
        if not (s['sourceFamily'] in scope['sourceFamilies'] and s['publisher'] == scope['publisher'] and
                s['url'].startswith(scope['urlPrefix']) and s.get('sourceType') == 'primary' and
                s.get('publicationDate') and s.get('editionAnchorSourceId') and
                s.get('componentEffectiveDate') and s['componentEffectiveDate'] <= s['editionEffectiveDate'] and
                s['publicationDate'] <= s['editionEffectiveDate'] and
                s['editionEffectiveDate'] <= s['accessedAt'][:10] and s.get('originalVerified') is True):
            missing.append('uncontrolled_edition_or_original')
            continue
        date.fromisoformat(s['editionEffectiveDate'])
        text = ' '.join(q['quote'] for q in s['spans'])
        if s.get('officialName') not in text or f"{a['code']} - {s.get('officialName')}" not in text:
            missing.append('official_name_code_binding_missing')
        point = arp(text)
        if not point or not physical or physical['coordinates']['value'] is None or any(
                abs(point[k] - physical['coordinates']['value'][k]) > v['arpToleranceDegrees'] for k in point):
            high.append('identity_unestablished')
        valid.append(s)
    if valid and len({canonical(arp(' '.join(q['quote'] for q in s['spans']))) for s in valid}) != 1:
        high.append('material_conflict')
    if valid and len({s['officialName'] for s in valid}) != 1:
        reasons.append('official_name_changed')
    if not physical or reference['totalMatches'] == 0:
        high.append('identity_unestablished')
    if physical and (physical['name']['status'] != 'reference' or physical['coordinates']['status'] != 'reference' or
                     physical['timezone']['status'] != 'unknown' or physical['timezone']['value'] is not None):
        high.append('identity_unestablished')
    dates = sorted({s['editionEffectiveDate'] for s in valid})
    window = None
    gap = None
    if len(dates) >= v['minimumObservations']:
        gap = max((date.fromisoformat(b) - date.fromisoformat(c)).days for c, b in zip(dates, dates[1:]))
        window = [(date.fromisoformat(dates[0]) + timedelta(days=1)).isoformat(), dates[-1]]
    if not window or window[0] >= window[1]:
        missing.append('no_defensible_whole_local_day_window')
    else:
        days = (date.fromisoformat(window[1]) - date.fromisoformat(window[0])).days
        if gap > v['maximumGapDays']: reasons.append('observation_gap_exceeds_low_limit')
        if days > v['maximumWindowDays']: reasons.append('window_exceeds_low_limit')
        if gap > v['mediumMaximumGapDays'] or days > v['mediumMaximumWindowDays']:
            high.append('continuity_exceeds_medium_limit')
    # Hard failures never fall through to batch authorization.
    risk = 'high' if high else 'insufficient' if missing else 'medium' if reasons else 'low'
    return {'risk': risk, 'reasons': sorted(set(high + missing + reasons)),
            'triggeredRules': ['all_low_risk_predicates_satisfied'] if risk == 'low' else
                [f'route_to_{risk}', *sorted(set(high + missing + reasons))], 'window': window,
            'maximumObservedGapDays': gap, 'observationCount': len(obs),
            'distinctOriginalCount': len({s['originalSha256'] for s in obs}),
            'publisherCount': len({s['publisher'] for s in obs})}


def evaluate():
    p, lock, base, records, airports, dossiers, sources, competitors = inputs()
    screens = load(DIRECTORY / 'screening.json')
    require(screens['reviewer'] is None and screens['screenedBy'] == 'Codex', 'Screening is not human approval')
    decisions = []
    admitted = {a['assignmentId'] for a in base['assignments']}
    for rid, a in sorted(records.items()):
        ref = lookup(code=a['code'], scheme=a['scheme'], limit=0)
        obs = observations(a, sources)
        screen = screens['records'].get(rid, {})
        result = classify(a, airports.get(a['airportId']), obs, competitors[(a['scheme'], a['code'])], ref, p, screen)
        research_evidence = [{k: sources[sid].get(k) for k in ('sourceId', 'url', 'originalSha256',
            'textOriginalSha256', 'sourceFamily', 'contentStatus')} for sid in sorted(set(a['sourceIds'])) if sid in sources]
        if research_evidence and not any(s['sourceFamily'] in p['scope']['sourceFamilies'] for s in research_evidence):
            result['reasons'] = sorted(set(result['reasons']) | {'outside_automatic_scope'})
            result['triggeredRules'] = sorted(set(result['triggeredRules']) | {'outside_automatic_scope'})
        candidate = deepcopy(a)
        physical = deepcopy(airports.get(a['airportId']))
        if result['window']:
            candidate.update(validFrom={'earliest': None, 'latest': result['window'][0], 'precision': 'unknown'},
                             validTo={'earliest': result['window'][1], 'latest': None, 'precision': 'unknown'},
                             evidenceType='continuity_inference', sourceIds=[s['sourceId'] for s in obs],
                             verificationStatus='pending', verifiedOn=None)
            if physical:
                physical['name']['sourceIds'] = candidate['sourceIds']
                physical['coordinates']['sourceIds'] = candidate['sourceIds']
        decisions.append({'recordId': rid, 'airportId': a['airportId'], 'scheme': a['scheme'], 'code': a['code'],
                          'sample': 'published-positive' if rid in admitted else 'unpublished',
                          **result, 'reviewMode': 'policy_dry_run', 'reviewer': None, 'authorizationSource': None,
                          'policyId': p['policyId'], 'policyVersion': p['policyVersion'], 'policySha256': p['policySha256'],
                          'baseline': lock['baseline'], 'inputSha256': sha(lock),
                          'evidenceSha256': sha({'observations': obs, 'researchEvidence': research_evidence}),
                          'sourceIds': [s['sourceId'] for s in obs], 'researchEvidence': research_evidence,
                          'referenceScreen': {k: ref[k] for k in ('status', 'totalMatches', 'possibleLocationCount')},
                          'knownSiteIds': sorted(competitors[(a['scheme'], a['code'])]),
                          'candidateRecord': candidate, 'physicalAirport': physical,
                          'evidence': [{k: s[k] for k in ('sourceId', 'url', 'publisher', 'originalSha256',
                              'textOriginalSha256', 'excerptSha256', 'publicationDate', 'componentEffectiveDate',
                              'editionEffectiveDate', 'originalPublicationKey', 'editionAnchorSourceId')} for s in obs],
                          'researchSourceIds': a['sourceIds'],
                          'researchBlockers': dossiers.get(rid, {}).get('approvalBlockers', []),
                          'residualRisks': ['Continuity is a bounded policy inference, not daily direct observation.',
                            'Conflict screening covers locked research/reference evidence only; no all-history absence claim.',
                            'First allocation, final withdrawal, timezone and official-name timeline remain unknown.']})
    return decisions


def proposed_dataset(decisions, *, verified=False, risks=('low',), reviewed_on=None):
    p, lock, base, records, airports, _, sources, _ = inputs()
    data = deepcopy(base)
    version = base['dataVersion'].split('.')
    require(len(version) == 3 and all(x.isdigit() for x in version), 'Unsupported formal data version')
    data['dataVersion'] = f'{version[0]}.{int(version[1])+1}.0'
    selected = [d for d in decisions if d['sample'] == 'unpublished' and d['risk'] in risks]
    for d in selected:
        a = deepcopy(records[d['recordId']])
        ids = d['sourceIds']
        a.update(sourceIds=ids, validFrom={'earliest': None, 'latest': d['window'][0], 'precision': 'unknown'},
                 validTo={'earliest': d['window'][1], 'latest': None, 'precision': 'unknown'},
                 evidenceType='continuity_inference', verificationStatus='verified' if verified else 'pending',
                 verifiedOn=(reviewed_on or lock['reviewedOn']) if verified else None,
                 note='Bounded whole-local-date policy inference; unknown outer bounds. Policy audit is external to Schema 3.0.0.')
        data['assignments'].append(a)
        if not any(x['airportId'] == a['airportId'] for x in data['airports']):
            physical = deepcopy(airports[a['airportId']])
            physical['name']['sourceIds'] = ids
            physical['coordinates']['sourceIds'] = ids
            data['airports'].append(physical)
        for sid in ids:
            if any(x['sourceId'] == sid for x in data['sources']): continue
            s = sources[sid]
            data['sources'].append({'sourceId': sid, 'title': s['title'], 'url': s['url'],
                'accessedOn': s['accessedAt'][:10], 'sourceType': 'primary', 'license': s['license'],
                'verificationStatus': 'verified' if verified else 'pending',
                'note': 'Same AAI issuer; dated editions are temporal observations. Original hashes and citations in policy lock.'})
    return data


def fixed_batches(decisions, risk):
    p, lock, *_ = inputs()
    rows = [r for r in decisions if r['sample'] == 'unpublished' and r['risk'] == risk]
    size = p['parameters']['maximumEventsPerBatch']
    batches = []
    for start in range(0, len(rows), size):
        content = {'formatVersion': 1, 'risk': risk, 'baseline': lock['baseline'], 'inputSha256': sha(lock),
                   'policySha256': p['policySha256'], 'records': rows[start:start+size]}
        batches.append({**content, 'batchSha256': sha(content)})
    return batches


def build(output):
    decisions = evaluate()
    p, lock, *_ = inputs()
    write_json(output / 'decisions.json', decisions)
    for risk in ('low', 'medium'):
        write_json(output / f'{risk}-batches.json', fixed_batches(decisions, risk))
    write_json(output / 'pending-data.json', proposed_dataset(decisions))
    write_json(output / 'simulation-data.json', proposed_dataset(decisions, verified=True))
    write_json(output / 'medium-simulation-data.json', proposed_dataset(decisions, verified=True, risks=('medium',)))
    write_json(output / 'summary.json', {'counts': dict(Counter(d['risk'] for d in decisions if d['sample'] == 'unpublished')),
        'positiveCounts': dict(Counter(d['risk'] for d in decisions if d['sample'] == 'published-positive')),
        'refusalRules': dict(Counter(r for d in decisions if d['sample'] == 'unpublished' for r in d['reasons'])),
        'mode': 'dry_run', 'authorized': False, 'policySha256': p['policySha256'], 'baseline': lock['baseline']})


def replay_originals():
    from global_batch import extract
    _, _, _, _, _, _, sources, _ = inputs()
    for s in load(DIRECTORY / 'source-lock.json')['sources']:
        raw = ROOT / s['privateOriginalPath']
        require(digest(raw) == s['originalSha256'], 'Original replay hash mismatch')
        text = extract(raw.read_bytes())
        require(hashlib.sha256(text.encode()).hexdigest() == s['textOriginalSha256'], 'Original extraction mismatch')
        normalized = ' '.join(text.split())
        for q in citation(sources[s['sourceId']])['spans']:
            target = raw.read_bytes().decode('utf-8') if q['kind'] == 'raw_html' else normalized
            require(target[q['characterStart']:q['characterEnd']] == q['quote'], 'Original citation replay mismatch')
    print('Replayed every policy original, extraction and exact citation; no human reading asserted.')


def freeze_inputs():
    """Explicit preparation from the current released snapshot, independently of old research baselines."""
    base = load(ROOT / 'data/airports.json')
    path = f"test/curated-{base['dataVersion']}.json"
    require((ROOT / path).read_bytes() == (ROOT / 'data/airports.json').read_bytes(), 'Unpublished formal baseline')
    files = [DIRECTORY / name for name in ('source-lock.json', 'screening.json')]
    files += list((DIRECTORY / 'excerpts').glob('*.json'))
    files += [ROOT / 'research/evidence/first-admission/selection.json',
              ROOT / 'research/evidence/first-admission/source-lock.json', ROOT / 'research/admissions/0.9.0/dossier.json']
    files += list((ROOT / 'research/evidence/first-admission/excerpts').glob('*.json'))
    for stage in STAGES:
        directory = ROOT / f'research/evidence/{stage}'
        files += [directory / 'source-lock.json', directory / 'generated/proposed-data.json', directory / 'generated/dossier.json']
        files += list((directory / 'excerpts').glob('*.json'))
    files += list((ROOT / 'reference/generated').glob('*.gz'))
    files += [ROOT / 'reference/generated/manifest.json', ROOT / 'reference/generated/sources.json']
    files += [ROOT / p for p in ('schema/dataset.schema.json', 'scripts/reference/admissions.py',
        'scripts/evidence/policy_review.py', 'scripts/evidence/policy_gate.py', 'scripts/evidence/policy_coverage.ts',
        'scripts/evidence/policy_report.py', 'src/resolve.ts', 'src/names.ts', 'src/evidence.ts', 'src/time.ts', 'src/validate.ts')]
    files += [ROOT / f'research/evidence/global/generated/batches/global-evidence-proposal-{n}.json' for n in (1, 2)]
    write_json(DIRECTORY / 'input-lock.json', {'formatVersion': 1,
        'baseline': {'path': path, 'sha256': digest(ROOT / path), 'dataVersion': base['dataVersion'],
            'schemaVersion': base['schemaVersion'],
            'baseCommit': subprocess.check_output(['git', 'rev-parse', 'origin/main'], cwd=ROOT, text=True).strip()},
        'reviewedOn': date.today().isoformat(),
        'files': {str(f.relative_to(ROOT)): digest(f) for f in sorted(set(files))}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'validate', 'originals', 'fetch-originals', 'freeze', 'admit', 'activate'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--authorization-url')
    parser.add_argument('--batch-sha256', help='Exact immutable medium batch; never a wildcard')
    args = parser.parse_args()
    if args.command == 'freeze': freeze_inputs()
    elif args.command == 'fetch-originals':
        import urllib.request
        for s in load(DIRECTORY / 'source-lock.json')['sources']:
            target = ROOT / s['privateOriginalPath']
            require(target.resolve().is_relative_to(ROOT / 'work'), 'Unsafe private original path')
            raw = urllib.request.urlopen(s['url'], timeout=60).read()
            require(hashlib.sha256(raw).hexdigest() == s['originalSha256'], 'Fetched original has changed')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        replay_originals()
    elif args.command == 'originals': replay_originals()
    elif args.command == 'activate':
        from policy_gate import activate
        activate(args.authorization_url, args.batch_sha256)
    elif args.command == 'admit':
        from policy_gate import admit
        require(args.output is not None and args.output.resolve().is_relative_to(ROOT / 'work'),
                'Admission output must be a new review proposal in ignored work/')
        admit(args.output, args.batch_sha256)
    elif args.command == 'build': build(DIRECTORY / 'generated' if args.output is None else args.output)
    else:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            build(Path(tmp))
            for path in Path(tmp).glob('*.json'):
                require(path.read_bytes() == (DIRECTORY / 'generated' / path.name).read_bytes(),
                        f'Non-reproducible policy output: {path.name}')
        print('Policy dry-run reproduced; formal data and authorization registry unchanged.')


if __name__ == '__main__': main()
