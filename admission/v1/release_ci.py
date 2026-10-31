"""Run frozen legacy release checks plus the versioned extension validation.

Private originals are unavailable on public CI. This command explicitly reports
that limitation and can never be used as the production publication validator.
"""
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile

from runtime import ROOT, load, require
from release import validate


def main():
    current = load(ROOT / 'data/airports.json')
    bundle = ROOT / 'research/admissions' / current['dataVersion'] / 'rule-v1'
    if not bundle.exists():
        subprocess.run(['pnpm', 'check'], cwd=ROOT, check=True)
        return
    proof = validate(bundle, originals=False)
    require(proof['originalBytesReadHere'] is False and proof['productionValidationPassed'] is False,
            'Offline CI overclaimed private-original verification')
    receipt = load(bundle / 'receipt.json')
    require(load(bundle / 'proposed-data.json') == current and
            load(ROOT / 'package.json')['version'] == current['dataVersion'], 'Published release detached from bundle/package')
    # Neither country's historical executor/grant is rewritten. Run it with the
    # exact historical tree on which its authorization was actually valid.
    with tempfile.TemporaryDirectory(prefix='legacy-release-', dir=ROOT / 'work') as tmp:
        root = Path(tmp)
        archive = subprocess.check_output(['git', 'archive', receipt['baselineCommit']], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter='data')
        (root / 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        subprocess.run(['git', 'fetch', '--quiet', str(ROOT), receipt['baselineCommit']], cwd=root, check=True)
        subprocess.run(['git', 'reset', '--quiet', receipt['baselineCommit']], cwd=root, check=True)
        subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', receipt['baselineCommit']], cwd=root, check=True)
        command = ['python3', 'admission/v1/release_ci.py'] if (root / 'admission/v1/release_ci.py').exists() else ['pnpm', 'check']
        subprocess.run(command, cwd=root, check=True)
    print('Versioned candidate schema/immutability/resolver and frozen legacy pnpm check passed. '
          'OFFLINE CI: private originals were not replayed; fresh production validation is separate.')


if __name__ == '__main__':
    main()
