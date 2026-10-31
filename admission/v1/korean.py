"""Korean bounded-code v2 bridge. Identity rules never supply code validity."""
import datetime as dt
import json
from copy import deepcopy
import io
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from runtime import ROOT, authorize, checked_bindings, load, policy, require, sha
from evidence import LOCK, Store, WINDOW, old, replay, revalidate_source

_REPLAY_CACHE = {}
_METADATA_CACHE = {}


def locked_metadata():
    """Replay the old predicates in their real frozen tree, including package semantics.

    New data/package versions may not rewrite the PR24/25 research fingerprint.
    This subprocess provides facts only; none of its grants or identity approval
    state can authorize v2 admission.
    """
    commit = policy('kr-code')['requirements']['frozenLegacyCommit']
    require(re.fullmatch('[0-9a-f]{40}', commit), 'Exact frozen legacy commit required')
    if commit in _METADATA_CACHE:
        return deepcopy(_METADATA_CACHE[commit])
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='legacy-kr-metadata-', dir=ROOT / 'work') as tmp:
        root = Path(tmp)
        archive = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter='data')
        program = "import sys,json;sys.path.insert(0,'scripts/admission');import kr_adapter as a;import kr_evidence as e;print(json.dumps(e.evaluate(a.policy())))"
        result = json.loads(subprocess.check_output(['python3', '-I', '-c', program], cwd=root, text=True))
    require(result['originalBytesReadHere'] is False, 'Frozen metadata must not claim current original replay')
    _METADATA_CACHE[commit] = deepcopy(result)
    return result


def evaluate(evidence, store):
    # All PR25 finite-window predicates remain in use, without modifying or
    # inheriting its authorization. v2 independently replays current originals.
    raw = replay(evidence, store)
    # Re-read/hash EVERY original on EVERY call. Reusing a deterministic graph
    # result for the exact same checked bytes cannot hide changed CAS content.
    key = sha(evidence)
    if key in _REPLAY_CACHE:
        return deepcopy(_REPLAY_CACHE[key])
    result = locked_metadata()
    assessments = [revalidate_source(entry, raw[entry['sourceId']]) for entry in evidence['sources']]
    fresh = {}
    notice_count = 0
    for code in ('RKSI', 'RKSS'):
        sid = 'notam-all-' + code.lower()
        obj = json.loads(raw[sid])
        require(obj['Total'] == len(obj['DATA']), 'Truncated airport archive')
        require(all(r['LOCATION'] == code for r in obj['DATA']), 'Wrong airport filter')
        fresh[code] = [old.research.metadata(item, sid, i) for i, item in enumerate(obj['DATA'])]
        notice_count += len(obj['DATA'])
        rows = fresh[code]
        relevant = [r for r in rows if old.research.lifecycle(r, rows)['disposition'] in ('overlap', 'unknown_lifecycle')]
        closure = list(relevant)
        while True:
            numbers = {r['seriesBaseNo'] for r in closure}
            targets = {r['replacesOrCancels'] for r in closure}
            added = [r for r in rows if r not in closure and
                     (r['seriesBaseNo'] in targets or r['replacesOrCancels'] in numbers)]
            if not added:
                break
            closure.extend(added)
        old.notice_checks(closure, old.research.START, old.research.END)
        for row in relevant:
            status = old.research.lifecycle(row, rows)
            require(status['disposition'] != 'unknown_lifecycle' and not status['missingPredecessor'] and
                    not row['identityChangeSignal'] and row['qcode'] != 'QFALC', 'New or conflicting historical airport exception')
    fir = load(old.PACKET / 'fir-screening.json')
    all_fir = []
    for segment in fir['segments']:
        sid = segment['sourceId']
        obj = json.loads(raw[sid])
        require(obj['Total'] == len(obj['DATA']), 'Truncated FIR segment')
        rows = [old.research.metadata(item, sid, i) for i, item in enumerate(obj['DATA'])]
        all_fir.extend(rows)
        notice_count += len(rows)
    relevant_fir = [r for r in all_fir if old.research.lifecycle(r, all_fir)['disposition'] in ('overlap', 'unknown_lifecycle')]
    old.duplicate_bytes(relevant_fir)
    for row in relevant_fir:
        status = old.research.lifecycle(row, all_fir)
        require(status['disposition'] != 'unknown_lifecycle' and not status['missingPredecessor'] and
                not row['identityChangeSignal'] and row['qcode'] != 'QFALC', 'Unresolved original FIR exception')
    for checklist in load(old.PACKET / 'checklist-reconciliation.json')['checklists']:
        row = checklist['checklist']
        found = [r for r in all_fir if r['notamNo'] == row['notamNo']]
        require(found and all(r['fullTextSha256'] == row['fullTextSha256'] for r in found), 'Changed/missing official historical checklist')
        snapshot = dt.datetime.fromisoformat(checklist['snapshot']['utc'])
        expected = set()
        for rows in fresh.values():
            for item in rows:
                if item['notamNo'][0] != row['notamNo'][0] or item['noticeType'] == 'C':
                    continue
                issued = old.research.instant(item['issued']['raw'])
                end = old.research.lifecycle(item, rows)['effectiveEndUtc']
                if issued and issued <= snapshot and (end is None or dt.datetime.fromisoformat(end) > snapshot):
                    expected.add(item['notamNo'])
        listed = set(checklist['listedNoticeNumbers'])
        require(expected <= listed and expected == {r['notamNo'] for r in checklist['airportOutstandingNotices']},
                'Fresh airport graph disagrees with historical outstanding set')
    sources = {s['sourceId']: s for s in load(LOCK)['sources']}
    statements = {s['observedCode']: s for s in load(ROOT / 'research/admission/rule-v1/candidate-catalog.json')['candidates']}
    from evidence import extract
    for candidate in result['candidates']:
        for sid in candidate['sourceIds']:
            text = ' '.join(extract(raw[sid]).split())
            require(candidate['code'] in text and candidate['arpDms'] in text and statements[candidate['code']]['aipName'] in text,
                    'Fresh AIP code/name/ARP does not establish the scoped window')
    for supplement in load(old.PACKET / 'publication-crosscheck.json')['supplementOriginals']:
        text = ' '.join(extract(raw[supplement['sourceId']]).split())
        require(all(s in text for s in supplement['explicitSupersessionStatements']), 'SUP original supersession conflict')
    outcome = {**result, 'mode': 'versioned-original-fact-replay', 'originalBytesReadHere': True,
            'evidenceVersionSha256': sha(evidence), 'rawNoticesParsed': notice_count,
            'sourcesRevalidated': len(assessments), 'legacyAuthorizationInherited': False}
    _REPLAY_CACHE[key] = deepcopy(outcome)
    return outcome


