"""Explicit, resumable offline research scan. Uses only local Git objects."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
from collections import Counter
from pathlib import Path

from core import (ZERO, canonical, describe, git, history, normalized, patch_rows,
                  rows_from_text, source_text, stable_id, write_candidates, write_json, write_jsonl)

ROOT = Path(__file__).resolve().parents[2]


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript('''
      CREATE TABLE IF NOT EXISTS edges (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS versions (blob TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS candidates (id TEXT PRIMARY KEY, entity TEXT NOT NULL, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS observations (candidate TEXT, edge TEXT, payload TEXT NOT NULL,
        PRIMARY KEY(candidate, edge));
      CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, firstSeen TEXT, lastSeen TEXT,
        codes TEXT, payload TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS observations_candidate ON observations(candidate);
      CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS gaps (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
    ''')
    return db


def baseline_stats(rows, source):
    data = [normalized(r) for r in rows.values()]
    # airportsdata/mwgg "icao" also contains pseudo identifiers. Count separately.
    return {'records': len(rows),
            'byType': dict(sorted(Counter(r.get('type', 'not_supplied') for r in data).items())),
            'byCountry': dict(sorted(Counter(r.get('country') or 'unknown' for r in data).items())),
            'iataNonempty': sum(bool(r.get('iata')) for r in data),
            'icaoFieldNonempty': sum(bool(r.get('icao')) for r in data),
            'icaoFourLetters': sum(len(r.get('icao', '')) == 4 and r.get('icao', '').isalpha() and r.get('icao', '').isascii() for r in data),
            'gpsCodeNonempty': sum(bool(r.get('gps_code')) for r in data),
            'neitherIataNorExplicitIcao': sum(not r.get('iata') and not r.get('icao') for r in data),
            'noIataIcaoOrGps': sum(not r.get('iata') and not r.get('icao') and not r.get('gps_code') for r in data),
            'closed': sum(r.get('type') == 'closed' for r in data),
            'scheduledService': sum(r.get('scheduled_service') == 'yes' for r in data),
            'columns': sorted(set().union(*(r.keys() for r in rows.values()))) if rows else []}


def observe_entity(db, entity, row, edge):
    info = db.execute('SELECT firstSeen,lastSeen,codes FROM entities WHERE id=?', (entity,)).fetchone()
    date = edge['observedAt']
    r = normalized(row)
    codes = {r.get(k) for k in ('iata', 'icao', 'gps_code', 'ident', 'lid', 'local_code')} - {None, ''}
    if info:
        codes.update(json.loads(info[2]))
    db.execute('INSERT OR REPLACE INTO entities VALUES (?,?,?,?,?)',
               (entity, min(date, info[0]) if info else date, max(date, info[1]) if info else date,
                canonical(sorted(codes)), canonical({'row': row, 'version': edge['commit'],
                                                    'blob': edge['afterBlob']})))


def insert_candidate(db, source, entity, before, after, edge, extra_type=None):
    detail = describe(before, after)
    if extra_type:
        detail['types'] = [extra_type]
    # Same source entity and exact raw field transition is one research lead.
    # Repeated occurrences remain individually recorded, not erased as an event.
    cid = stable_id('cand_', [source['id'], entity, detail['changes'], extra_type])
    db.execute('INSERT OR IGNORE INTO candidates VALUES (?,?,?)',
               (cid, entity, canonical(detail)))
    db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?)',
               (cid, stable_id('edge_', edge), canonical(edge)))


def scan(source, cache):
    repo = ROOT / source['localRepository']
    revision = source['revision']
    if git(repo, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise ValueError('Shallow histories cannot establish full source coverage')
    # Verify the pinned commit before reading any history.
    if git(repo, 'rev-parse', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('Expected a full pinned SHA')
    edges = history(repo, revision, source['path'])
    db = connect(cache / (source['id'] + '.sqlite'))
    signature = canonical({'engineVersion': 1, **{k: v for k, v in source.items() if k != 'revision'}})
    previous = dict(db.execute('SELECT key,value FROM metadata'))
    if previous and previous.get('signature') != signature:
        raise ValueError('Cache configuration changed; use a fresh --cache directory')
    if previous.get('revision'):
        git(repo, 'merge-base', '--is-ancestor', previous['revision'], revision)
    db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('signature', signature))
    db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('revision', revision))
    db.commit()
    current, header, current_blob = {}, [], ZERO
    repairs_by_blob = {}
    bad_blobs = {}
    fresh, fallback = 0, 0

    def load(blob):
        if blob == ZERO:
            return [], {}
        if blob in bad_blobs:
            raise ValueError(bad_blobs[blob])
        text, repairs = source_text(source, git(repo, 'cat-file', 'blob', blob).decode('utf-8-sig'))
        repairs_by_blob[blob] = repairs
        try:
            return rows_from_text(text, source['key'], source.get('format', 'csv'))
        except (ValueError, csv.Error) as error:
            bad_blobs[blob] = str(error)
            raise

    for index, edge in enumerate(edges):
        eid = stable_id('edge_', edge)
        if db.execute('SELECT 1 FROM edges WHERE id=?', (eid,)).fetchone():
            continue
        old, new = edge['beforeBlob'], edge['afterBlob']
        if source.get('allowParseGaps'):
            # Explicitly configured quarantine: inspect both endpoints, retain
            # valid snapshots, and never bridge an unparseable revision as an event.
            states, failures = {}, {}
            for label, blob in [('before', old), ('after', new)]:
                try:
                    states[label] = (header, current) if current_blob == blob else load(blob)
                except (ValueError, csv.Error) as error:
                    failures[label] = {'blob': blob, 'error': str(error)}
                    db.execute('INSERT OR IGNORE INTO versions VALUES (?,?)',
                               (blob, canonical({'records': None, 'columns': [], 'parseError': str(error)})))
            if failures:
                gap = {**edge, 'unparsedEndpoints': failures,
                       'meaning': 'No change inference across this edge; no event date or missing row is invented.'}
                db.execute('INSERT OR REPLACE INTO gaps VALUES (?,?)', (eid, canonical(gap)))
                if 'after' in states:
                    header, current = states['after']
                    current_blob = new
                    for entity, row in current.items():
                        observe_entity(db, entity, row, edge)
                    db.execute('INSERT OR REPLACE INTO versions VALUES (?,?)',
                               (new, canonical({'records': len(current), 'columns': header,
                                                'parseRepairs': repairs_by_blob.get(new, [])})))
                else:
                    current_blob, header, current = ZERO, [], {}
                db.execute('INSERT INTO edges VALUES (?,?)', (eid, canonical(edge)))
                db.commit()
                print(f"{source['id']}: quarantined {edge['commit']} ({', '.join(failures)})", flush=True)
                continue
            header, current = states['before']
            current_blob = old
        if current_blob != old:
            header, current = load(old)
        if old == ZERO or new == ZERO or source.get('format') == 'json' or source.get('csvRepairs'):
            new_header, after_all = states['after'] if source.get('allowParseGaps') else load(new)
            before, after = current, after_all
            full = True
        else:
            patch = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-color',
                        '--no-renames', '--unified=0', old, new).decode('utf-8-sig')
            try:
                before, after = patch_rows(patch, header, source['key'], current)
                new_header, full = header, False
            except (ValueError, csv.Error):
                new_header, after_all = load(new)
                before, after, full = current, after_all, True
                fallback += 1
        changed = sorted(e for e in before.keys() | after.keys() if before.get(e) != after.get(e))
        is_baseline = old == ZERO
        for entity in changed:
            a, b = before.get(entity, {}), after.get(entity, {})
            if not is_baseline:
                insert_candidate(db, source, entity, a, b, edge)
            elif normalized(b).get('type') == 'closed':
                insert_candidate(db, source, entity, {}, b, edge, 'baseline_closed_record')
            observe_entity(db, entity, b or a, edge)
        if full:
            current = after
        else:
            for entity in before:
                current.pop(entity)
            current.update(after)
        current_blob, header = new, new_header
        db.execute('INSERT OR IGNORE INTO versions VALUES (?,?)',
                   (new, canonical({'records': len(current), 'columns': header,
                                    'parseRepairs': repairs_by_blob.get(new, [])})))
        db.execute('INSERT INTO edges VALUES (?,?)', (eid, canonical(edge)))
        db.commit()  # Each completed edge is the resumable transaction boundary.
        fresh += 1
        if index % 100 == 0:
            print(f"{source['id']}: {index+1}/{len(edges)} edges, {len(current)} rows", flush=True)
    # Always check the full target snapshot; do not trust only patch parsing.
    tree = git(repo, 'ls-tree', revision, '--', source['path']).decode().strip()
    target_blob = tree.split()[2] if tree else ZERO
    _, latest = load(target_blob)
    if current_blob == target_blob and current != latest:
        raise ValueError('Incremental patch state differs from full target snapshot')
    gaps = db.execute('SELECT count(*) FROM gaps').fetchone()[0]
    print(f"{source['id']}: enumerated all {len(edges)} edges; {gaps} comparisons blocked; {fresh} new comparisons; {fallback} full-parse fallbacks", flush=True)
    return db, edges, latest


def matches(dataset, source, entity, context):
    exact = [a['airportId'] for a in dataset['airports']
             if source['id'] in ('ourairports', 'airport-codes-raw', 'airport-codes-initial')
             and a['externalIds'].get('ourAirports') == entity]
    code = [a for a in dataset['assignments'] if a['code'] in context['codes']]
    return {'airportIds': exact,
            'assignmentIds': sorted(a['assignmentId'] for a in dataset['assignments'] if a['airportId'] in exact),
            'nameIds': sorted(n['nameId'] for n in dataset['names'] if n['airportId'] in exact),
            'codeOnlyPossibleAirportIds': sorted({a['airportId'] for a in code} - set(exact)),
            'codeOnlyPossibleAssignmentIds': sorted(a['assignmentId'] for a in code)}


def export(source, db, edges, latest, out, dataset, reviews):
    types, countries, continents, years, statuses = (Counter() for _ in range(5))
    year_region = Counter()
    obs_count = 0
    count = 0
    def candidates():
        nonlocal obs_count, count
        for cid, entity, payload in db.execute('SELECT * FROM candidates ORDER BY id'):
            detail = json.loads(payload)
            observations = [json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM observations WHERE candidate=? ORDER BY edge', (cid,))]
            observations.sort(key=lambda r: (r['observedAt'], r['commit'], r['beforeBlob']))
            obs_count += len(observations)
            count += 1
            context = detail['context']
            year = observations[0]['observedAt'][:4]
            review = reviews.get(cid, {})
            status = review.get('status', 'pending_investigation')
            types.update(detail['types'])
            countries[context['country']] += 1
            continents[context['continent']] += 1
            years[year] += 1
            year_region[(year, context['country'])] += 1
            statuses[status] += 1
            yield {'candidateId': cid, 'sourceId': source['id'], 'sourceEntityId': entity,
                   **detail, 'observations': observations,
                   'possibleEvent': 'Unverified source revision; may be correction, label edit, allocation, closure or physical change.',
                   'time': {'eventDate': None, 'eventDatePrecision': 'unknown',
                            'firstObservedRevisionAt': observations[0]['observedAt'],
                            'lastObservedRevisionAt': observations[-1]['observedAt'],
                            'meaning': 'Repository observation times, not event validity bounds; earlier real-world dates remain possible.'},
                   'evidence': {'sourceType': 'secondary', 'evidenceType': 'indirect',
                                'verificationStatus': 'pending', 'sourceUrl': source['url']},
                   'matches': matches(dataset, source, entity, context),
                   'review': {'status': status, 'conflicts': review.get('conflicts', []),
                              'exclusionReason': review.get('exclusionReason'),
                              'evidenceGaps': review.get('evidenceGaps', ['Primary event and code-specific effective boundaries not reviewed.']),
                              'nextAction': review.get('nextAction', 'Review source correction vs real event; obtain dated primary notices independently for identity, codes and official name.'),
                              'eventGroupId': review.get('eventGroupId'),
                              'relatedLegacyIds': review.get('relatedLegacyIds', [])}}
    write_candidates(out, source['id'], candidates())
    # Preserve every historical source identity, including deleted and codeless rows.
    def entities():
        for entity, first, last, codes, payload in db.execute('SELECT * FROM entities ORDER BY id'):
            info = json.loads(payload)
            row = latest.get(entity)
            yield {'sourceId': source['id'], 'sourceEntityId': entity,
                   'identityStatus': 'external_record_only; physical continuity requires review',
                   'firstObservedAt': first, 'lastChangedAt': last,
                   'everObservedCodes': json.loads(codes), 'presentAtTarget': row is not None,
                   'reference': info, 'scope': 'in_scope_if_used_in_flight_record; includes closed, heliport, seaplane and codeless facilities',
                   'matches': matches(dataset, source, entity, {'codes': json.loads(codes)})}
    write_jsonl(out / (source['id'] + '.entities.jsonl.gz'), entities())
    versions = {blob: json.loads(payload) for blob, payload in db.execute('SELECT * FROM versions')}
    version_by_year = Counter(e['observedAt'][:4] for e in edges)
    report = {'sourceId': source['id'], 'revision': source['revision'], 'path': source['path'],
              'target': baseline_stats(latest, source),
              'history': {'fileChangingCommits': len({e['commit'] for e in edges}),
                          'parentDiffs': len(edges), 'uniqueFileVersions': len(versions),
                          'parsedFileVersions': sum(v['records'] is not None for v in versions.values()),
                          'unparsedFileVersions': sum(v['records'] is None for v in versions.values()),
                          'blockedComparisons': db.execute('SELECT count(*) FROM gaps').fetchone()[0],
                          'recordVersionsProcessed': sum(v['records'] or 0 for v in versions.values()),
                          'entitiesEverObserved': db.execute('SELECT count(*) FROM entities').fetchone()[0],
                          'absentAtTarget': db.execute('SELECT count(*) FROM entities').fetchone()[0] - len(latest),
                          'from': min(e['observedAt'] for e in edges), 'through': max(e['observedAt'] for e in edges),
                          'parentDiffsByObservationYear': dict(sorted(version_by_year.items())),
                          'columnsAcrossVersions': sorted(set().union(*(v['columns'] for v in versions.values()))),
                          'sourceFormattingRepairs': {blob: v['parseRepairs'] for blob,v in versions.items() if v.get('parseRepairs')},
                          'mode': 'all reachable main-ancestor file revisions; all merge-parent diffs; no annual sampling'},
              'discovery': {'rawCandidateObservations': obs_count, 'candidates': count,
                            'repeatedObservationsGrouped': obs_count-count,
                            'byType': dict(sorted(types.items())), 'byCountry': dict(sorted(countries.items())),
                            'byContinent': dict(sorted(continents.items())), 'byObservationYear': dict(sorted(years.items())),
                            'byStatus': dict(sorted(statuses.items())),
                            'byObservationYearAndCountry': [{'year': y, 'country': c, 'candidates': n}
                                                           for (y,c), n in sorted(year_region.items())]}}
    write_json(out / (source['id'] + '.coverage.json'), report)
    write_jsonl(out / (source['id'] + '.gaps.jsonl.gz'),
                (json.loads(r[0]) for r in db.execute('SELECT payload FROM gaps ORDER BY id')))
    write_jsonl(out / (source['id'] + '.versions.jsonl.gz'),
                ({**edge, 'afterRecords': versions[edge['afterBlob']]['records']} for edge in edges))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'research/discovery/sources.json')
    parser.add_argument('--cache', type=Path, default=ROOT / 'work/discovery-cache')
    parser.add_argument('--output', type=Path, default=ROOT / 'research/discovery/generated')
    parser.add_argument('--source', action='append')
    args = parser.parse_args()
    config = json.loads(args.manifest.read_text())
    dataset = json.loads((ROOT / 'data/airports.json').read_text())
    reviews = json.loads((ROOT / 'research/discovery/reviews.json').read_text())
    for source in config['sources']:
        if args.source and source['id'] not in args.source:
            continue
        db, edges, latest = scan(source, args.cache)
        export(source, db, edges, latest, args.output, dataset, reviews)
        db.close()


if __name__ == '__main__':
    main()
