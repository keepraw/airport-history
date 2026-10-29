"""Audit complete PR ancestry using public, domain-separated object fingerprints.

No private inventory or remote object download is needed. Remote accessibility is
separate, dated evidence; a clean ancestry result never establishes remote erasure.
"""
import bz2
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / 'research/evidence/history/pr15-rights-audit.json'
OID = re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])')
FINGERPRINT = re.compile(r'[0-9a-f]{64}')
MAX_PAYLOAD = 16 * 1024 * 1024
PRIVATE_PATH = re.compile(
    r'^(work/|research/evidence/(global|markets|transfers)/(inputs|texts|originals|cache)/)')


def fingerprint(kind, oid):
    """SHA256(ASCII namespace + NUL + normalized full SHA-1), lowercase hex.

    Strip only ASCII space/tab/CR/LF, lowercase ASCII hex, require all 40 digits.
    Abbreviations, Unicode lookalikes and other object algorithms are rejected.
    This is an audit comparison key, not secrecy or remote deletion.
    """
    if kind not in ('blob', 'commit') or not isinstance(oid, str):
        raise ValueError('Expected a blob/commit kind and full Git SHA-1 string')
    oid = oid.strip(' \t\r\n').lower()
    if re.fullmatch(r'[0-9a-f]{40}', oid) is None:
        raise ValueError('Expected exactly 40 ASCII hexadecimal Git SHA-1 digits')
    return hashlib.sha256(('restricted-git-' + kind + '-v1\0' + oid).encode('ascii')).hexdigest()


def git(root, *args, input=None):
    try:
        return subprocess.check_output(
            ['git', '--no-replace-objects', '-C', str(root), *args], input=input,
            stderr=subprocess.PIPE,
            env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})
    except subprocess.CalledProcessError as error:
        raise ValueError('Complete Git history and objects are required for the ancestry audit') from error


def inventory(audit):
    if audit.get('formatVersion') != 2:
        raise ValueError('Fingerprint audit formatVersion 2 is required')
    blobs = {f['gitBlobFingerprint'] for s in audit['sources'] for f in s['files']}
    commits = set(audit['restrictedCommitFingerprints'])
    locators = set(audit.get('locatorExposureCommitFingerprints', []))
    if not blobs or any(FINGERPRINT.fullmatch(v) is None for v in blobs | commits | locators):
        raise ValueError('Invalid or empty restricted-object fingerprint inventory')
    content = {f['decompressedSha256'] for s in audit['sources'] for f in s['files']}
    return blobs, commits, locators, content


def check_locators(text, blobs, commits):
    for match in OID.finditer(text):
        oid = match.group()
        if fingerprint('blob', oid) in blobs or fingerprint('commit', oid) in commits:
            raise ValueError('Direct restricted Git object locator in public PR content')


def check_payload(raw, blobs, commits, content_hashes, depth=0):
    """Inspect bytes and archive members, independently of path or extension.

    Known full original/extraction hashes also catch changed compression. This
    is a mechanical gate, not a general determination of redistribution rights;
    new publications still require source-by-source review.
    """
    if depth > 6 or len(raw) > MAX_PAYLOAD:
        raise ValueError('Public payload exceeds bounded content-review limits')
    if hashlib.sha256(raw).hexdigest() in content_hashes:
        raise ValueError('Restricted full original/extraction content in PR history')
    if raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            check_payload(stream.read(MAX_PAYLOAD + 1), blobs, commits, content_hashes, depth + 1)
        return
    if raw.startswith((b'BZh', b'\xfd7zXZ\0')):
        opener = bz2.open if raw.startswith(b'BZh') else lzma.open
        with opener(io.BytesIO(raw), 'rb') as stream:
            check_payload(stream.read(MAX_PAYLOAD + 1), blobs, commits, content_hashes, depth + 1)
        return
    if raw.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            total = 0
            for entry in archive.infolist():
                total += entry.file_size
                if total > MAX_PAYLOAD:
                    raise ValueError('Public archive exceeds content-review limits')
                check_locators(entry.filename, blobs, commits)
                with archive.open(entry) as stream:
                    check_payload(stream.read(MAX_PAYLOAD + 1), blobs, commits, content_hashes, depth + 1)
        return
    if raw[257:262] == b'ustar':
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
            total = 0
            for entry in archive:
                total += entry.size
                if total > MAX_PAYLOAD or not (entry.isfile() or entry.isdir()):
                    raise ValueError('Unreviewed public archive member')
                check_locators(entry.name, blobs, commits)
                if entry.isfile():
                    with archive.extractfile(entry) as stream:
                        check_payload(stream.read(MAX_PAYLOAD + 1), blobs, commits, content_hashes, depth + 1)
        return
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError('Unreviewed binary payload in new PR content') from error
    stripped = text.lstrip('\ufeff \t\r\n').lower()
    if stripped.startswith('%pdf-') or re.match(r'<(?:!doctype\s+html|html|head|body)(?:\s|>)', stripped):
        raise ValueError('Full PDF/HTML response in public PR content')
    check_locators(text, blobs, commits)
    # JSON escaping must not hide a full response, extraction or direct locator.
    if stripped.startswith(('{', '[')):
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            return  # JSONL and source code are still checked as raw text above.

        def inspect(value):
            if isinstance(value, str):
                check_payload(value.encode(), blobs, commits, content_hashes, depth + 1)
            elif isinstance(value, dict):
                for key, child in value.items():
                    check_locators(key, blobs, commits)
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)
        inspect(document)


