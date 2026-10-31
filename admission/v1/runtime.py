"""Versioned admission runtime. No discovery globs in an authorization binding."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'research/admission/rule-v1'
PRIVATE = ROOT / 'work/rule-admission'
sys.path.insert(0, str(ROOT / 'scripts/admission'))
import kr_adapter as legacy


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False).encode() + b'\n')


def private_path(path, *, new=False):
    path = Path(path).absolute()
    require(path.resolve().is_relative_to((ROOT / 'work').resolve()), 'Output must stay in ignored work/')
    require(not any(p.is_symlink() for p in [path, *path.parents] if p != ROOT.parent), 'Symlinked private path')
    require(not new or not path.exists(), 'Output already exists; never overwrite a bundle')
    return path


def policy(kind):
    require(kind in ('identity', 'kr-code'), 'Unknown policy: default deny')
    return load(PUBLIC / (kind + '-policy.json'))


def fingerprint():
    # A reviewed explicit transitive closure. A third country's new module does
    # not silently enter this executor; edits to this closure require reapproval.
    definition = load(PUBLIC / 'executor-inputs.json')
    require(definition['formatVersion'] == 2, 'Unsupported executor manifest')
    files = {}
    for name in definition['files']:
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and path.is_file() and not (ROOT / name).is_symlink(), 'Unsafe executor input')
        files[name] = digest(path.read_bytes())
    package = load(ROOT / 'package.json')
    package.pop('version')  # The signed release rules alone permit this scalar to increase.
    payload = {'formatVersion': 2, 'files': files, 'canonicalJsonInputs': {'package.json': sha(package)},
               'releaseVariableFields': ['package.json#/version']}
    return {**payload, 'executorSha256': sha(payload)}


def bindings(p):
    return {'policyKey': p['policyKey'], 'policySha256': sha(p), 'scopeSha256': sha(p['scope']),
            'executorSha256': fingerprint()['executorSha256']}


def checked_bindings(p):
    expected = load(PUBLIC / 'bindings.json')
    actual = bindings(p)
    require(expected['policies'].get(p['policyKey']) == actual and expected['manifest'] == fingerprint(),
            'Policy, Scope or Executor changed; independent rule authorization required')
    return actual


def authority_text(p):
    b = checked_bindings(p)
    return (f"Authorize rule {p['policyKey']} policy-sha256:{b['policySha256']} "
            f"scope-sha256:{b['scopeSha256']} executor-sha256:{b['executorSha256']}. "
            + p['authorizationTerms'])


def authorize(p, registry):
    require(registry.get('formatVersion') == 1 and set(registry) == {'formatVersion', 'authorizations'}, 'Invalid grant registry')
    grants = [g for g in registry['authorizations'] if g.get('policyKey') == p['policyKey']]
    require(len(grants) == 1, 'Missing or ambiguous real Owner rule authorization: ' + p['policyKey'])
    grant = grants[0]
    require(set(grant) == {'policyKey', 'bindings', 'approval'} and grant['bindings'] == checked_bindings(p),
            'Exact authorization binding mismatch')
    # No fixture transport, approved boolean, environment switch, or CLI test flag.
    require(legacy.read_owner_comment(grant['approval']['html_url'], authority_text(p)) == grant['approval'],
            'Owner rule approval edited, revoked or fabricated')
    return grant


def version(value, baseline):
    require(re.fullmatch(r'\d+\.\d+\.\d+', value or '') and
            tuple(map(int, value.split('.'))) > tuple(map(int, baseline.split('.'))), 'Increasing dataVersion required')
