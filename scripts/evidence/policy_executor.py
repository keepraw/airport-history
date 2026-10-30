"""Bind owner authorization to the executable evidence/admission semantics."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    'scripts/evidence/policy_executor.py', 'scripts/evidence/policy_review.py',
    'scripts/evidence/policy_gate.py', 'scripts/evidence/policy_originals.py',
    'scripts/evidence/policy_formal.py', 'scripts/evidence/policy_coverage.ts',
    'scripts/evidence/review.py',
    'scripts/evidence/global_batch.py', 'scripts/reference/admissions.py',
    'scripts/reference/common.py', 'scripts/reference/query.py', 'scripts/discovery/review.py',
    'src/resolve.ts', 'src/names.ts', 'src/time.ts', 'src/evidence.ts',
    'src/validate.ts', 'src/types.ts', 'schema/dataset.schema.json', 'pnpm-lock.yaml',
)


def fingerprint():
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(FILES)}
    payload = {'formatVersion': 1, 'files': files}
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return {**payload, 'executorSha256': hashlib.sha256(encoded).hexdigest()}


def require_binding(grant):
    if grant.get('executorSha256') != fingerprint()['executorSha256']:
        raise ValueError('Executor changed or unbound: new explicit authorization is required')
