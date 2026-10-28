"""Explicit recovery of the exact pinned input; never fetch a moving branch."""
import gzip
import hashlib
import json
import urllib.request
from common import ROOT


def main():
    lock = json.loads((ROOT / 'reference/source-lock.json').read_text())
    with urllib.request.urlopen(lock['downloadUrl'], timeout=60) as response:
        raw = response.read()
    if hashlib.sha256(raw).hexdigest() != lock['sha256']:
        raise ValueError('Downloaded snapshot does not match pinned SHA-256')
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if blob != lock['gitBlob']:
        raise ValueError('Downloaded snapshot does not match pinned Git blob')
    with (ROOT / 'reference/inputs/ourairports.csv.gz').open('wb') as f:
        with gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0) as z:
            z.write(raw)
    print(f"Recovered {lock['revision']} ({len(raw):,} bytes); no history scan.")


if __name__ == '__main__':
    main()
