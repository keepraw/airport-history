"""Offline, deterministic reference primitives; no historical validity inference."""
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISCOVERY = ROOT / 'research/discovery/generated'
OUTPUT = ROOT / 'reference/generated'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def stable_id(prefix, value):
    return prefix + hashlib.sha256(canonical(value).encode()).hexdigest()[:24]


def read_jsonl(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            for row in rows:
                compressed.write((canonical(row) + '\n').encode())


def position(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return {'latitude': lat, 'longitude': lon}
    except (ValueError, TypeError):
        pass
    return None


def distance(a, b):
    if a is None or b is None:
        return None
    x, y = math.radians(b['latitude'] - a['latitude']), math.radians(b['longitude'] - a['longitude'])
    q = math.sin(x / 2) ** 2 + math.cos(math.radians(a['latitude'])) * math.cos(math.radians(b['latitude'])) * math.sin(y / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(max(0, q))))


def checked(path, expected):
    if digest(path) != expected:
        raise ValueError(f'Changed pinned input: {path}')


def research_baseline_path():
    """Immutable input of the PR11-13 research snapshots, independent of later admissions."""
    path = ROOT / 'test/curated-0.7.0.json'
    checked(path, '31c5735b333881d7afdd527fe4af1db8e28413d5bba114fbf88a4aad0809cff7')
    return path


def verify_discovery(names):
    lock = json.loads((DISCOVERY / 'manifest.json').read_text())
    for name in names:
        checked(DISCOVERY / name, lock['files'][name]['sha256'])


def manifest(directory, inputs, **metadata):
    write_json(directory / 'manifest.json', {
        'formatVersion': 1, **metadata, 'inputs': {str(p.relative_to(ROOT)): digest(p) for p in sorted(inputs)},
        'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                  for p in sorted(directory.iterdir()) if p.is_file() and p.name != 'manifest.json'},
    })
