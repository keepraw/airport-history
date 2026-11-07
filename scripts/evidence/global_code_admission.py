"""Replay new data through the unchanged, owner-authorized AAI admission CLI.

The old intake has fixed paths. Restore its new data-only inputs in an isolated
published-baseline checkout instead of editing old research or extending a grant.
Preparation checked actual private originals; this command replays their receipt
offline, using the original gate's schema, evidence, authority and conflict rules.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASE = '7d21ff6762e1569faa1be19c8203e577420cd1f2'
DIRECTORY = ROOT / 'research/evidence/global-code-expansion/policy/aai-intake'
sys.path.insert(0, str(ROOT / 'scripts/evidence'))
from policy_executor import fingerprint
from policy_gate import authorization


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local(path):
    value = ROOT / path
    require(value.resolve().is_relative_to(ROOT), 'Replay input escapes the repository')
    return value


def check_inputs(candidate):
    manifest = load(DIRECTORY / 'replay-manifest.json')
    require(manifest['formatVersion'] == 1 and manifest['baselineCommit'] == BASE,
            'Unknown isolated admission baseline')
    require(manifest['baselinePath'] == 'test/curated-0.11.0.json' and
            manifest['candidatePath'] == 'test/curated-0.12.0.json' and
            manifest['bundlePath'] == 'research/admissions/0.12.0', 'Unexpected admission paths')
    require(digest(local(manifest['baselinePath'])) == manifest['baselineSha256'],
            'Published baseline snapshot changed')
    require(digest(candidate) == digest(local(manifest['candidatePath'])) == manifest['candidateSha256'],
            'Formal candidate differs from the immutable 0.12.0 admission')
    require(digest(local(manifest['bundlePath']) / 'proposed-data.json') == manifest['candidateSha256'],
            'Admission bundle differs from the exact candidate')
    execution = fingerprint()
    require(execution == manifest['executor'], 'Existing AAI executor changed')
    protected = set(execution['files']) | {'research/policy/policy.json',
        'research/policy/authorizations.json', 'research/policy/batch-authorizations.json',
        'research/admission/source-claims-v1/policy.json',
        'scripts/evidence/project_admission.py', 'scripts/evidence/admission_0110_coverage.ts'}
    for path in sorted(protected):
        original = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT)
        require(local(path).read_bytes() == original, 'Protected historical input changed: ' + path)
    grant = authorization(load(ROOT / 'research/policy/policy.json'))
    require(grant['authorizationSource'] == manifest['authorizationSource'], 'Different AAI authorization')
    # This is a data restoration allowlist, not an alternative policy evaluator.
    allowed = {'research/policy/input-lock.json', 'research/policy/source-lock.json',
        'research/policy/screening.json', 'research/evidence/global/generated/proposed-data.json',
        'research/evidence/global/generated/dossier.json',
        'research/evidence/global/generated/batches/global-evidence-proposal-2.json'}
    allowed |= {'research/policy/excerpts/' + name + '.json' for name in (
        'asia-in-11-06-2026-vosh', 'asia-in-11-06-2026-veay', 'asia-in-11-06-2026-vanm',
        'asia-in-09-07-2026-vosh', 'asia-in-09-07-2026-veay', 'asia-in-09-07-2026-vanm',
        'asia-in-11-06-2026-gen02')}
    targets = [row['target'] for row in manifest['overlayFiles']]
    require(len(targets) == len(set(targets)) and set(targets) == allowed,
            'Unexpected or missing data-only intake target')
    for row in manifest['overlayFiles']:
        expected_path = DIRECTORY / 'overlay' / row['target']
        source = local(row['path'])
        require(source == expected_path and digest(source) == row['sha256'] and
                source.stat().st_size == row['bytes'], 'Changed data-only intake file: ' + row['target'])
    return manifest


def validate(candidate=None):
    candidate = ROOT / 'data/airports.json' if candidate is None else candidate.resolve()
    manifest = check_inputs(candidate)
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aai-data-replay-', dir=ROOT / 'work') as name:
        checkout = Path(name)
        subprocess.run(['git', 'clone', '--quiet', '--shared', '--no-checkout', str(ROOT), name], check=True)
        subprocess.run(['git', 'checkout', '--quiet', '--detach', BASE], cwd=checkout, check=True)
        subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', BASE], cwd=checkout, check=True)
        (checkout / 'work').mkdir(exist_ok=True)
        (checkout / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        with (checkout / '.git/info/exclude').open('a') as exclude:
            exclude.write('\n/node_modules\n')
        # Keep the previous China identity-only gate and measurements on their exact
        # published bytes. No Chinese code authority is inferred for the new batch.
        subprocess.run(['python3', 'scripts/evidence/project_admission.py'], cwd=checkout, check=True)
        subprocess.run(['node', 'scripts/evidence/admission_0110_coverage.ts', 'validate'], cwd=checkout, check=True)
        for row in manifest['overlayFiles']:
            destination = checkout / row['target']
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(local(row['path']).read_bytes())
        # The same executable recomputes decisions, authorization, exact proposal,
        # batches, dossier and offline original receipt; this wrapper grants nothing.
        subprocess.run(['python3', 'scripts/evidence/policy_formal.py', '--candidate', str(candidate),
            '--bundle', str(local(manifest['bundlePath']))], cwd=checkout, check=True)
        observed = json.loads(subprocess.check_output(['python3', '-c',
            'import json,sys;sys.path.insert(0,"scripts/evidence");'
            'from policy_executor import fingerprint;print(json.dumps(fingerprint()))'], cwd=checkout))
        require(observed == manifest['executor'], 'Isolated AAI executor changed during replay')
    check_inputs(candidate)
    if candidate == ROOT / 'data/airports.json':
        subprocess.run(['node', 'scripts/evidence/admission_0120_coverage.ts', 'validate'], cwd=ROOT, check=True)
    print('0.12.0 admitted by unchanged AAI policy/gate: 3 ICAO assignments; '
          'actual original receipt replayed OFFLINE; no new authority or original downloads.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    validate(args.candidate)
