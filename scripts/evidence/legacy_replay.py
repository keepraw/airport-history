"""Replay frozen legacy checks when their grants bind the old package/data.

No evaluator or grant is rewritten. Changed legacy source/test files fail closed;
current formal data is checked by validate:data and validate:admission separately.
"""
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
ROOT = Path(__file__).resolve().parents[2]
BASE = '1e35d424a42377ea80c5c4ab53e1ee3d492b5acf'
COMMANDS = {
    'aai-validate': ['pnpm', 'policy:validate'],
    'aai-rehearsal': ['python3', 'scripts/evidence/policy_rehearsal.py'],
    'evidence-tests': ['python3', '-m', 'unittest', 'discover', '-s', 'test/evidence', '-v'],
    'kr-verify': ['python3', 'scripts/admission/kr_verify.py', 'validate'],
    'kr-rehearsal': ['python3', 'scripts/admission/kr_rehearsal.py'],
    'kr-rights': ['python3', 'scripts/evidence/korea_readiness.py', 'rights'],
    'rule-verify': ['python3', 'admission/v1/verify.py'],
    'rule-registration': ['python3', 'admission/v1/test_registration.py'],
    'rule-engine': ['python3', 'admission/v1/test_engine.py'],
}

def main():
    command = sys.argv[1]
    args = COMMANDS[command]
    # Check the live executable/source/test inputs before replaying their old contract.
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', BASE,
                                    'scripts', 'src', 'schema', 'test', 'admission', 'research', 'pnpm-lock.yaml'], cwd=ROOT).decode().rstrip('\0').split('\0')
    for path in paths:
        expected = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT)
        if (ROOT / path).read_bytes() != expected:
            raise ValueError('Legacy input changed; archival replay cannot validate it: ' + path)
    (ROOT / 'work').mkdir(exist_ok=True)
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASE, 'origin/main'], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory(prefix='legacy-replay-', dir=ROOT / 'work') as tmp:
        # A real repository is required by baseline/ancestry tests and authorization checks.
        subprocess.run(['git', 'clone', '--quiet', '--shared', str(ROOT), tmp], check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--detach', BASE], cwd=tmp, check=True)
        subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', BASE], cwd=tmp, check=True)
        Path(tmp, 'work').mkdir(exist_ok=True)
        Path(tmp, 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        subprocess.run(args, cwd=tmp, check=True)
    if command == 'evidence-tests':
        subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'test/evidence', '-p', 'test_project_admission.py', '-v'], cwd=ROOT, check=True)
    print('Frozen legacy contract replay passed:', command)

if __name__ == '__main__': main()
