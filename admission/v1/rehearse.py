"""Disposable end-to-end exercise; no production flag accepts test authority."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from runtime import ROOT, PUBLIC, PRIVATE, digest, load, require, write
from evidence import Store


def fixture(root):
    """Synthetic bytes only for public/offline CI, never original recovery."""
    packet = load(ROOT / 'research/evidence/code-dates/korea-readiness/source-lock.json')
    raw_by_id = {}
    catalog = load(PUBLIC / 'candidate-catalog.json')
    for row in catalog['candidates']:
        support = row['independent']
        text = ('SYNTHETIC TEST FIXTURE ' + row['observedCode'] + ' ' + row['aipName'] + ' ' + row['arpDms'] + ' ' + row['name'] + ' ' +
                ' '.join(support['addressTokens'] + support['aipAddressTokens']) + ' ' + support['siteNameToken'])
        for sid in [*row['editionSources'].values(), support['sourceId']]:
            raw_by_id[sid] = text.encode()
    raw_by_id['kr-history'] = b'SYNTHETIC 16 APR 202506 MAR 2025AIRAC AIP AMDT 3/25 (WEF 1600 UTC 16 APR 2025) 01 MAY 202501 MAY 2025AIP AMDT 5/25 14 MAY 202503 APR 2025AIRAC AIP AMDT 4/25 (WEF 1600 UTC 14 MAY 2025)'
    raw_by_id['kr-20250501-amdt-full'] = b'SYNTHETIC TEST FIXTURE AIP AMDT 5/25 1 MAY 2025'
    store = Store(root / 'work/rule-admission/cas')
    entries = []
    for source in packet['sources']:
        raw = raw_by_id.get(source['sourceId'], b'SYNTHETIC TEST FIXTURE: no original aviation claim')
        entries.append({'sourceId': source['sourceId'], 'url': source['url'], 'finalUrl': source['url'],
            'observedAt': '2026-10-30T00:00:00+00:00', 'originalSha256': store.put(raw), 'originalBytes': len(raw),
            'previousOriginalSha256': source['originalSha256'], 'kind': 'isolated-synthetic-fixture'})
    from evidence import LOCK, WINDOW
    return {'formatVersion': 2, 'sourceLockSha256': digest(LOCK.read_bytes()), 'windowToReevaluate': WINDOW,
            'sources': entries, 'simulation': True}


def rehearse(manifest=None):
    protected = load(PUBLIC / 'protected-baseline.json')
    before = {p: digest((ROOT / p).read_bytes()) for p in protected}
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rule-isolated-', dir=ROOT / 'work') as tmp:
        root = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', '--shared', str(ROOT), str(root)], check=True)
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
        for name in filter(None, names):
            if name == 'node_modules' or name.startswith('node_modules/'):
                continue
            path = ROOT / name
            require(not path.is_symlink(), 'Symlinked rehearsal source')
            if not path.exists(): continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        (root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        (root / 'work').mkdir(exist_ok=True)
        # Store's root validation deliberately applies to the child, not the
        # parent. Copy checked raw objects without mounting a writable parent CAS.
        if manifest:
            packet = load(manifest)
            parent_store = Store()
            for entry in packet['sources']:
                for obj in entry.get('components', [entry]):
                    if 'originalSha256' not in obj: continue
                    raw = parent_store.read(obj['originalSha256'])
                    key = obj['originalSha256']
                    target = root / 'work/rule-admission/cas/sha256' / key[:2] / key[2:]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
            write(root / 'work/evidence.json', packet)
        else:
            # Generate the fixture inside the disposable root so Store still
            # enforces its real per-checkout private-path boundary.
            program = "import sys;sys.path.insert(0,'admission/v1');import rehearse;from runtime import ROOT,write;write(ROOT/'work/evidence.json',rehearse.fixture(ROOT))"
            subprocess.run(['python3', '-I', '-c', program], cwd=root, check=True)
        program = r'''
import sys
from pathlib import Path
sys.path.insert(0,'admission/v1')
import runtime as r
import release as release
import korean
import publish
import provenance
from evidence import Store
from copy import deepcopy
actual_reader=r.legacy.read_owner_comment
def reader(url, expected):
    assert url.startswith('test-fixture://isolated-rule/')
    return {'html_url':url,'body':expected,'created_at':'2026-10-30T00:00:00Z',
        'updated_at':'2026-10-30T00:00:00Z','principal':{'login':'isolated-rule-admission','id':0},'kind':'isolated-test-authority'}
r.legacy.read_owner_comment=reader
r.legacy.require_published=lambda base,identities=None:'a852596869d7ae157ef53fdf236ffbdaff5508c8'
release.pending_from_github=lambda: []  # No network/pending production PR reads inside this disposable authority fixture.
release.published_checkout=lambda commit: None  # Same isolated published-main dependency, never a production CLI switch.
provenance.origin_metadata=lambda: {'originPendingRegistry':{'identities':[]},'bundles':[{'files':{'candidates.json':[]}}]}
packet=r.load(Path('work/evidence.json'))
real_bytes=not packet.get('simulation',False)
if not real_bytes:
    import kr_evidence
    import identity
    # Only the unavailable external risk-original provider is synthetic in CI.
    # The live-original run exercises risk_screen without this replacement.
    identity.risk_screen=lambda *args: []
    def offline(evidence,store):
        result=korean.locked_metadata()
        return {**result,'evidenceVersionSha256':r.sha(evidence),'legacyAuthorizationInherited':False}
    korean.evaluate=offline
grants={'formatVersion':1,'authorizations':[{'policyKey':r.policy(k)['policyKey'],
    'bindings':r.checked_bindings(r.policy(k)),
    'approval':reader('test-fixture://isolated-rule/'+k,r.authority_text(r.policy(k)))} for k in ('identity','kr-code')]}
receipt=release.prepare(packet,Store(),grants,'0.10.1',Path('work/first'))
assert receipt['resolver']['conditionalResolved']==54
assert receipt['resolver']['formalRegressionQueries']==37736
assert receipt['resolver']['boundaryExtraResolved']==receipt['resolver']['formalChangedAnswers']==0
proof=release.validate(Path('work/first'))
if real_bytes:
    pr=publish.plan(Path('work/first'),Path('work/pr-plan'))
    assert pr['humanMergeRequired'] and not pr['autoMerge'] and not pr['simulation']
else:
    # The offline run must not pass production PR preparation's raw-byte guard.
    try: publish.plan(Path('work/first'),Path('work/forbidden-plan'))
    except ValueError as e: assert 'Full original replay' in str(e)
    else: raise AssertionError('Offline fixture prepared a production PR')
second=release.prepare(packet,Store(),grants,'0.10.1',Path('work/second'))
first_ids=[v['airportId'] for v in r.load(Path('work/first/identities.json'))['identities']]
second_ids=[v['airportId'] for v in r.load(Path('work/second/identities.json'))['identities']]
assert first_ids==second_ids and len(set(first_ids))==2
release.validate(Path('work/second'))
# Simulate that the reviewed batch has been merged, only inside this disposable
# published-main fixture. Daily repetition must not propose another data release.
r.write(r.ROOT/'data/airports.json',r.load(Path('work/second/proposed-data.json')))
r.write(r.PUBLIC/'identities.json',r.load(Path('work/second/identities.json')))
package=r.load(r.ROOT/'package.json')
package['version']='0.10.1'
r.write(r.ROOT/'package.json',package)
korean._REPLAY_CACHE.clear()  # A fresh daily execution cannot rely on the earlier package version's cache.
no_changes=release.prepare(packet,Store(),grants,'0.10.2',Path('work/after-merge'))
assert no_changes['status']=='NO_CHANGES' and no_changes['newPermanentIds']==no_changes['newPullRequests']==0
assert not Path('work/after-merge').exists()
# A clean production process receives the actual serialized fixture grants.
r.write(Path('work/test-grants.json'),grants)
result={'testOnly':True,'mode':'real-official-originals-test-authority' if real_bytes else 'synthetic-offline-test-authority',
    'originalBytesReadHere':real_bytes,'freshNetworkAcquisition':False,'productionSuccess':False,
    'classificationCounts':{'AUTO_ELIGIBLE':2},'conditionalResolved':54,'formalRegressionQueries':37736,
    'formalChangedAnswers':0,'boundaryExtraResolved':0,'distinctPhysicalSites':True,
    'repeatBatchReusesIds':True,'repeatAfterMergeIsNoOp':True,'identitySchemaStagePassed':True,'codeStagePassed':True,
    'bundleRevalidationPassed':True,'realResolveAirportUsed':True,
    'productionPrPlanPreparedInIsolation':real_bytes,'publicPrCreated':False,
    'formalKoreanIdentitiesCreated':0,'realAuthorizationsCreated':0}
r.write(Path('work/report.json'),result)
'''
        child = subprocess.run(['python3', '-I', '-c', program], cwd=root, capture_output=True, text=True)
        require(child.returncode == 0, 'End-to-end rehearsal failed: ' + child.stderr[-6000:])
        check = "import sys;sys.path.insert(0,'admission/v1');from runtime import *;authorize(policy('identity'),load(ROOT/'work/test-grants.json'))"
        rejected = subprocess.run(['python3', '-I', '-c', check], cwd=root, capture_output=True, text=True)
        require(rejected.returncode != 0 and 'Exact repository issue-comment URL required' in rejected.stderr,
                'Production accepted isolated test authority')
        result = load(root / 'work/report.json')
    require(before == {p: digest((ROOT / p).read_bytes()) for p in protected}, 'Rehearsal changed protected production files')
    return {**result, 'productionRejectedTestAuthority': True, 'protectedBaselineFilesUnchanged': len(before)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path)
    p.add_argument('--output', type=Path, default=PRIVATE / 'rehearsal.json')
    args = p.parse_args()
    result = rehearse(args.manifest)
    write(args.output, result)
    print(json.dumps(result))
