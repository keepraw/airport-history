"""Offline discovery primitives. Source edits are observations, never historical facts."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import subprocess
from contextlib import ExitStack
import tempfile
from pathlib import Path

ZERO = '0' * 40
FIELDS = {
    'iata_code': 'iata', 'icao_code': 'icao', 'latitude_deg': 'lat',
    'longitude_deg': 'lon', 'municipality': 'city', 'iso_country': 'country',
    'iso_region': 'region', 'subd': 'region', 'state': 'region', 'elevation_ft': 'elevation',
    'Airport Code': 'iata', 'City Code': 'cityCode', 'Country': 'country', 'City Name': 'city',
}


def entity_key(row, key):
    if key == '@legacy':
        if 'id' in row:
            return row['id']
        return '|'.join(row.get(k, '') for k in ('iata_code', 'iso_country', 'name'))
    if '+' in key:
        return '|'.join(row[k] for k in key.split('+'))
    return row[key]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def stable_id(prefix, value):
    return prefix + hashlib.sha256(canonical(value).encode()).hexdigest()[:24]


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args],
                                   env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})


def source_text(source, text):
    applied = []
    for repair in source.get('csvRepairs', []) + source.get('jsonRepairs', []):
        if repair['from'] in text:
            if text.count(repair['from']) != repair.get('occurrences', 1):
                raise ValueError('Ambiguous source formatting repair')
            text = text.replace(repair['from'], repair['to'])
            applied.append(repair['id'])
    return text, applied


def rows_from_text(text, key, fmt='csv'):
    if not text:
        return [], {}
    if fmt == 'json':
        def unique(pairs):
            result = {}
            for k, v in pairs:
                if k in result:
                    raise ValueError('Duplicate JSON key ' + k)
                result[k] = v
            return result
        data = json.loads(text, object_pairs_hook=unique)
        # Dictionary keys are source IDs. Never overwrite a conflicting row code.
        result = {str(entity): {k: '' if v is None else str(v) for k, v in row.items()}
                  for entity, row in data.items()}
        header = sorted(set().union(*(r.keys() for r in result.values())))
        return header, result
    else:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader)
        if len(header) != len(set(header)) or (key != '@legacy' and not all(k in header for k in key.split('+'))):
            raise ValueError(f'Invalid header: {header}')
        rows = []
        for values in reader:
            if not values:
                continue
            if len(values) != len(header):
                raise ValueError(f'Wrong column count: {values[:2]}')
            rows.append(dict(zip(header, values)))
    result = {}
    for row in rows:
        entity = entity_key(row, key)
        if not entity or entity in result:
            raise ValueError(f'Duplicate/empty source key: {entity}')
        result[entity] = row
    return header, result


def patch_rows(patch, header, key, current):
    """Fast path for CSV diffs; fail closed to full parsing on schema/multiline edits.

    Every removed row must equal the complete existing row. A partial multiline
    fragment cannot silently replace an entity. Reordering produces no changes.
    """
    removed, added = [], []
    for line in patch.splitlines(keepends=True):
        if line.startswith(('---', '+++')):
            continue
        if line.startswith('-'):
            removed.append(line[1:])
        elif line.startswith('+'):
            added.append(line[1:])

    def parse(lines):
        out = {}
        for values in csv.reader(io.StringIO(''.join(lines), newline=''), strict=True):
            if len(values) != len(header):
                raise ValueError('Partial CSV row or schema change')
            row = dict(zip(header, values))
            entity = entity_key(row, key)
            if not entity or entity in out:
                raise ValueError('Duplicate key in patch')
            out[entity] = row
        return out

    before, after = parse(removed), parse(added)
    for entity, row in before.items():
        if current.get(entity) != row:
            raise ValueError('Patch does not contain a complete existing row')
    for entity in after:
        if entity in current and entity not in before:
            raise ValueError('Patch would duplicate an entity')
    return before, after


def normalized(row):
    return {FIELDS.get(k, k): v for k, v in row.items()}


def distance(a, b):
    try:
        lat1, lon1, lat2, lon2 = [float(v) for v in (a['lat'], a['lon'], b['lat'], b['lon'])]
        if not all(math.isfinite(v) for v in (lat1, lon1, lat2, lon2)):
            return None
        x, y = math.radians(lat2-lat1), math.radians(lon2-lon1)
        q = math.sin(x/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(y/2)**2
        return round(6371 * 2 * math.asin(min(1, math.sqrt(max(0, q)))), 3)
    except (KeyError, ValueError):
        return None


def describe(before, after):
    a, b = normalized(before), normalized(after)
    changes = {k: [a.get(k), b.get(k)] for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)}
    types = []
    if not before:
        types.append('record_added')
    elif not after:
        types.append('record_removed')
    else:
        for field, kind in [('iata', 'iata_change'), ('icao', 'icao_change'),
                            ('gps_code', 'gps_code_change'), ('ident', 'identifier_change'),
                            ('name', 'possible_rename'), ('city', 'city_label_change')]:
            if field in changes:
                types.append(kind)
        if 'lat' in changes or 'lon' in changes or 'coordinates' in changes:
            types.append('coordinate_revision')
            if (distance(a, b) or 0) >= 5:
                types.append('possible_relocation')
        if a.get('type') != 'closed' and b.get('type') == 'closed':
            types.append('possible_closure')
        elif a.get('type') == 'closed' and b.get('type') != 'closed':
            types.append('possible_reopening')
        elif 'type' in changes:
            types.append('facility_type_change')
    if not types:
        types.append('record_revision')
    if 'cityCode' in a or 'cityCode' in b:
        types = ['city_code_membership_change']
    codes = sorted({r.get(k, '') for r in (a, b) for k in ('iata', 'icao', 'gps_code', 'ident', 'lid', 'local_code')} - {''})
    return {
        'types': sorted(types), 'changes': changes,
        'context': {'country': b.get('country') or a.get('country') or 'unknown',
                    'region': b.get('region') or a.get('region') or 'unknown',
                    'continent': b.get('continent') or a.get('continent') or 'unknown',
                    'city': b.get('city') or a.get('city') or None,
                    'airport': b.get('name') or a.get('name') or None, 'codes': codes},
        'distanceKm': distance(a, b),
    }


def history(repo, revision, path):
    """Every reachable file-changing commit, including each merge-parent diff."""
    raw = git(repo, 'log', '--reverse', '--topo-order', '--full-history', '-m',
              '--root', '--no-renames', '--no-abbrev', '--raw',
              '--format=@%H|%P|%cI', revision, '--', path).decode()
    edges = []
    for line in raw.splitlines():
        if line.startswith('@'):
            commit, parents, date = line[1:].split('|')
        elif line.startswith(':'):
            meta, name = line.split('\t', 1)
            _, _, old, new, action = meta.split()
            if name != path:
                raise ValueError('Unexpected path')
            edges.append({'commit': commit, 'parents': parents.split(), 'observedAt': date,
                          'beforeBlob': old, 'afterBlob': new, 'action': action})
    return edges


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    # No source filename or wall clock in gzip headers.
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            for row in rows:
                compressed.write((canonical(row) + '\n').encode())


def read_jsonl(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def apply_review(row, reviews):
    """Overlay authoritative curation without changing a pinned source observation."""
    override = reviews.get(row['candidateId'])
    if override is None:
        return row
    result = dict(row)
    result['review'] = {**row.get('review', {'status': row.get('status')}), **override}
    if 'status' in row:  # Compact priority queue rows use a top-level status.
        result['status'] = result['review']['status']
    return result


def read_candidates(out, source_id, reviews=None):
    for path in sorted(out.glob(source_id + '.candidates.*.jsonl.gz')):
        for row in read_jsonl(path):
            yield apply_review(row, reviews or {})


def write_candidates(out, source_id, rows):
    """Stable hash-prefix shards keep individual Git artifacts bounded."""
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        stage = Path(tmp)
        streams = {}
        with ExitStack() as stack:
            for row in rows:
                bucket = row['candidateId'][5]
                if bucket not in streams:
                    raw = stack.enter_context((stage / f'{source_id}.candidates.{bucket}.jsonl.gz').open('wb'))
                    streams[bucket] = stack.enter_context(gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0))
                streams[bucket].write((canonical(row) + '\n').encode())
        names = {p.name for p in stage.iterdir()}
        for path in stage.iterdir():
            path.replace(out / path.name)
        for path in out.glob(source_id + '.candidates*.jsonl.gz'):
            if path.name not in names:
                path.unlink()
