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
import threading
import time
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

def current_main(root=ROOT, refresh=False):
    """The published main commit. ``refresh`` first fetches it from origin (local CLI steps)."""
    if refresh and subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=root, capture_output=True).returncode == 0:
        fetched = subprocess.run(['git', 'fetch', '--quiet', 'origin', '+refs/heads/main:refs/remotes/origin/main'],
                                 cwd=root, capture_output=True, text=True)
        require(fetched.returncode == 0, 'Cannot confirm the current published main: ' + fetched.stderr.strip()[-300:])
    main = subprocess.run(['git', 'rev-parse', '--verify', '--quiet', 'origin/main^{commit}'], cwd=root,
                          capture_output=True, text=True).stdout.strip()
    require(main, 'Published main (origin/main) unavailable')
    return main


def require_fresh(base_commit, root=ROOT, refresh=True):
    """A pending batch must sit exactly on the current published main.

    If main advanced, the candidate, original verification and Owner approval
    are all stale: prepare, verify-originals and build again on the new main
    and obtain a new Owner approval.
    """
    main = current_main(root, refresh)
    require(base_commit == main, 'Published main advanced from %s to %s since this batch was prepared: prepare, '
            'verify-originals and build again on the new main and obtain a new Owner approval'
            % (base_commit[:12], main[:12]))
    return main


def data_version_at(commit, root=ROOT):
    try:
        return json.loads(subprocess.check_output(['git', 'show', commit + ':data/airports.json'], cwd=root,
                                                  stderr=subprocess.DEVNULL))['dataVersion']
    except subprocess.CalledProcessError:
        return None


def publishing_commit(version, head='HEAD', root=ROOT):
    """First commit on HEAD's first-parent chain whose data is ``version``, and its first parent.

    On a pull_request checkout HEAD is GitHub's test merge (first parent: the
    current main tip); on a main push it is main itself. Either way the
    first-parent chain is main's own history plus, at most, the PR merge.
    """
    chain = git('rev-list', '--first-parent', head, cwd=root).split()
    require(chain and data_version_at(chain[0], root) == version, 'HEAD does not carry dataVersion ' + version)
    for index, commit in enumerate(chain):
        parent = chain[index + 1] if index + 1 < len(chain) else None
        if parent is None or data_version_at(parent, root) != version:
            return commit, parent
    raise AdmissionError('unreachable')


def check_release_lineage(manifest, root=ROOT):
    """The release must be published directly on its approved base, never on a stale or rebased one.

    * Pending (main does not carry the release yet, i.e. the data PR's CI): the
      current main must still be exactly the approved base.
    * Published or pending: the first commit on HEAD's first-parent chain that
      carries the release must have the approved base as its first parent. This
      holds for a merge commit, a squash and a single-commit rebase made while
      main == base, and for every later main commit. It fails for an old PR re-run
      after main advanced, and for a merge on top of a newer main.
    """
    version, base = manifest['targetDataVersion'], manifest['baseCommit']
    main = current_main(root)
    if data_version_at(main, root) != version:
        require(main == base, 'Published main advanced from %s to %s after this batch was approved: rebuild on the new '
                'main and obtain a new Owner approval' % (base[:12], main[:12]))
    else:
        require(subprocess.run(['git', 'merge-base', '--is-ancestor', main, 'HEAD'], cwd=root).returncode == 0,
                'HEAD does not contain the current published main')
    publisher, parent = publishing_commit(version, 'HEAD', root)
    require(parent == base, 'Release %s was published by %s on parent %s, not on its approved base %s'
            % (version, publisher[:12], (parent or 'none')[:12], base[:12]))
    return {'publishingCommit': publisher, 'baseCommit': base, 'currentMain': main}


def published_baseline(base_commit, root=ROOT):
    """The base must be a published main commit whose data equals its immutable snapshot.

    Ancestry (not equality) is checked here so historical releases replay; the
    freshness of a pending batch is ``require_fresh`` and, in CI,
    ``check_release_lineage``.
    """
    require(re.fullmatch(r'[0-9a-f]{40}', base_commit or ''), 'Full base commit SHA required')
    main = current_main(root)
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


RECEIPT_KEYS = {'format', 'mode', 'evidenceLockSha256', 'verifiedAt', 'sources', 'originalsCommitted', 'note'}
RECEIPT_SOURCE_KEYS = {'sourceId', 'originalSha256', 'textSha256', 'extractor', 'citationsVerified', 'bytes'}


