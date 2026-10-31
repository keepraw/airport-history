"""Retry missing evidence as new versions; split slow official checklist lookups."""
import concurrent.futures
from copy import deepcopy
import datetime as dt
import json
import sys
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from runtime import PRIVATE, load, write, require, sha
from evidence import LOCK, Store, fetch_one, save_version, old


def recover(path):
    packet = deepcopy(load(path))
    store = Store()
    sources = {s['sourceId']: s for s in load(LOCK)['sources']}
    for entry in packet['sources']:
        sid = entry['sourceId']
        if entry['kind'] != 'unavailable':
            continue
        if not sid.startswith('checklist-'):
            entry.update(fetch_one(sources[sid], store))
            continue
        checklist = next(c for c in load(old.PACKET / 'checklist-reconciliation.json')['checklists'] if c['lookupSourceId'] == sid)
        parts = urlsplit(entry['url'])
        query = parse_qs(parts.query)
        def one(number):
            selected = {k: v[0] for k, v in query.items()}
            selected['sch_notam_no'] = number
            url = urlunsplit(parts._replace(query=urlencode(selected)))
            return fetch_one({**sources[sid], 'sourceId': sid + '/' + number, 'url': url}, store)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            components = list(pool.map(one, checklist['listedNoticeNumbers']))
        entry.update(kind='derived-official-notam-set', components=components,
                     observedAt=dt.datetime.now(dt.timezone.utc).isoformat(),
                     derivation='Union of individually acquired official NOTAM queries; no assembled bytes are an original.')
        entry.pop('errorType', None)
        entry.pop('reason', None)
    packet['parentEvidenceVersionSha256'] = sha(load(path))
    key, version_path = save_version(packet)
    print(json.dumps({'versionSha256': key, 'privateManifest': str(version_path)}))


if __name__ == '__main__':
    recover(sys.argv[1])