def assignments(p, grants, approved, evidence, store, base, day):
    authorize(p, grants)
    checked_bindings(p)
    result = evaluate(evidence, store)
    require(p['scope']['namespace'] == 'ICAO' and p['scope']['country'] == 'KR' and
            p['scope']['window'] == WINDOW and
            set(p['scope']['codes']) == {c['code'] for c in result['candidates']} and
            not p['scope']['newPhysicalIdentities'] and not p['scope']['newIataAssignments'] and
            not p['scope']['publishedCorrections'], 'Unsupported code scope')
    entries = []
    for record in result['candidates']:
        matched = [a for a in approved if a['candidate']['observedCode'] == record['code']]
        if not matched:
            continue
        require(len(matched) == 1, 'Ambiguous approved physical site for code')
        accepted = matched[0]
        require(accepted['candidate']['observations'][0]['arpDms'] == record['arpDms'] and
                accepted['decision']['classification'] == 'AUTO_ELIGIBLE', 'Unadmitted/wrong physical identity')
        require(not any(a['scheme'] == 'ICAO' and a['code'] == record['code'] for a in base['assignments']), 'Existing code requires manual correction policy')
        entries.append({'assignmentId': 'rule-kr-' + sha([p['policyKey'], accepted['identity']['siteKey'], record])[:24],
            'airportId': accepted['identity']['airportId'], 'scheme': 'ICAO', 'code': record['code'],
            'verificationStatus': 'verified', 'verifiedOn': day,
            'validFrom': {'earliest': None, 'latest': record['window']['from'], 'precision': 'unknown'},
            'validTo': {'earliest': record['window']['toExclusive'], 'latest': None, 'precision': 'unknown'},
            'evidenceType': 'continuity_inference', 'sourceIds': record['sourceIds'],
            'note': 'Independent identity admission plus bounded AIP/NOTAM/SUP code review; outer historical bounds unknown.'})
    return entries, result


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Read-only full versioned Korean original/fact replay; no authority or UUID creation.')
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(load(args.manifest), Store())
    print(json.dumps({k: v for k, v in result.items() if k != 'candidates'}))
