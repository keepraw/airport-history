"""Materialize ALL pinned airport code/site observations into one indexed SQLite DB.

This is a bulk observation index, not an automatic promotion of directory edits to
verified historical code assignments. Curated assignments keep their exact
uncertainty bounds; reference revisions retain their *observation* timestamps.
No airport-specific allowlist, artificial batch cap, network request or grant.
"""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/reference'))
from common import ROOT, OUTPUT, DISCOVERY, canonical, checked, digest, read_jsonl, stable_id

TRIAGE = ROOT / 'reference/triage'
SCHEMES = {'IATA': re.compile(r'[A-Z]{3}'), 'ICAO': re.compile(r'[A-Z]{4}'),
           'GPS': re.compile(r'[^\s]+'), 'LOCAL': re.compile(r'[^\s]+'),
           'IDENT': re.compile(r'[^\s]+')}

SCHEMA = '''
CREATE TABLE sites (
  site_id TEXT PRIMARY KEY, airport_id TEXT, reference_id TEXT,
  name TEXT, country TEXT, latitude REAL, longitude REAL,
  identity_status TEXT NOT NULL
);
CREATE TABLE source_sites (
  reference_id TEXT NOT NULL, location_id TEXT NOT NULL, site_id TEXT NOT NULL,
  PRIMARY KEY(reference_id,location_id,site_id),
  FOREIGN KEY(site_id) REFERENCES sites(site_id)
);
CREATE TABLE reference_observations (
  observation_id TEXT PRIMARY KEY, scheme TEXT NOT NULL, code TEXT NOT NULL,
  site_id TEXT NOT NULL, reference_id TEXT NOT NULL, source_id TEXT NOT NULL,
  kind TEXT NOT NULL, side TEXT, revision_observed_at TEXT, candidate_id TEXT,
  source_commit TEXT, source_blob TEXT, ambiguous_location INTEGER NOT NULL,
  FOREIGN KEY(site_id) REFERENCES sites(site_id)
);
CREATE INDEX ref_code ON reference_observations(scheme,code,site_id);
CREATE TABLE formal_assignments (
  assignment_id TEXT PRIMARY KEY, scheme TEXT NOT NULL, code TEXT NOT NULL,
  airport_id TEXT NOT NULL, verified_on TEXT, evidence_type TEXT NOT NULL,
  start_earliest TEXT, start_latest TEXT, end_earliest TEXT, end_latest TEXT,
  source_ids TEXT NOT NULL
);
CREATE INDEX formal_code ON formal_assignments(scheme,code);
CREATE TABLE lead_groups (
  group_id TEXT PRIMARY KEY, reference_id TEXT, country TEXT, name TEXT,
  status TEXT NOT NULL, classifications TEXT NOT NULL, candidate_count INTEGER NOT NULL
);
CREATE TABLE lead_members (
  candidate_id TEXT PRIMARY KEY, group_id TEXT NOT NULL, source_id TEXT,
  source_entity_id TEXT, revision_observed_at TEXT,
  FOREIGN KEY(group_id) REFERENCES lead_groups(group_id)
);
CREATE TABLE lead_code_observations (
  candidate_id TEXT NOT NULL, scheme TEXT NOT NULL, code TEXT NOT NULL,
  side TEXT NOT NULL, group_id TEXT NOT NULL,
  PRIMARY KEY(candidate_id,scheme,code,side),
  FOREIGN KEY(candidate_id) REFERENCES lead_members(candidate_id)
);
CREATE INDEX lead_code ON lead_code_observations(scheme,code,group_id);
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


def _load_manifest(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _iter_inputs(reference_dir, triage_dir, discovery_dir, strict):
    reference_dir, triage_dir, discovery_dir = map(Path, (reference_dir,triage_dir,discovery_dir))
    r = _load_manifest(reference_dir / 'manifest.json')
    t = _load_manifest(triage_dir / 'manifest.json')
    d = _load_manifest(discovery_dir / 'manifest.json')
    shards = [f'records.{x}.jsonl.gz' for x in '0123456789abcdef']
    if strict and any(n not in r['files'] for n in shards):
        raise ValueError('Incomplete 16-shard reference population')
    shards = [n for n in shards if n in r['files']]
    candidate_files = sorted(n for n in d['files'] if '.candidates.' in n and n != 'code-links.candidates.jsonl.gz')
    if not shards or not candidate_files:
        raise ValueError('Incomplete historical input population')
    required = [(reference_dir,n,r['files'][n]['sha256']) for n in shards]
    required += [(triage_dir,n,t['files'][n]['sha256']) for n in ('groups.jsonl.gz',)]
    required += [(discovery_dir,n,d['files'][n]['sha256']) for n in candidate_files]
    for folder,name,sha in required:
        if strict:
            checked(folder / name,sha)
        elif not (folder / name).is_file():
            raise FileNotFoundError(folder / name)
    return shards, candidate_files, required


def _code(scheme, value):
    if not isinstance(value,str):
        return None
    if scheme in ('IATA','ICAO'):
        value = value.strip().upper()
    return value if SCHEMES[scheme].fullmatch(value) else None


def _site(cursor, site_id, airport_id, reference_id, name, country, coordinates, status):
    cursor.execute('INSERT OR IGNORE INTO sites VALUES (?,?,?,?,?,?,?,?)',
                   (site_id,airport_id,reference_id,name,country,
                    coordinates.get('latitude') if coordinates else None,
                    coordinates.get('longitude') if coordinates else None,status))


def _reference_record(db, record, stats):
    ref = record['referenceId']
    locations = record['locations']
    if not locations:
        raise ValueError('Reference record has no location hypotheses')
    candidates = []
    for loc in locations:
        linked = loc.get('curatedAirportIds', [])
        site_ids = linked if linked else [loc['locationId']]
        for site_id in site_ids:
            _site(db,site_id,site_id if linked else None,ref if not linked else None,
                  record['name'],record['country'],loc.get('coordinates'),
                  'curated_physical_site' if linked else 'reference_location_hypothesis')
            db.execute('INSERT OR IGNORE INTO source_sites VALUES(?,?,?)',
                       (ref,loc['locationId'],site_id))
            candidates.append((site_id, loc))
    stats['referenceRecords'] += 1

    def record_code(scheme, raw, kind, side=None, item=None):
        code = _code(scheme,raw)
        if code is None:
            return
        # Only a matching changed-location candidate may localize an old code.
        # If the association remains ambiguous, expose *every* possibility.
        matching = [pair for pair in candidates if item and item.get('candidateId') in pair[1].get('candidateIds',[])]
        possibilities = matching if matching else candidates
        ambiguous = len({site for site,_ in possibilities}) != 1 or (item is not None and not matching and len(candidates)>1)
        for site_id, loc in possibilities:
            identifying = [ref, loc['locationId'],site_id,scheme,code,kind,side,
                           item['candidateId'] if item else None,item['blob'] if item else None]
            obs_id = stable_id('obs_',identifying)
            db.execute('INSERT OR IGNORE INTO reference_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (obs_id,scheme,code,site_id,ref,item['sourceId'] if item else record['sourceId'],
                        kind,side,item['revisionObservedAt'] if item else record['observedAt'],
                        item['candidateId'] if item else None,item['commit'] if item else
                        (record.get('observation') or {}).get('revision'),
                        item['blob'] if item else (record.get('observation') or {}).get('blob'),int(ambiguous)))
            stats['referenceCodeObservations'] += db.execute('SELECT changes()').fetchone()[0]

    for scheme,value in record['identifiers'].items():
        record_code(scheme,value,'pinned_snapshot' if record['presentAtSnapshot'] else 'retained_source_row')
    for item in record['historicalIdentifiers']:
        if item['scheme'] in ('IATA','ICAO'):
            record_code(item['scheme'],item['code'],'source_transition',item['side'],item)


def _formal(db, curated, stats):
    for airport in curated['airports']:
        _site(db, airport['airportId'],airport['airportId'],None,
              airport['name']['value'],None,airport['coordinates']['value'],'curated_physical_site')
    stats['formalAirports'] = len(curated['airports'])
    for row in curated['assignments']:
        if row['scheme'] not in SCHEMES or _code(row['scheme'],row['code']) is None:
            continue
        db.execute('INSERT INTO formal_assignments VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (row['assignmentId'],row['scheme'],row['code'],row['airportId'],
                    row.get('verifiedOn'),row['evidenceType'],row['validFrom']['earliest'],
                    row['validFrom']['latest'],row['validTo']['earliest'],row['validTo']['latest'],
                    canonical(row['sourceIds'])))
        stats['formalCodeAssignments'] += 1


def _leads(db, triage_dir, discovery_dir, candidate_files, stats):
    for group in read_jsonl(triage_dir / 'groups.jsonl.gz'):
        match = group.get('physicalMatch') or {}
        db.execute('INSERT INTO lead_groups VALUES (?,?,?,?,?,?,?)',
                   (group['eventGroupId'],match.get('referenceId'),group.get('country'),group.get('name'),
                    group['status'],canonical(group['classifications']),len(group['members'])))
        for member in group['members']:
            db.execute('INSERT INTO lead_members VALUES (?,?,?,?,?)',
                       (member['candidateId'],group['eventGroupId'],member['sourceId'],
                        member['sourceEntityId'],member['firstRevisionObservedAt']))
            stats['indexedLeadMembers'] += 1
        stats['indexedEventGroups'] += 1
    db.commit()
    # Only selected candidates enter the code index. The source scanner remains
    # full-corpus and is not reduced to a handpicked airport list.
    query = db.execute
    for filename in candidate_files:
        for item in read_jsonl(discovery_dir / filename):
            row = query('SELECT group_id FROM lead_members WHERE candidate_id=?',
                        (item['candidateId'],)).fetchone()
            if row is None:
                continue
            changes = item.get('changes',{})
            for scheme, key in (('IATA','iata'),('ICAO','icao')):
                values = changes.get(key)
                if not isinstance(values,list):
                    continue
                for side,value in zip(('before','after'),values):
                    code = _code(scheme,value)
                    if code is None:
                        continue
                    db.execute('INSERT OR IGNORE INTO lead_code_observations VALUES (?,?,?,?,?)',
                               (item['candidateId'],scheme,code,side,row[0]))
                    stats['indexedTransitionCodeObservations'] += query('SELECT changes()').fetchone()[0]
        db.commit()


def build(output, reference_dir=OUTPUT, triage_dir=TRIAGE, discovery_dir=DISCOVERY,
          curated_path=ROOT/'data/airports.json', *, strict=True):
    """Atomic full-corpus SQLite rebuild. All source files are consumed, not sampled."""
    output = Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    shards,candidate_files,inputs = _iter_inputs(reference_dir,triage_dir,discovery_dir,strict)
    curated = _load_manifest(curated_path)
    fd, temp_name = tempfile.mkstemp(prefix='bulk-history-', suffix='.sqlite',dir=output.parent)
    os.close(fd)
    stats = {k:0 for k in ('referenceRecords','referenceCodeObservations','formalAirports',
                         'formalCodeAssignments','indexedLeadMembers','indexedEventGroups',
                         'indexedTransitionCodeObservations')}
    try:
        with sqlite3.connect(temp_name) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript(SCHEMA)
            _formal(db,curated,stats)
            for name in shards:
                for record in read_jsonl(Path(reference_dir)/name):
                    _reference_record(db,record,stats)
                db.commit()
            _leads(db,Path(triage_dir),Path(discovery_dir),candidate_files,stats)
            db.execute('INSERT INTO metadata VALUES (?,?)',('formatVersion','1.0.0'))
            db.execute('INSERT INTO metadata VALUES (?,?)',('curatedDataVersion',curated['dataVersion']))
            db.execute('INSERT INTO metadata VALUES (?,?)',('inputs',canonical({
                str(folder / name): sha for folder,name,sha in inputs})))
            db.execute('INSERT INTO metadata VALUES (?,?)',('curatedSha256',digest(curated_path)))
            db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Bulk SQLite integrity failure')
            if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise ValueError('Unlinked bulk history site/group')
            stats['materializedSites'] = db.execute('SELECT COUNT(*) FROM sites').fetchone()[0]
            db.execute('VACUUM')
        os.replace(temp_name,output)
        return {'schemaVersion':'1.0.0','database':str(output),'dataVersion':curated['dataVersion'],
                'historicallyVerifiedReferenceClaims':0,'metrics':stats,'databaseSha256':digest(output),
                'meaning':'Curated assignments retain reviewed dates; worldwide directory changes are bulk-indexed as observations, NOT official effective dates.'}
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _relation(day, row):
    # Conservatively reproduce the repository's possible/certain interval bounds.
    if day is None:
        return 'not_date_filtered'
    if ((row['start_earliest'] is None or day >= row['start_earliest']) and
        (row['end_latest'] is None or day < row['end_latest'])):
        if ((row['start_latest'] is not None and day >= row['start_latest']) and
            (row['end_earliest'] is not None and day < row['end_earliest'])):
            return 'certain'
        return 'possible'
    return 'excluded'


def lookup(database,code,scheme='IATA',at=None,limit=50,offset=0):
    if scheme not in SCHEMES or not _code(scheme,code):
        raise ValueError('Invalid scheme/code')
    if limit < 1 or limit > 1000 or offset < 0:
        raise ValueError('limit must be 1..1000; offset must be nonnegative')
    code = _code(scheme,code)
    if at is not None:
        try:
            if date.fromisoformat(at).isoformat() != at:
                raise ValueError()
        except ValueError:
            raise ValueError('Date must be YYYY-MM-DD') from None
    conn = sqlite3.connect(f'file:{Path(database).resolve()}?mode=ro',uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if conn.execute('SELECT value FROM metadata WHERE key=?',('formatVersion',)).fetchone()[0] != '1.0.0':
            raise ValueError('Unknown bulk-history database')
        formal = []
        for r in conn.execute('''SELECT f.*, s.name, s.latitude, s.longitude FROM formal_assignments f
                                 JOIN sites s ON s.site_id=f.airport_id
                                 WHERE f.scheme=? AND f.code=? ORDER BY f.airport_id,f.assignment_id''',(scheme,code)):
            item = dict(r)
            item['dateRelation'] = _relation(at,item)
            item['source_ids'] = json.loads(item['source_ids'])
            if item['dateRelation'] != 'excluded':
                formal.append(item)
        count = conn.execute('''SELECT COUNT(*) FROM reference_observations
                                WHERE scheme=? AND code=?''',(scheme,code)).fetchone()[0]
        refs = [dict(r) for r in conn.execute('''
             SELECT o.*, s.name, s.country, s.latitude, s.longitude, s.identity_status
             FROM reference_observations o JOIN sites s ON s.site_id=o.site_id
             WHERE o.scheme=? AND o.code=? ORDER BY o.site_id,o.kind,o.reference_id,o.observation_id
             LIMIT ? OFFSET ?''',(scheme,code,limit,offset))]
        lead_count = conn.execute('''SELECT COUNT(DISTINCT group_id) FROM lead_code_observations
                                     WHERE scheme=? AND code=?''',(scheme,code)).fetchone()[0]
        leads = [dict(r) for r in conn.execute('''
             SELECT DISTINCT g.group_id,g.reference_id,g.country,g.name,g.status,g.classifications
             FROM lead_code_observations c JOIN lead_groups g ON g.group_id=c.group_id
             WHERE c.scheme=? AND c.code=? ORDER BY g.group_id LIMIT ? OFFSET ?''',
             (scheme,code,limit,offset))]
        for row in leads:
            row['classifications'] = json.loads(row['classifications'])
        certain = {v['airport_id'] for v in formal if v['dateRelation']=='certain'}
        possible = {v['airport_id'] for v in formal if v['dateRelation']=='possible'}
        if at is not None and len(certain)==1 and not (possible - certain):
            status = 'resolved'
        elif at is not None and (certain or possible):
            status = 'uncertain'
        elif formal or count or lead_count:
            status = 'historical_observations_only' if at is not None else 'indexed'
        else:
            status = 'not_found'
        return {'query':{'scheme':scheme,'code':code,'date':at,'limit':limit,'offset':offset},
                'status':status,'resolvedAirportId':next(iter(certain)) if status=='resolved' else None,
                'formalAssignments':formal,'referenceObservationCount':count,
                'referenceObservations':refs,'transitionLeadGroupCount':lead_count,
                'transitionLeadGroups':leads,
                'timestampMeaning':'Directory revision timestamps are observations, never official code effective dates.',
                'identityMeaning':'A loc_ ID is a location hypothesis, not an approved physical airport. Only formal apt_ assignments can resolve a date.'}
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest='command',required=True)
    b = sp.add_parser('build',help='Atomically index every pinned worldwide record and selected source transition')
    b.add_argument('--output',type=Path,default=ROOT/'work/history-index.sqlite')
    q = sp.add_parser('lookup',help='Query the complete bulk index by code and optional local date')
    q.add_argument('--database',type=Path,default=ROOT/'work/history-index.sqlite')
    q.add_argument('--code',required=True)
    q.add_argument('--scheme',choices=tuple(SCHEMES),default='IATA')
    q.add_argument('--date',dest='at')
    q.add_argument('--limit',type=int,default=50)
    q.add_argument('--offset',type=int,default=0)
    args = p.parse_args()
    if args.command == 'build':
        print(canonical(build(args.output)))
    else:
        print(canonical(lookup(args.database,args.code,args.scheme,args.at,args.limit,args.offset)))


if __name__=='__main__':
    main()