def tree(root, commit):
    result = []
    for row in git(root, 'ls-tree', '-r', '-z', commit).split(b'\0'):
        if row:
            metadata, path = row.split(b'\t', 1)
            mode, kind, oid = metadata.decode('ascii').split()
            if kind != 'blob' or mode not in ('100644', '100755'):
                raise ValueError('Unreviewed submodule or symbolic link in PR tree')
            result.append((oid, path.decode('utf-8')))
    return result


def verify(root=ROOT, audit=None, head='HEAD'):
    audit = json.loads(AUDIT.read_text()) if audit is None else audit
    blocked, bad_commits, locator_commits, content_hashes = inventory(audit)
    base = audit['base']
    if git(root, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise ValueError('Complete Git history is required for the ancestry audit')
    grafts = Path(git(root, 'rev-parse', '--git-path', 'info/grafts').decode().strip())
    if not grafts.is_absolute():
        grafts = Path(root) / grafts
    if grafts.exists():
        raise ValueError('Complete unmodified Git ancestry is required; grafts are unsupported')
    ancestors = git(root, 'rev-list', head).decode().splitlines()
    if any(fingerprint('commit', c) in bad_commits for c in ancestors):
        raise ValueError('Restricted-original commit remains an ancestor')
    if any(fingerprint('commit', c) in locator_commits for c in ancestors):
        raise ValueError('Retired locator-exposure commit remains an ancestor')
    if base not in ancestors:
        raise ValueError('Latest pinned main must remain an ancestor')
    # Missing blobs in a partial clone must fail even if commits/trees exist.
    objects = git(root, 'rev-list', '--objects', '--no-object-names', head)
    presence = git(root, 'cat-file', '--batch-check', input=objects)
    if any(row.endswith(b' missing') for row in presence.splitlines()):
        raise ValueError('Complete Git history and objects are required; missing object')
    commits = git(root, 'rev-list', head, '^' + base).decode().splitlines()
    base_blobs = {oid for oid, _ in tree(root, base)}
    # Public locks cover full originals acquired after the 92-pair audit too.
    # No private cache is read, and source/hash values are never modified here.
    for scope in ('global', 'markets', 'transfers'):
        path = Path(root) / 'research/evidence' / scope / 'source-lock.json'
        if path.exists():
            for source in json.loads(path.read_text())['sources']:
                content_hashes.update(source[k] for k in ('originalSha256', 'textOriginalSha256'))
    inspected = set()
    for commit in commits:
        check_locators(git(root, 'show', '-s', '--format=%B', commit).decode(), blocked, bad_commits | locator_commits)
        for oid, path in tree(root, commit):
            if fingerprint('blob', oid) in blocked or PRIVATE_PATH.match(path):
                raise ValueError('Restricted full original/extraction reachable in PR history')
            check_locators(path, blocked, bad_commits | locator_commits)
            if oid not in base_blobs and oid not in inspected:
                check_payload(git(root, 'cat-file', 'blob', oid), blocked,
                              bad_commits | locator_commits, content_hashes)
                inspected.add(oid)
    clean = audit.get('cleanSnapshot')
    if clean:
        if clean['commit'] not in ancestors:
            raise ValueError('Pinned clean snapshot must remain an ancestor')
        if git(root, 'rev-parse', clean['commit'] + '^{tree}').decode().strip() != clean['tree']:
            raise ValueError('Clean snapshot tree changed')
        parents = git(root, 'rev-list', '--parents', '-n', '1', clean['commit']).decode().split()[1:]
        if parents != [base]:
            raise ValueError('Clean snapshot must be based directly on pinned main')
    residual = audit.get('residualRisk', {})
    return {'reachablePRCommits': len(commits), 'restrictedFileBlobs': len(blocked),
            'restrictedAncestorCommits': 0, 'restrictedReachableBlobs': 0,
            'locatorExposureAncestorCommits': 0, 'inspectedNewFileBlobs': len(inspected),
            'currentPRAncestryClean': True,
            'remoteOldObjectsStillAccessible': residual.get('remoteOldObjectsStillAccessible'),
            'remoteEvidenceCheckedAt': residual.get('checkedAt'),
            'remoteAccessibilityCheckedByThisCommand': False,
            'scope': 'Complete reachable PR history. Remote deletion is not established.'}


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False))
