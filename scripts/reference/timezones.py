"""Recover a pinned IANA identifier catalog without consulting the host tzdb."""
import argparse
import hashlib
import io
import json
import re
import tarfile
import urllib.request

from common import ROOT, write_json


def catalog(raw, lock):
    if hashlib.sha256(raw).hexdigest() != lock['sha256']:
        raise ValueError('IANA archive does not match the pinned SHA-256')
    zones = set()
    # Read selected text members only; never extract archive paths to the filesystem.
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for name in lock['sourceFiles']:
            member = archive.extractfile(name)
            if member is None:
                raise ValueError('Missing pinned tzdb source file')
            with member:
                for line in member.read().decode('utf-8').splitlines():
                    match = re.match(r'^Zone\s+(\S+)|^Link\s+\S+\s+(\S+)', line)
                    if match:
                        zones.add(match[1] or match[2])
    return {'formatVersion': 1, 'tzdbVersion': lock['version'], 'zones': sorted(zones)}


def load_catalog():
    lock = json.loads((ROOT / 'reference/timezones-lock.json').read_text())
    data = json.loads((ROOT / 'reference/inputs/iana-timezones.json').read_text())
    if data['tzdbVersion'] != lock['version'] or data['zones'] != sorted(set(data['zones'])):
        raise ValueError('Invalid pinned timezone catalog')
    return set(data['zones'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', required=True, help='Explicitly recover the exact pinned IANA release')
    parser.parse_args()
    lock = json.loads((ROOT / 'reference/timezones-lock.json').read_text())
    with urllib.request.urlopen(lock['downloadUrl'], timeout=60) as response:
        raw = response.read()
    write_json(ROOT / 'reference/inputs/iana-timezones.json', catalog(raw, lock))
