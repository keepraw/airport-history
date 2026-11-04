"""Human Admission v1: exact, per-batch Owner-approved formal admission.

This module adds no new evidence, schema, conflict or resolver semantics. It
composes the existing gates:

* ``scripts/reference/admissions.validate_admission`` (human review path, no
  ``policy_context``) and ``scripts/discovery/review.validate_batch_series``;
* ``src/validate.ts`` (``assertDataset`` / ``validateDataset``) for schema,
  physical identity and overlap/conflict semantics;
* ``scripts/evidence/policy_coverage.ts`` ``measure()`` for the production
  ``resolveAirport()`` differential and published-answer immutability.

What this module adds is only the binding: one batch manifest whose hashes the
Owner approves verbatim in a real GitHub comment, original-evidence locking and
replay, date-basis checks, and a CI router that replays the frozen published
tree. It never authorizes anything by itself and has no test or bypass switch.
"""
import datetime as dt
import hashlib
import html.parser
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'admission/human-v1'
ADMISSIONS = ROOT / 'research/admissions'
WORK = ROOT / 'work/human-v1'
REPOSITORY = 'keepraw/airport-history'
OWNER = {'login': 'keepraw', 'id': 49091395}
FORMAT = 'human-admission@1'
MAX_EVENTS = 20
MAX_QUOTE = 240

for sub in ('scripts/reference', 'scripts/discovery', 'scripts/evidence'):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

# Every file whose behaviour an approval relies on. Changing any of them changes
# the executor hash, which invalidates every approval bound to the old hash.
REUSED_GATES = (
    'scripts/reference/admissions.py', 'scripts/reference/common.py', 'scripts/reference/triage.py',
    'scripts/discovery/review.py', 'scripts/evidence/policy_coverage.ts',
    'src/resolve.ts', 'src/names.ts', 'src/time.ts', 'src/evidence.ts', 'src/validate.ts', 'src/types.ts',
    'schema/dataset.schema.json', 'pnpm-lock.yaml',
)
COLLECTIONS = {'airports': 'airportId', 'assignments': 'assignmentId', 'names': 'nameId', 'sources': 'sourceId'}
RECORD_FIELDS = {'airports': 'admittedAirportIds', 'assignments': 'admittedAssignmentIds', 'names': 'admittedNameIds'}
# Dates that may bound a code or name interval, and dates that never may.
BOUND_KINDS = {'code_effective', 'observed_in_force', 'observed_not_in_force', 'name_effective'}
FORBIDDEN_KINDS = {'opening', 'capture', 'licence', 'git', 'publication', 'operations_start', 'operations_end'}
# (date kind, bound) -> allowed day offsets of the bound from the cited date.
# An effective date opens a one-day window [D, D+1); an in-force observation on
# D proves start <= D(+1 when the observation day itself is excluded) and end > D.
ALLOWED_DELTAS = {
    **{(k, b): (0,) for k in ('code_effective', 'name_effective') for b in ('validFrom.earliest', 'validTo.earliest')},
    **{(k, b): (0, 1) for k in ('code_effective', 'name_effective') for b in ('validFrom.latest', 'validTo.latest')},
    ('observed_in_force', 'validFrom.latest'): (0, 1), ('observed_in_force', 'validTo.earliest'): (-1, 0),
    ('observed_not_in_force', 'validFrom.earliest'): (0, 1), ('observed_not_in_force', 'validTo.latest'): (0, 1),
}
EXTRACTORS = {'pdftotext-layout', 'html-text', 'utf8-text'}


class AdmissionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AdmissionError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    return sha_bytes(Path(path).read_bytes())


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def version_tuple(value):
    require(isinstance(value, str) and re.fullmatch(r'\d+\.\d+\.\d+', value), 'Invalid dataVersion: %r' % (value,))
    return tuple(map(int, value.split('.')))


def bundle_dir(version, root=ROOT):
    version_tuple(version)
    return root / 'research/admissions' / version / 'human-v1'


# ---------------------------------------------------------------- executor --

