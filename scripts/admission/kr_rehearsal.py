"""Disposable identity + policy + actual resolver exercise with an unmistakable test principal."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from kr_adapter import ROOT, DIRECTORY, load, write, require


def rehearse():
    protected = load(DIRECTORY / 'protected-baseline.json')
    before = {p: (ROOT / p).read_bytes() for p in protected}
    with tempfile.TemporaryDirectory(prefix='kr-isolated-', dir=ROOT / 'work') as tmp:
        root = Path(tmp) / 'repo'
        paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
        for name in filter(None, paths):
            source = ROOT / name
            require(not source.is_symlink(), 'Symlink in rehearsal source')
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        (root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        (root / 'work').mkdir()
        # Nothing below is committed, published or accepted by a production process.
        program = '''import json,sys
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,'scripts/admission')
import kr_adapter as a
real_evaluate=a.evaluate
a.OWNER={'login':'isolated-korean-rehearsal','id':0}
a.AUTHORITY_KIND='isolated-test-authority'
def reader(url, expected):
    assert url in ('test-fixture://kr/identity','test-fixture://kr/policy')
    return {'html_url':url,'body':expected,'created_at':'2026-10-30T00:00:00Z',
            'updated_at':'2026-10-30T00:00:00Z','principal':a.OWNER,'kind':a.AUTHORITY_KIND}
a.read_owner_comment=reader
# This disposable copy has intentionally unpublished test identities. The
# published-main dependency is isolated together with its distinct principal.
a.require_published=lambda data, identities=None: 'isolated-unpublished-test-copy'
def offline(p, *, originals=False):
    result=real_evaluate(p,originals=False)
    assert result['originalBytesReadHere'] is False
    return result
a.evaluate=offline
p=a.policy()
a.prepare_identities(Path('work/identities'), 'test-fixture://kr/identity', '0.10.1')
identity_candidate=a.load(Path('work/identities/proposed-data.json'))
a.write(a.ROOT/'data/airports.json',identity_candidate)
a.write(a.DIRECTORY/'identities.json',a.load(Path('work/identities/identities.json')))
ids=a.physical_identities(p,identity_candidate)
negative_checks=[]
registry=a.load(a.DIRECTORY/'identities.json')
def deny(label, action):
    try: action()
    except ValueError: negative_checks.append(label)
    else: raise AssertionError('Negative admission unexpectedly passed: '+label)
for label in ('test-permanent-id','wrong-airport-id','different-site','conflicting-arp','missing-identity-approval'):
    altered=deepcopy(registry)
    data=deepcopy(identity_candidate)
    if label=='test-permanent-id': altered['identities'][0]['airportId']='simulation-only'
    elif label=='wrong-airport-id': altered['identities'][0]['airportId']=altered['identities'][1]['airportId']
    elif label=='different-site':
        record=next(r for r in data['airports'] if r['airportId']==altered['identities'][0]['airportId'])
        record['coordinates']['value']['latitude']+=1
        altered['identities'][0]['recordSha256']=a.sha(record)
    elif label=='conflicting-arp':
        record=next(r for r in data['airports'] if r['airportId']==altered['identities'][0]['airportId'])
        record['coordinates']['value']['latitude']+=0.001
    else: altered['identities'][0]['approval']['principal']['id']=-1
    a.write(a.DIRECTORY/'identities.json',altered)
    deny(label,lambda:a.physical_identities(p,data))
a.write(a.DIRECTORY/'identities.json',registry)
deny('missing-policy-authorization',lambda:a.authorization(p,ids))
grant={'policyKey':a.KEY,'bindings':a.checked_bindings(p),'identitiesSha256':a.sha(ids),
       'approval':reader('test-fixture://kr/policy',a.policy_text(p,ids))}
for field in ('policySha256','scopeSha256','executorSha256'):
    changed=deepcopy(grant)
    changed['bindings'][field]='0'*64
    a.write(a.DIRECTORY/'authorizations.json',{'formatVersion':1,'authorizations':[changed]})
    deny('changed-'+field,lambda:a.authorization(p,ids))
a.write(a.DIRECTORY/'authorizations.json',{'formatVersion':1,'authorizations':[grant]})
report=a.prepare(p,Path('work/proposal'),'0.10.2')
receipt=a.load(Path('work/proposal/receipt.json'))
assert receipt['evidence']['originalBytesReadHere'] is False
assert report['conditionalResolved']==54 and report['formalRegressionQueries']==37736
assert report['formalChangedAnswers']==report['formalNewResolved']==report['boundaryExtraResolved']==0
report['isolatedNegativeChecks']=negative_checks
a.write(Path('work/report.json'),report)
'''
        completed = subprocess.run(['python3', '-c', program], cwd=root, capture_output=True, text=True)
        require(completed.returncode == 0, 'Isolated rehearsal failed: ' + completed.stderr[-5000:])
        # No dependency injection in this second process: real authority must reject the fixture.
        rejected = subprocess.run(['python3', 'scripts/admission/kr_adapter.py', 'admit', '--data-version', '0.10.2',
                                   '--output', 'work/production-must-reject'], cwd=root, capture_output=True, text=True)
        require(rejected.returncode != 0 and 'Invalid physical identity approval' in rejected.stderr and
                not (root / 'work/production-must-reject').exists(), 'Production accepted test identity/authorization')
        report = load(root / 'work/report.json')
    require(all((ROOT / p).read_bytes() == raw for p, raw in before.items()), 'Rehearsal changed real baseline')
    return {**report, 'testOnly': True, 'mode': 'isolated-offline-locked-evidence-replay',
            'productionRejectedTestAuthority': True, 'realFilesUnchanged': True,
            'originalBytesReadHere': False, 'freshNetworkAcquisition': False,
            'identityAdmissionGate': 'original-human-validate_admission',
            'formalKoreanIdentitiesCreated': 0, 'realKoreanAuthorizationsCreated': 0}


if __name__ == '__main__':
    (ROOT / 'work').mkdir(exist_ok=True)
    result = rehearse()
    write(ROOT / 'work/pr25/rehearsal.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'outcomes'}, sort_keys=True))