def check_receipt(receipt, lock):
    """The complete original-verification receipt must match the lock exactly.

    Its full hash is also bound into the manifest (``originalVerificationSha256``)
    and so into the Owner approval text: any re-verification, edit or replacement
    of the receipt voids the approval.
    """
    require(isinstance(receipt, dict) and set(receipt) == RECEIPT_KEYS and receipt.get('format') == FORMAT and
            receipt.get('mode') == 'live-acquisition' and receipt.get('evidenceLockSha256') == sha(lock) and
            receipt.get('originalsCommitted') is False and isinstance(receipt.get('note'), str),
            'Original-verification receipt is missing, stale or not a live acquisition')
    try:
        verified = dt.datetime.fromisoformat(receipt['verifiedAt'])
    except (TypeError, ValueError):
        raise AdmissionError('Original-verification receipt has no valid verifiedAt')
    require(verified.tzinfo is not None and verified <= dt.datetime.now(dt.timezone.utc),
            'Original-verification receipt verifiedAt must be a past UTC time')
    require(isinstance(receipt['sources'], list), 'Original-verification receipt lacks its source list')
    by_id = {s['sourceId']: s for s in lock['sources']}
    listed = [r.get('sourceId') if isinstance(r, dict) else None for r in receipt['sources']]
    require(listed == sorted(by_id), 'Receipt does not cover every locked source exactly once, in order')
    for r in receipt['sources']:
        s = by_id[r['sourceId']]
        require(set(r) == RECEIPT_SOURCE_KEYS, 'Receipt source entry has missing or extra fields: ' + r['sourceId'])
        require(r['originalSha256'] == s['originalSha256'] and r['textSha256'] == s['textSha256'] and
                r['extractor'] == s['extractor'] and r['citationsVerified'] == len(s['citations']) and
                isinstance(r['bytes'], int) and not isinstance(r['bytes'], bool) and r['bytes'] > 0,
                'Receipt detached from evidence lock: ' + r['sourceId'])


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
    (ROOT / 'work').mkdir(exist_ok=True)  # ignored; absent in a fresh CI checkout and in frozen trees
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

