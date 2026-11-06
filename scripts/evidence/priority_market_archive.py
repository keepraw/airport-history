"""Replay the immutable PR22 research validator without freezing future formal data."""
import json
from pathlib import Path
import subprocess
import tempfile
import tarfile
import io

ROOT = Path(__file__).resolve().parents[2]
COMMIT = 'b201f4a'

def main():
    old = json.loads((ROOT / 'test/curated-0.10.0.json').read_text())
    current = json.loads((ROOT / 'data/airports.json').read_text())
    for key in ('airports', 'assignments', 'sources', 'names'):
        if current[key][:len(old[key])] != old[key]:
            raise ValueError('Published records changed')
    # The original script and all draft fingerprints remain byte-identical.
    paths = ['scripts/evidence/priority_markets.py', 'scripts/evidence/priority_market_coverage.ts']
    paths += [str(p.relative_to(ROOT)) for p in (ROOT / 'research/evidence/priority-markets').rglob('*') if p.is_file()]
    for path in paths:
        expected = subprocess.check_output(['git', 'show', f'{COMMIT}:{path}'], cwd=ROOT)
        if (ROOT / path).read_bytes() != expected:
            raise ValueError('Archived research changed: ' + path)
    (ROOT / 'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pr22-archive-', dir=ROOT / 'work') as tmp:
        raw = subprocess.check_output(['git', 'archive', COMMIT], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            archive.extractall(tmp, filter='data')
        Path(tmp, 'node_modules').symlink_to(ROOT / 'node_modules', target_is_directory=True)
        subprocess.run(['python3', 'scripts/evidence/priority_markets.py', 'validate'], cwd=tmp, check=True)
    print('Immutable PR22 research replay passed; current formal records checked separately.')

if __name__ == '__main__':
    main()
