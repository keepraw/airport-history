"""The only network-enabled research entry point. Never imported by runtime/checks."""
import argparse
import json
import subprocess
import urllib.request
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'research/discovery/sources.json')
    args = parser.parse_args()
    config = json.loads(args.manifest.read_text())
    repositories = {}
    for source in config['sources']:
        repositories.setdefault(source['localRepository'], []).append(source)
    for local, sources in repositories.items():
        repo = ROOT / local
        url = sources[0]['url'] + '.git'
        repo.parent.mkdir(parents=True, exist_ok=True)
        if not repo.exists():
            subprocess.run(['git', 'clone', '--mirror', url, str(repo)], check=True)
        else:
            remote = subprocess.check_output(['git', '-C', str(repo), 'remote', 'get-url', 'origin']).decode().strip()
            if remote != url:
                raise ValueError(f'Unexpected origin for {local}')
            subprocess.run(['git', '-C', str(repo), 'fetch', '--prune', 'origin'], check=True)
        for source in sources:
            subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', source['revision'] + '^{commit}'], check=True)
    baseline = json.loads((ROOT / 'research/discovery/keepraw-fly-baseline.json').read_text())
    url = 'https://raw.githubusercontent.com/keepraw/Keepraw-Fly/' + baseline['revision'] + '/' + baseline['path']
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != baseline['sha256']:
        raise ValueError('Downloaded baseline checksum mismatch')
    path = ROOT / baseline['inputPath']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


if __name__ == '__main__':
    main()