def manifest_for(bundle, spec_meta, baseline, candidate, records, lock, batches, dossier, excluded, coverage, receipt):
    return {
        'format': FORMAT, 'batchId': spec_meta['batchId'], 'reviewedOn': spec_meta['reviewedOn'],
        'baseCommit': baseline['baseCommit'], 'baseDataVersion': baseline['baseDataVersion'],
        'baseSnapshot': baseline['baseSnapshot'], 'baseDataSha256': baseline['baseDataSha256'],
        'targetDataVersion': candidate['dataVersion'], 'candidateSha256': sha(candidate),
        'recordsSha256': sha(records), 'evidenceLockSha256': sha(lock),
        'reviewBatchesSha256': sha(batches), 'dossierSha256': sha(dossier), 'excludedSha256': sha(excluded),
        'coverageSha256': sha(coverage), 'executorSha256': executor()['executorSha256'],
        'originalVerificationSha256': sha(receipt),
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
        'original-verification-sha256:%s' % m['originalVerificationSha256'],
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


def validate_bundle(bundle, *, reader=None, require_approval=True, root=ROOT, fresh=True):
    """Re-run every check. ``fresh``: the batch must sit on the current main (all pre-merge steps);
    CI instead checks the release lineage (``check_release_lineage``)."""
    b = load_bundle(bundle)
    m, records = b['manifest'], b['records']['records']
    require(m.get('format') == FORMAT, 'Not a human-v1 bundle')
    require(bundle.parent.name == m['targetDataVersion'], 'Bundle directory does not match target dataVersion')
    baseline, base = published_baseline(m['baseCommit'], root)
    if fresh:
        require_fresh(m['baseCommit'], root, refresh=False)
    for key in ('baseDataVersion', 'baseSnapshot', 'baseDataSha256'):
        require(m[key] == baseline[key], 'Base main or base data hash changed')
    require((root / baseline['baseSnapshot']).read_bytes() == subprocess.check_output(
        ['git', 'show', m['baseCommit'] + ':data/airports.json'], cwd=root), 'Immutable base snapshot changed')
    require(m['executorSha256'] == executor(root)['executorSha256'], 'Executor changed since this batch was built')
    check_single_active(m['targetDataVersion'], m['baseDataVersion'], records, root)
    hashes = {'candidateSha256': b['proposed-data'], 'recordsSha256': records, 'evidenceLockSha256': b['evidence-lock'],
              'reviewBatchesSha256': b['batches'], 'dossierSha256': b['dossier'], 'excludedSha256': b['excluded'],
              'coverageSha256': b['coverage'], 'originalVerificationSha256': b['original-verification']}
    for key, value in hashes.items():
        require(m[key] == sha(value), 'Bundle file changed after build: ' + key)
    require(m['recordIds'] == {c: [r['id'] for r in records if r['collection'] == c] for c in COLLECTIONS},
            'Manifest record list differs from records')
    sources = validate_evidence_lock(b['evidence-lock'], records)
    check_receipt(b['original-verification'], b['evidence-lock'])
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
    'python3 scripts/evidence/korea_readiness.py rights': 'its priority-markets entry check pins the 0.10.0 data/airports.json bytes and version; the full ancestry/blob audit runs below via rights.py',
}
CURRENT_REPLACEMENTS = {
    'pnpm validate:admission': ['python3 scripts/evidence/admitted.py', 'python3 scripts/evidence/admitted_090.py',
                                'node scripts/evidence/admission_090_coverage.ts validate',
                                'node scripts/evidence/admission_0100_coverage.ts validate'],
    'pnpm test': ['npx vitest run --exclude test/names.test.ts --exclude test/pr9-admissions.test.ts '
                  '--exclude test/validate.test.ts'],
    'pnpm test:evidence': ['python3 admission/human-v1/evidence_tests.py'],
    'python3 scripts/evidence/korea_readiness.py rights': ['python3 admission/human-v1/rights.py'],
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


# The frozen tree replays only the data-pinned checks: everything else runs on the
# release tree itself (or via its replacement), so each legacy check runs exactly once.
# test:evidence is pinned only for the FROZEN_ONLY tests of evidence_tests.py; the
# frozen tree runs exactly those, the current tree all the others.
FROZEN_EVIDENCE = 'python3 %s --frozen-only' % (HERE / 'evidence_tests.py')
FROZEN_REPLACEMENTS = {'pnpm test:evidence': [FROZEN_EVIDENCE]}
# Long commands run after every quick check of both trees has passed.
HEAVY = {'pnpm policy:rehearse', 'python3 admission/human-v1/evidence_tests.py', FROZEN_EVIDENCE}
# Release-compatibility checks that fail in seconds: run before anything else.
FIRST = ('python3 scripts/evidence/korea_readiness.py rights', 'python3 admission/human-v1/rights.py')
HEARTBEAT_SECONDS = 60
TIMINGS = []


def route_plan(legacy):
    """(frozen, current): every legacy check routed to exactly one tree, data-pinned ones frozen-only."""
    frozen, current = [], []
    for command in dict.fromkeys(legacy):
        if command in DATA_PINNED:
            frozen.extend(FROZEN_REPLACEMENTS.get(command, [command]))
        current.extend(CURRENT_REPLACEMENTS.get(command, [] if command in DATA_PINNED else [command]))
    for command in set(legacy):
        require(command in DATA_PINNED or command in current or command in CURRENT_REPLACEMENTS,
                'Legacy check not routed to any tree: ' + command)
    require(not set(DATA_PINNED) & set(current), 'Data-pinned check routed to the current tree')
    return frozen, current


def phases(commands):
    """Quick commands first (release-compatibility checks at the very front), heavy ones last; order otherwise kept."""
    quick = [c for c in commands if c not in HEAVY]
    quick = [c for c in quick if c in FIRST] + [c for c in quick if c not in FIRST]
    return quick, [c for c in commands if c in HEAVY]


def execute(command, cwd):
    subprocess.run(command, shell=True, cwd=cwd, check=True, env=dict(os.environ))


def run_all(commands, cwd, label='current'):
    for index, command in enumerate(commands, 1):
        started = time.monotonic()
        print('::group::[%s %d/%d] %s' % (label, index, len(commands), command), flush=True)
        done = threading.Event()

        def heartbeat():
            while not done.wait(HEARTBEAT_SECONDS):
                print('[human-v1] still running [%s] %s: %dm%02ds' % ((label, command) + divmod(int(time.monotonic() - started), 60)),
                      flush=True)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            execute(command, cwd)
        finally:
            done.set()
            seconds = time.monotonic() - started
            TIMINGS.append((label, command, round(seconds, 1)))
            print('::endgroup::', flush=True)
            print('[human-v1] [%s] %s: %.1fs' % (label, command, seconds), flush=True)


def frozen_tree(commit, tmp):
    root = Path(tmp)
    archive = subprocess.check_output(['git', 'archive', commit], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(root, filter='data')
    (root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
    subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
    # .gitignore's 'node_modules/' matches directories only; git sees this symlink as a
    # file, and policy_rehearsal refuses symlinked inputs. Exclude it locally.
    with (root / '.git/info/exclude').open('a') as exclude:
        exclude.write('\nnode_modules\n')
    subprocess.run(['git', 'fetch', '--quiet', str(ROOT), commit, '+refs/heads/main:refs/remotes/origin/main'],
                   cwd=root, check=False, stderr=subprocess.DEVNULL)  # optional: a checkout may have no local main
    subprocess.run(['git', 'fetch', '--quiet', str(ROOT), commit], cwd=root, check=True)
    subprocess.run(['git', 'reset', '--quiet', commit], cwd=root, check=True)
    subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', commit], cwd=root, check=True)
    return root


def require_clean_tree(root, what):
    """Untracked inputs (a stray symlink, a generated file) fail here in seconds, not after a 15-minute rehearsal."""
    status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=root, capture_output=True,
                            text=True, check=True).stdout.strip()
    require(not status, '%s tree has untracked or modified files: %s' % (what, status[:300]))
    links = [p for p in subprocess.check_output(['git', 'ls-files', '-s'], cwd=root, text=True).splitlines()
             if p.startswith('120000 ')]
    require(not links, '%s tree tracks symlinks: %s' % (what, links[:3]))


def _show(commit, path, root=ROOT):
    return subprocess.check_output(['git', 'show', '%s:%s' % (commit, path)], cwd=root)


def _object(commit, path, root=ROOT):
    return subprocess.run(['git', 'rev-parse', '--verify', '--quiet', '%s:%s' % (commit, path)], cwd=root,
                          capture_output=True, text=True).stdout.strip()


def verify_earlier_releases(base_commit, reader=None, root=ROOT):
    """Walk back through every earlier human release without re-running its CI.

    Each earlier release already passed the full release CI when it was published,
    on bytes that are immutable by commit SHA. Here we prove those bytes are still
    what was approved and published, in O(1) work per release:

    * its bundle directory and ``test/curated-<v>.json`` in HEAD are the exact git
      objects published with it (no later edit, deletion or substitution);
    * every bundle file still hashes to its manifest, the candidate equals the data
      published at that commit and its immutable snapshot;
    * the recorded Owner approval is bound to that manifest and its text, and the
      live GitHub comment still matches it (not edited, revoked or fabricated);
    * the release was published directly on its approved base (release lineage).

    Returns the first commit that is not a human release (the legacy anchor, whose
    data-pinned checks are replayed frozen) and the releases checked, newest first.
    """
    checked, commit = [], base_commit
    while True:
        version = data_version_at(commit, root)
        require(version, 'No formal data at %s' % commit[:12])
        bundle_path = 'research/admissions/%s/human-v1' % version
        published = _object(commit, bundle_path, root)
        if not published:
            return commit, checked
        started = time.monotonic()
        snapshot = 'test/curated-%s.json' % version
        require(_object('HEAD', bundle_path, root) == published, 'Published human-v1 bundle %s changed after release' % version)
        require(_object('HEAD', snapshot, root) == _object(commit, snapshot, root) == _object(commit, 'data/airports.json', root),
                'Immutable snapshot of release %s missing or different' % version)
        with tempfile.TemporaryDirectory(prefix='release-') as tmp:
            archive = subprocess.check_output(['git', 'archive', commit, bundle_path], cwd=root)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(tmp, filter='data')
            b = load_bundle(Path(tmp) / bundle_path)
        m = b['manifest']
        require(m.get('format') == FORMAT and m['targetDataVersion'] == version, 'Release %s manifest is not its own' % version)
        hashes = {'candidateSha256': b['proposed-data'], 'recordsSha256': b['records']['records'],
                  'evidenceLockSha256': b['evidence-lock'], 'reviewBatchesSha256': b['batches'], 'dossierSha256': b['dossier'],
                  'excludedSha256': b['excluded'], 'coverageSha256': b['coverage'],
                  'originalVerificationSha256': b['original-verification']}
        for key, value in hashes.items():
            require(m[key] == sha(value), 'Release %s bundle file changed: %s' % (version, key))
        require(b['proposed-data'] == json.loads(_show(commit, 'data/airports.json', root)),
                'Release %s published data detached from its approved candidate' % version)
        require(m['baseDataSha256'] == sha_bytes(_show(m['baseCommit'], 'data/airports.json', root)),
                'Release %s base data hash changed' % version)
        check_receipt(b['original-verification'], b['evidence-lock'])
        recorded, text = b['approval'], approval_text(m)
        require(recorded and recorded.get('manifestSha256') == sha(m) and
                recorded.get('approvalTextSha256') == sha_bytes(text.encode()),
                'Release %s approval is bound to a different manifest/text' % version)
        require(read_owner_comment(recorded['comment']['html_url'], text, reader) == recorded['comment'],
                'Release %s Owner approval edited, revoked or fabricated' % version)
        publisher, parent = publishing_commit(version, commit, root)
        require(parent == m['baseCommit'], 'Release %s was not published on its approved base' % version)
        checked.append({'dataVersion': version, 'publishingCommit': publisher, 'baseCommit': m['baseCommit'],
                        'seconds': round(time.monotonic() - started, 2)})
        print('[human-v1] earlier release %s verified (published by %s on %s, approval re-read live) in %.2fs'
              % (version, publisher[:12], m['baseCommit'][:12], checked[-1]['seconds']), flush=True)
        commit = m['baseCommit']


def ci():
    started = time.monotonic()
    current = load(ROOT / 'data/airports.json')
    bundle = bundle_dir(current['dataVersion'])
    if not bundle.exists():
        legacy = workflow_commands(ROOT)
        require(legacy, 'No legacy workflows and no human-v1 release: refusing an empty CI')
        print('No human-v1 release at dataVersion %s; the legacy workflows own CI unchanged. '
              'Human-v1 entry checked executor %s.' % (current['dataVersion'], executor()['executorSha256']))
        return
    del TIMINGS[:]
    # -- preflight: everything here takes seconds ---------------------------------
    require(load(bundle / 'proposed-data.json') == current, 'Published data detached from its approved candidate')
    require(load(ROOT / 'package.json')['version'] == current['dataVersion'], 'package.json version detached from data')
    require((ROOT / ('test/curated-%s.json' % current['dataVersion'])).read_bytes() ==
            (ROOT / 'data/airports.json').read_bytes(), 'Immutable snapshot of this release missing or different')
    proof = validate_bundle(bundle, fresh=False)
    m = proof['manifest']
    lineage = check_release_lineage(m)
    print('Release lineage: %s published by %s on approved base %s (current main %s).'
          % (m['targetDataVersion'], lineage['publishingCommit'][:12], m['baseCommit'][:12], lineage['currentMain'][:12]),
          flush=True)
    anchor, earlier = verify_earlier_releases(m['baseCommit'])
    frozen_cmds, current_cmds = route_plan(LEGACY_CURRENT_COMMANDS)
    require_clean_tree(ROOT, 'Release')
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='frozen-', dir=WORK) as tmp:
        root = frozen_tree(anchor, tmp)
        legacy = workflow_commands(root)
        require(sorted(legacy) == sorted(LEGACY_CURRENT_COMMANDS),
                'Frozen legacy workflows differ from the declared legacy check list')
        require_clean_tree(root, 'Frozen')
        frozen_quick, frozen_heavy = phases(frozen_cmds)
        current_quick, current_heavy = phases(current_cmds)
        print('[human-v1] preflight passed in %.1fs: %d earlier human release(s) verified without replay; legacy anchor %s; '
              'plan frozen %d quick + %d heavy, current %d quick + %d heavy'
              % (time.monotonic() - started, len(earlier), anchor[:12], len(frozen_quick), len(frozen_heavy),
                 len(current_quick), len(current_heavy)), flush=True)
        for commands, cwd, label in ((frozen_quick, root, 'frozen'), (current_quick, ROOT, 'current'),
                                     (frozen_heavy, root, 'frozen'), (current_heavy, ROOT, 'current')):
            if commands:
                run_all(commands, cwd, label)
    print('[human-v1] timings: ' + '; '.join('%s %s %.1fs' % t for t in TIMINGS), flush=True)
    print('Human-v1 release %s validated: Owner approval re-read live, offline original-verification receipt replayed '
          '(no original bytes on CI), %d earlier human release(s) verified immutable and approved, data-pinned legacy '
          'checks replayed unchanged in frozen %s, every other check on the release tree (%.0fs).'
          % (m['targetDataVersion'], len(earlier), anchor[:12], time.monotonic() - started))


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