def executor_files(root=ROOT):
    own = sorted(str(p.relative_to(root)) for p in (root / 'admission/human-v1').rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.md', '.pyc'))
    missing = [p for p in REUSED_GATES if not (root / p).is_file()]
    require(not missing, 'Reused gate missing: ' + ', '.join(missing))
    return sorted(set(own) | set(REUSED_GATES))


def executor(root=ROOT):
    files = {p: sha_file(root / p) for p in executor_files(root)}
    payload = {'format': FORMAT, 'files': files}
    return {**payload, 'executorSha256': sha(payload)}


# ---------------------------------------------------------------- baseline --

def published_baseline(base_commit, root=ROOT):
    """The base must be a published main commit whose data equals its immutable snapshot."""
    require(re.fullmatch(r'[0-9a-f]{40}', base_commit or ''), 'Full base commit SHA required')
    main = None
    for ref in ('origin/main', 'main'):
        try:
            main = git('rev-parse', '--verify', '--quiet', ref, cwd=root)
            break
        except subprocess.CalledProcessError:
            continue
    require(main, 'Published main history unavailable')
    require(subprocess.run(['git', 'merge-base', '--is-ancestor', base_commit, main], cwd=root,
                           stderr=subprocess.DEVNULL).returncode == 0,
            'Base commit is not part of published main history')
    data = subprocess.check_output(['git', 'show', base_commit + ':data/airports.json'], cwd=root)
    base = json.loads(data)
    snapshot_path = 'test/curated-%s.json' % base['dataVersion']
    snapshot = subprocess.check_output(['git', 'show', base_commit + ':' + snapshot_path], cwd=root)
    require(data == snapshot, 'Published data differs from its immutable snapshot ' + snapshot_path)
    return {'baseCommit': base_commit, 'baseDataVersion': base['dataVersion'], 'baseSnapshot': snapshot_path,
            'baseDataSha256': sha_bytes(data), 'schemaVersion': base['schemaVersion']}, base


def other_bundles(version, root=ROOT):
    return [p for p in sorted((root / 'research/admissions').glob('*/human-v1')) if p.parent.name != version]


def check_single_active(version, base_version, records, root=ROOT):
    """One active batch at a time; permanent identifiers never reused across batches."""
    ids = {r['id'] for r in records}
    for other in other_bundles(version, root):
        other_version = other.parent.name
        published = version_tuple(other_version) <= version_tuple(base_version)
        require(published, 'Another human admission batch is active: ' + other_version)
        if (other / 'records.json').exists():
            clash = ids & {r['id'] for r in load(other / 'records.json')['records']}
            require(not clash, 'Permanent identifier reused across batches: ' + ', '.join(sorted(clash)))


# ------------------------------------------------------------------- spec ---

def validate_spec(spec):
    require(isinstance(spec, dict) and spec.get('format') == FORMAT, 'Batch spec must declare ' + FORMAT)
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{2,80}', spec.get('batchId') or ''), 'Invalid batchId')
    require(not re.search(r'(^|-)(all|any|every|wildcard)(-|$)', spec['batchId']), 'Wildcard-like batchId refused')
    version_tuple(spec.get('targetDataVersion'))
    dt.date.fromisoformat(spec.get('reviewedOn'))
    for key in ('records', 'events', 'evidence', 'dossier', 'excluded'):
        require(key in spec, 'Batch spec lacks ' + key)
    require(set(spec['records']) == set(COLLECTIONS), 'Records must list airports, assignments, names and sources')
    for collection, field in COLLECTIONS.items():
        for record in spec['records'][collection]:
            value = record.get(field)
            require(isinstance(value, str) and value and '*' not in value, 'Exact record ID required in ' + collection)
    excluded = {e['recordId'] for e in spec['excluded']}
    included = {r[f] for c, f in COLLECTIONS.items() for r in spec['records'][c]}
    require(not (excluded & included), 'Excluded candidate also listed for admission')
    for e in spec['excluded']:
        require(e.get('reason') and e.get('recordType'), 'Excluded candidate lacks recordType/reason')


def record_list(spec):
    out = []
    for collection, field in COLLECTIONS.items():
        for record in spec['records'][collection]:
            out.append({'collection': collection, 'id': record[field], 'record': record})
    ids = [r['id'] for r in out]
    require(len(ids) == len(set(ids)), 'Duplicate record ID in batch')
    return out


def review_batches(spec):
    """Split events into existing-format review batches of at most 20 events."""
    events = spec['events']
    sources = spec['evidence']['reviewSources']
    out = []
    for n in range(0, max(len(events), 1), MAX_EVENTS):
        chunk = events[n:n + MAX_EVENTS]
        counts = {s: sum(e['status'] == s for e in chunk) for s in ('ready_to_admit', 'pending_review', 'excluded', 'insufficient_evidence')}
        used = sorted({s for e in chunk for s in e['sourceIds']})
        admitted = {k: sum(len(e[RECORD_FIELDS[k]]) for e in chunk) for k in RECORD_FIELDS}
        out.append({
            'batchId': '%s-%d' % (spec['batchId'], n // MAX_EVENTS + 1), 'baseCommit': spec['baseCommit'],
            'reviewedOn': spec['reviewedOn'],
            'selection': {'maximumEvents': MAX_EVENTS, 'eventCount': len(chunk),
                          'scope': 'Exact records of human admission batch %s only' % spec['batchId']},
            'statusCounts': counts,
            'admission': {**admitted, 'formalSources': len(spec['records']['sources'])},
            'sources': [s for s in sources if s['sourceId'] in used],
            'events': chunk,
        })
    return out


# ------------------------------------------------------------- originals ---

class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        elif tag in ('br', 'p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'td', 'th', 'table'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def extract(data, extractor):
    """Independent, deterministic text extraction from original bytes."""
    require(extractor in EXTRACTORS, 'Unknown extractor ' + str(extractor))
    if extractor == 'pdftotext-layout':
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'o.pdf'
            src.write_bytes(data)
            subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', str(src), str(Path(tmp) / 'o.txt')], check=True)
            text = (Path(tmp) / 'o.txt').read_text('utf-8')
    elif extractor == 'html-text':
        parser = _Text()
        parser.feed(data.decode('utf-8', errors='replace'))
        text = ''.join(parser.parts)
    else:
        text = data.decode('utf-8')
    return re.sub(r'[ \t\u00a0]+', ' ', text).replace('\r\n', '\n')


def fetch(url):
    """Network acquisition of an original. Only https URLs are acquired."""
    require(url.startswith('https://'), 'Originals are acquired over https only')
    request = urllib.request.Request(url, headers={'User-Agent': 'keepraw-airport-history human-v1 verification'})
    with urllib.request.urlopen(request, timeout=90) as response:
        require(response.status == 200, 'Original unavailable: HTTP %s' % response.status)
        return response.read()


def validate_evidence_lock(lock, records):
    require(lock.get('format') == FORMAT and isinstance(lock.get('sources'), list) and lock['sources'], 'Invalid evidence lock')
    formal = {r['id']: r['record'] for r in records if r['collection'] == 'sources'}
    seen = set()
    for s in lock['sources']:
        sid = s.get('sourceId')
        require(sid not in seen, 'Duplicate locked source ' + str(sid))
        seen.add(sid)
        require(sid in formal, 'Locked source is not an approved formal source: ' + str(sid))
        require(formal[sid]['url'] == s['url'], 'Locked source URL differs from formal source')
        require(re.fullmatch(r'[0-9a-f]{64}', s.get('originalSha256') or '') and
                re.fullmatch(r'[0-9a-f]{64}', s.get('textSha256') or ''), 'Locked source lacks original/text SHA-256')
        require(s.get('extractor') in EXTRACTORS, 'Locked source lacks a known independent extractor')
        require(s.get('rights', {}).get('licenseId') and s['rights'].get('redistribution') == 'citation-only',
                'Rights must be recorded; originals are citation-only and never committed')
        require(s.get('independenceKey') and s.get('publisher'), 'Source independence key/publisher required')
        for key in ('publicationDate', 'effectiveDate', 'observedOn'):
            if s.get(key) is not None:
                dt.date.fromisoformat(s[key])
        require(s.get('observedOn'), 'Observation date required')
        require(s.get('citations'), 'Locked source lacks citations')
        for c in s['citations']:
            require(isinstance(c.get('quote'), str) and 0 < len(c['quote']) <= MAX_QUOTE, 'Citation must be a short excerpt')
            require(c['characterEnd'] - c['characterStart'] == len(c['quote']), 'Citation span and quote length disagree')
            require(c.get('quoteSha256') == sha_bytes(c['quote'].encode()), 'Citation quote hash mismatch')
            require(c.get('recordIds'), 'Citation must name the records it supports')
            for d in c.get('dates', []):
                require(d.get('kind') in BOUND_KINDS | FORBIDDEN_KINDS, 'Unknown date kind')
                dt.date.fromisoformat(d['date'])
    return {s['sourceId']: s for s in lock['sources']}


def verify_originals(lock, records, workdir, fetcher=None):
    """Acquire every original, check bytes, independent extraction and each citation."""
    fetcher = fetcher or fetch
    sources = validate_evidence_lock(lock, records)
    out = []
    for sid, s in sorted(sources.items()):
        data = fetcher(s['url'])
        original = sha_bytes(data)
        require(original == s['originalSha256'], 'Original bytes changed: ' + sid)
        cache = Path(workdir) / original
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(data)
        text = extract(data, s['extractor'])
        require(sha_bytes(text.encode()) == s['textSha256'], 'Independent extraction differs: ' + sid)
        for c in s['citations']:
            require(text[c['characterStart']:c['characterEnd']] == c['quote'], 'Citation position/content mismatch: ' + sid)
        out.append({'sourceId': sid, 'originalSha256': original, 'textSha256': s['textSha256'],
                    'extractor': s['extractor'], 'citationsVerified': len(s['citations']), 'bytes': len(data)})
    return {'format': FORMAT, 'mode': 'live-acquisition', 'evidenceLockSha256': sha(lock),
            'verifiedAt': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            'sources': out, 'originalsCommitted': False,
            'note': 'Originals and full extractions stay in ignored work/; only hashes and short citations are committed.'}


def check_receipt(receipt, lock):
    require(receipt.get('format') == FORMAT and receipt.get('mode') == 'live-acquisition' and
            receipt.get('evidenceLockSha256') == sha(lock) and receipt.get('originalsCommitted') is False,
            'Original-verification receipt is missing, stale or not a live acquisition')
    by_id = {s['sourceId']: s for s in lock['sources']}
    require(sorted(by_id) == [r['sourceId'] for r in receipt['sources']], 'Receipt does not cover every locked source')
    for r in receipt['sources']:
        s = by_id[r['sourceId']]
        require(r['originalSha256'] == s['originalSha256'] and r['textSha256'] == s['textSha256'] and
                r['citationsVerified'] == len(s['citations']), 'Receipt detached from evidence lock')


# ------------------------------------------------------------------- gate ---

def _interval_dates(record):
    return [('validFrom.earliest', record['validFrom']['earliest']), ('validFrom.latest', record['validFrom']['latest']),
            ('validTo.earliest', record['validTo']['earliest']), ('validTo.latest', record['validTo']['latest'])]


def check_dates(records, dossier, sources):
    """Every non-null interval bound needs a cited, admissible date basis."""
    entries = {d['recordId']: d for d in dossier}
    for r in records:
        if r['collection'] not in ('assignments', 'names'):
            continue
        record, entry = r['record'], entries.get(r['id'])
        require(entry is not None, 'Missing dossier entry for ' + r['id'])
        basis = {b['bound']: b for b in entry.get('boundBasis', [])}
        for bound, value in _interval_dates(record):
            if value is None:
                continue
            b = basis.get(bound)
            require(b is not None, 'Unproven interval bound %s of %s' % (bound, r['id']))
            require(b.get('kind') in BOUND_KINDS, 'Date kind %r cannot bound a code/name interval' % b.get('kind'))
            source = sources.get(b.get('sourceId'))
            require(source is not None and b['sourceId'] in record['sourceIds'], 'Bound basis source not linked to record')
            cited = [d for c in source['citations'] if r['id'] in c['recordIds'] for d in c.get('dates', [])]
            require({'kind': b['kind'], 'date': b['date']} in [{'kind': d['kind'], 'date': d['date']} for d in cited],
                    'Bound basis date is not cited in the original for ' + r['id'])
            delta = (dt.date.fromisoformat(value) - dt.date.fromisoformat(b['date'])).days
            require(delta in ALLOWED_DELTAS.get((b['kind'], bound), ()),
                    'Interval bound %s of %s does not follow its %s basis date' % (bound, r['id'], b['kind']))
        for side in ('validFrom', 'validTo'):
            if record[side].get('precision') == 'day':
                require(record[side]['earliest'] and record[side]['latest'] and
                        (dt.date.fromisoformat(record[side]['latest']) - dt.date.fromisoformat(record[side]['earliest'])).days == 1 and
                        basis.get(side + '.earliest', {}).get('kind') in ('code_effective', 'name_effective'),
                        'Day precision needs one documented effective date: ' + r['id'])


def check_fields(records, dossier):
    """New verified timezones or official names need their own explicit approval entry."""
    entries = {d['recordId']: d for d in dossier}
    for r in records:
        if r['collection'] != 'airports':
            continue
        approved = set(entries.get(r['id'], {}).get('approvedFieldUpgrades', []))
        record = r['record']
        if record.get('timezone', {}).get('status') not in (None, 'unknown'):
            require('timezone' in approved, 'Unapproved timezone upgrade: ' + r['id'])
        if record.get('name', {}).get('status') == 'verified':
            require('name' in approved, 'Unapproved official-name upgrade: ' + r['id'])
        if record.get('coordinates', {}).get('status') == 'verified':
            require('coordinates' in approved, 'Unapproved coordinate upgrade: ' + r['id'])


def node_json(script, *args):
    out = subprocess.run(['node', '--input-type=module', '-e', script, *map(str, args)], cwd=ROOT,
                         check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


VALIDATE_JS = '''import {readFileSync} from "node:fs";
import {validateDataset} from "./src/validate.ts";
const r = validateDataset(JSON.parse(readFileSync(process.argv[1], "utf8")));
process.stdout.write(JSON.stringify(r));'''

MEASURE_JS = '''import {readFileSync} from "node:fs";
import {measure} from "./scripts/evidence/policy_coverage.ts";
const read = p => JSON.parse(readFileSync(p, "utf8"));
const m = measure(read(process.argv[1]), read(process.argv[2]));
process.stdout.write(JSON.stringify(m));'''


def build_candidate(base, records, target):
    candidate = json.loads(json.dumps(base))
    candidate['dataVersion'] = target
    for r in records:
        candidate[r['collection']].append(r['record'])
    return candidate


def gate(base, candidate, records, batches, dossier, sources):
    """Run the existing gates plus the batch-exactness checks; return coverage."""
    from admissions import validate_admission
    from review import validate_batch_series
    require(version_tuple(candidate['dataVersion']) > version_tuple(base['dataVersion']), 'Increasing dataVersion required')
    expected = build_candidate(base, records, candidate['dataVersion'])
    require(candidate == expected, 'Candidate is not exactly the published base plus the approved records')
    for collection, field in COLLECTIONS.items():
        ids = [r[field] for r in candidate[collection]]
        require(len(ids) == len(set(ids)), 'Duplicate %s in candidate' % field)
    existing = [load(p) for p in sorted((ROOT / 'research/discovery/batches').glob('*.json'))]
    validate_batch_series([*existing, *batches])
    counts = validate_admission(base, candidate, batches, dossier)  # human path: no policy_context
    new_sources = {r['id'] for r in records if r['collection'] == 'sources'}
    used = {s for r in records if r['collection'] in ('assignments', 'names') for s in r['record']['sourceIds']}
    used |= {s for r in records if r['collection'] == 'airports' for s in r['record']['coordinates']['sourceIds']}
    require(new_sources == set(sources), 'Every new formal source must be locked original evidence, and vice versa')
    require(new_sources <= used, 'Unused formal source in batch')
    check_dates(records, dossier, sources)
    check_fields(records, dossier)
    with tempfile.TemporaryDirectory(dir=ROOT / 'work') as tmp:
        bp, cp = Path(tmp) / 'base.json', Path(tmp) / 'candidate.json'
        bp.write_text(json.dumps(base))
        cp.write_text(json.dumps(candidate))
        before, after = node_json(VALIDATE_JS, bp), node_json(VALIDATE_JS, cp)
        require(not after['errors'], 'Schema/semantic gate: ' + '; '.join(after['errors']))
        new_ids = {r['id'] for r in records}
        added = [w for w in after['warnings'] if w not in before['warnings']]
        unhandled = [w for w in added if w.startswith('Unconfirmed') and any(i in w for i in new_ids)]
        require(not unhandled, 'Unhandled overlap/conflict: ' + '; '.join(unhandled))
        try:
            coverage = node_json(MEASURE_JS, bp, cp)
        except subprocess.CalledProcessError as error:
            raise AdmissionError('Production resolver differential failed: ' + error.stderr[-800:])
    transitions = coverage['transitions']
    summary = {
        'newResolved': sum(v for k, v in transitions.items() if k.endswith('->resolved') and not k.startswith('resolved')),
        'newUncertain': sum(v for k, v in transitions.items() if k.endswith('->uncertain') and not k.startswith('uncertain')),
        'newConflicts': coverage['newConflicts'], 'removedConflicts': coverage['removedConflicts'],
        'changedPublishedResolved': coverage['changedPublishedResolved'],
        'changedExistingAnswers': coverage['changedExistingAnswers'],
        'codeQueries': coverage['codeQueries'], 'interval': coverage['interval'], 'localDates': coverage['localDates'],
        'mode': 'candidate-prepublication', 'formalCoverage': False,
        'note': 'Production resolveAirport() differential on the candidate. Formal coverage exists only after the data PR merges.',
    }
    return {'admittedCounts': counts, 'coverage': summary, 'newWarnings': added}


# --------------------------------------------------------------- manifest ---

def manifest_for(bundle, spec_meta, baseline, candidate, records, lock, batches, dossier, excluded, coverage):
    return {
        'format': FORMAT, 'batchId': spec_meta['batchId'], 'reviewedOn': spec_meta['reviewedOn'],
        'baseCommit': baseline['baseCommit'], 'baseDataVersion': baseline['baseDataVersion'],
        'baseSnapshot': baseline['baseSnapshot'], 'baseDataSha256': baseline['baseDataSha256'],
        'targetDataVersion': candidate['dataVersion'], 'candidateSha256': sha(candidate),
        'recordsSha256': sha(records), 'evidenceLockSha256': sha(lock),
        'reviewBatchesSha256': sha(batches), 'dossierSha256': sha(dossier), 'excludedSha256': sha(excluded),
        'coverageSha256': sha(coverage), 'executorSha256': executor()['executorSha256'],
        'counts': {c: sum(r['collection'] == c for r in records) for c in COLLECTIONS},
        'recordIds': {c: [r['id'] for r in records if r['collection'] == c] for c in COLLECTIONS},
        'excludedIds': sorted(e['recordId'] for e in excluded),
    }


def approval_text(manifest):
    m = manifest
    lines = [
        'Approve Keepraw human admission batch %s (%s)' % (m['batchId'], FORMAT),
        'manifest-sha256:%s' % sha(m),
        'base-commit:%s base-data:%s sha256:%s' % (m['baseCommit'], m['baseDataVersion'], m['baseDataSha256']),
        'candidate:%s sha256:%s' % (m['targetDataVersion'], m['candidateSha256']),
        'records-sha256:%s evidence-lock-sha256:%s' % (m['recordsSha256'], m['evidenceLockSha256']),
        'executor-sha256:%s' % m['executorSha256'],
    ]
    for c in ('airports', 'assignments', 'names', 'sources'):
        ids = m['recordIds'][c]
        lines.append('%s (%d): %s' % (c, len(ids), ', '.join(ids) if ids else 'none'))
    lines.append('Excluded, not approved (%d): %s' % (len(m['excludedIds']), ', '.join(m['excludedIds']) or 'none'))
    lines.append('This approves exactly the records listed above, with the exact content bound by records-sha256, '
                 'for this one batch only. It approves no other record, batch, country, code type or later change. '
                 'Final merge of the data pull request remains a separate Owner decision.')
    return '\n'.join(lines)


# ----------------------------------------------------------------- github ---

def github(path):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        request = urllib.request.Request('https://api.github.com/' + path, headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
            'User-Agent': 'keepraw-airport-history human-v1'})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def read_owner_comment(url, expected_text, reader=None):
    """Fetch the real comment; never accept an offline or fixture authority."""
    reader = reader or github
    match = re.fullmatch(r'https://github\.com/keepraw/airport-history/(?:issues|pull)/(\d+)#issuecomment-(\d+)', url or '')
    require(match, 'Exact keepraw/airport-history issue-comment URL required')
    repo = reader('repos/' + REPOSITORY)
    require(repo['owner']['login'] == OWNER['login'] and repo['owner']['id'] == OWNER['id'], 'Repository owner identity changed')
    c = reader('repos/%s/issues/comments/%s' % (REPOSITORY, match[2]))
    require(c.get('html_url') == url and c.get('issue_url') ==
            'https://api.github.com/repos/%s/issues/%s' % (REPOSITORY, match[1]), 'Comment does not belong to this repository/issue')
    require(c['user']['login'] == OWNER['login'] and c['user']['id'] == OWNER['id'] and c['user'].get('type') == 'User',
            'Approval comment is not by Owner keepraw (49091395)')
    require(c['body'].replace('\r\n', '\n').strip() == expected_text, 'Approval text does not exactly match this batch')
    now = dt.datetime.now(dt.timezone.utc)
    for k in ('created_at', 'updated_at'):
        require(dt.datetime.fromisoformat(c[k].replace('Z', '+00:00')) <= now, 'Future approval timestamp')
    require(c['created_at'] <= c['updated_at'], 'Invalid approval timestamps')
    return {'html_url': c['html_url'], 'author': {'login': c['user']['login'], 'id': c['user']['id']},
            'created_at': c['created_at'], 'updated_at': c['updated_at'],
            'bodySha256': sha_bytes(expected_text.encode())}


# --------------------------------------------------------------- validate ---

def load_bundle(bundle):
    names = ('manifest', 'records', 'evidence-lock', 'dossier', 'excluded', 'coverage', 'proposed-data')
    out = {n: load(bundle / (n + '.json')) for n in names}
    out['batches'] = [load(p) for p in sorted((bundle / 'batches').glob('*.json'))]
    for optional in ('approval', 'original-verification'):
        path = bundle / (optional + '.json')
        out[optional] = load(path) if path.exists() else None
    return out


def validate_bundle(bundle, *, reader=None, require_approval=True, root=ROOT):
    b = load_bundle(bundle)
    m, records = b['manifest'], b['records']['records']
    require(m.get('format') == FORMAT, 'Not a human-v1 bundle')
    require(bundle.parent.name == m['targetDataVersion'], 'Bundle directory does not match target dataVersion')
    baseline, base = published_baseline(m['baseCommit'], root)
    for key in ('baseDataVersion', 'baseSnapshot', 'baseDataSha256'):
        require(m[key] == baseline[key], 'Base main or base data hash changed')
    require((root / baseline['baseSnapshot']).read_bytes() == subprocess.check_output(
        ['git', 'show', m['baseCommit'] + ':data/airports.json'], cwd=root), 'Immutable base snapshot changed')
    require(m['executorSha256'] == executor(root)['executorSha256'], 'Executor changed since this batch was built')
    check_single_active(m['targetDataVersion'], m['baseDataVersion'], records, root)
    hashes = {'candidateSha256': b['proposed-data'], 'recordsSha256': records, 'evidenceLockSha256': b['evidence-lock'],
              'reviewBatchesSha256': b['batches'], 'dossierSha256': b['dossier'], 'excludedSha256': b['excluded'],
              'coverageSha256': b['coverage']}
    for key, value in hashes.items():
        require(m[key] == sha(value), 'Bundle file changed after build: ' + key)
    require(m['recordIds'] == {c: [r['id'] for r in records if r['collection'] == c] for c in COLLECTIONS},
            'Manifest record list differs from records')
    sources = validate_evidence_lock(b['evidence-lock'], records)
    check_receipt(b['original-verification'] or {}, b['evidence-lock'])
    excluded = {e['recordId'] for e in b['excluded']}
    candidate_ids = {r[f] for c, f in COLLECTIONS.items() for r in b['proposed-data'][c]}
    require(not (excluded & candidate_ids), 'Excluded candidate entered formal data')
    approval = None
    if require_approval:
        recorded = b['approval']
        require(recorded is not None, 'No Owner approval recorded for this batch')
        text = approval_text(m)
        require(recorded.get('manifestSha256') == sha(m) and recorded.get('approvalTextSha256') == sha_bytes(text.encode()),
                'Recorded approval is bound to a different manifest/text')
        live = read_owner_comment(recorded['comment']['html_url'], text, reader)
        require(live == recorded['comment'], 'Owner approval edited, revoked or fabricated')
        approval = live
    result = gate(base, b['proposed-data'], records, b['batches'], b['dossier'], sources)
    require(result['coverage'] == b['coverage'], 'Resolver differential differs from the recorded coverage')
    return {'manifest': m, 'gate': result, 'approval': approval, 'originals': 'offline-receipt-replay'}


# --------------------------------------------------------------------- ci ---

SETUP_COMMANDS = {'pnpm install --frozen-lockfile'}
LEGACY_WORKFLOWS = ('ci.yml', 'kr-admission.yml', 'rule-admission.yml')
# Checks that pin the exact 0.10.0 formal bytes, Korean/AAI fingerprints or data
# counts. They cannot hold on a newer dataVersion without editing protected
# executors, so they run unchanged in the frozen published tree only.
DATA_PINNED = {
    'pnpm validate:admission': 'policy_formal.py accepts only AAI policy receipts for a new dataVersion; its 0.10.0 replay runs in the frozen tree. The other four replays run below.',
    'pnpm evidence:priority-markets validate': 'priority-markets baseline lock pins data/airports.json bytes',
    'pnpm policy:validate': 'policy report pins the 0.9.0/0.10.0 simulation inputs',
    'pnpm test': 'three vitest files assert exact boundary counts of the published data; all others run below',
    'pnpm test:evidence': 'two Korean tests pin research fingerprints that include data/airports.json and the Global Batch 5 research validator asserts data 0.10.0; all others run below',
    'python3 scripts/admission/kr_verify.py validate': 'Korean protected baseline pins data/airports.json',
    'python3 scripts/admission/kr_rehearsal.py': 'Korean fingerprints include data/airports.json',
    'python3 admission/v1/verify.py': 'rule-v1 verify hard-codes dataVersion 0.10.0 and its counts',
    'python3 admission/v1/test_engine.py': 'rule-v1 rehearsal requires its own increasing dataVersion over 0.10.0',
}
CURRENT_REPLACEMENTS = {
    'pnpm validate:admission': ['python3 scripts/evidence/admitted.py', 'python3 scripts/evidence/admitted_090.py',
                                'node scripts/evidence/admission_090_coverage.ts validate',
                                'node scripts/evidence/admission_0100_coverage.ts validate'],
    'pnpm test': ['npx vitest run --exclude test/names.test.ts --exclude test/pr9-admissions.test.ts '
                  '--exclude test/validate.test.ts'],
    'pnpm test:evidence': ['python3 admission/human-v1/evidence_tests.py'],
}


def workflow_commands(root):
    """Every single-line run step of the legacy workflows, in order (setup steps excluded)."""
    commands = []
    for name in LEGACY_WORKFLOWS:
        path = root / '.github/workflows' / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            match = re.fullmatch(r'\s*(?:- )?run:\s*(.*?)\s*', line)
            if not match:
                continue
            run = match[1]
            require(run and run not in ('|', '>'), 'Multi-line legacy run step is not supported: ' + name)
            if run not in SETUP_COMMANDS and not run.startswith('command -v pdftotext'):
                commands.append(run)
    return commands


def run_all(commands, cwd):
    env = dict(os.environ)
    for command in commands:
        print('::group::' + command, flush=True)
        subprocess.run(command, shell=True, cwd=cwd, check=True, env=env)
        print('::endgroup::', flush=True)


def frozen_tree(commit, tmp):
    root = Path(tmp)
    archive = subprocess.check_output(['git', 'archive', commit], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(root, filter='data')
    (root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    subprocess.run(['git', 'fetch', '--quiet', str(ROOT), commit, '+refs/heads/main:refs/remotes/origin/main'],
                   cwd=root, check=False)
    subprocess.run(['git', 'fetch', '--quiet', str(ROOT), commit], cwd=root, check=True)
    subprocess.run(['git', 'reset', '--quiet', commit], cwd=root, check=True)
    subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', commit], cwd=root, check=True)
    return root


def ci():
    current = load(ROOT / 'data/airports.json')
    bundle = bundle_dir(current['dataVersion'])
    if not bundle.exists():
        legacy = workflow_commands(ROOT)
        require(legacy, 'No legacy workflows and no human-v1 release: refusing an empty CI')
        print('No human-v1 release at dataVersion %s; the legacy workflows own CI unchanged. '
              'Human-v1 entry checked executor %s.' % (current['dataVersion'], executor()['executorSha256']))
        return
    proof = validate_bundle(bundle)
    m = proof['manifest']
    require(load(bundle / 'proposed-data.json') == current, 'Published data detached from its approved candidate')
    require((ROOT / ('test/curated-%s.json' % m['targetDataVersion'])).read_bytes() ==
            (ROOT / 'data/airports.json').read_bytes(), 'Immutable snapshot of this release missing or different')
    require(load(ROOT / 'package.json')['version'] == current['dataVersion'], 'package.json version detached from data')
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='frozen-', dir=WORK) as tmp:
        root = frozen_tree(m['baseCommit'], tmp)
        frozen_version = load(root / 'data/airports.json')['dataVersion']
        if (root / 'admission/human-v1/human.py').exists() and bundle_dir(frozen_version, root).exists():
            run_all(['python3 admission/human-v1/human.py ci'], root)  # recursive replay of an earlier human release
        else:
            legacy = workflow_commands(root)
            require(sorted(legacy) == sorted(LEGACY_CURRENT_COMMANDS),
                    'Frozen legacy workflows differ from the declared legacy check list')
            run_all(legacy, root)
    commands = []
    for command in dict.fromkeys(LEGACY_CURRENT_COMMANDS):
        commands.extend(CURRENT_REPLACEMENTS.get(command, [] if command in DATA_PINNED else [command]))
    run_all(commands, ROOT)
    print('Human-v1 release %s validated: Owner approval re-read live, offline original-verification receipt replayed '
          '(no original bytes on CI), frozen %s legacy CI replayed unchanged, current-tree checks passed.'
          % (m['targetDataVersion'], m['baseCommit'][:12]))


# The full legacy command list at the time Human v1 was introduced (main 5c54ab3).
# The router refuses to run if the frozen tree's workflows list a data-pinned
# check that is not here, so no check can silently disappear.
LEGACY_CURRENT_COMMANDS = (
    'pnpm typecheck', 'pnpm validate:data', 'pnpm validate:admission', 'pnpm test', 'pnpm test:research',
    'pnpm research:validate', 'pnpm reference:validate', 'pnpm test:reference', 'pnpm evidence:validate',
    'pnpm evidence:global validate', 'pnpm evidence:markets validate', 'pnpm evidence:transfers validate',
    'pnpm evidence:priority-markets validate', 'pnpm evidence:first-admission validate', 'pnpm policy:validate',
    'pnpm evidence:history', 'pnpm test:evidence', 'pnpm build', 'pnpm policy:rehearse',
    'python3 scripts/admission/kr_verify.py validate', 'python3 scripts/admission/kr_rehearsal.py',
    'python3 scripts/evidence/korea_readiness.py rights', 'python3 admission/v1/verify.py',
    'python3 admission/v1/test_registration.py', 'python3 admission/v1/test_engine.py',
    'python3 scripts/evidence/korea_readiness.py rights',  # listed in both Korean and rule workflows
)
