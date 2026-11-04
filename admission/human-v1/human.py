"""Human Admission v1 command line.

prepare -> verify-originals -> build -> approval-text -> (Owner comments) ->
record-approval -> validate -> submit. ``ci`` is the CI entry point.

There is no flag that skips Owner verification, original replay or any gate.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402
from core import ROOT, WORK, AdmissionError, bundle_dir, dump, load, require, sha, sha_bytes  # noqa: E402


def prepare(spec_path, base_commit=None):
    spec = load(spec_path)
    core.validate_spec(spec)
    base_commit = base_commit or core.git('rev-parse', 'origin/main')
    baseline, base = core.published_baseline(base_commit)
    require((ROOT / 'data/airports.json').read_bytes() ==
            subprocess.check_output(['git', 'show', base_commit + ':data/airports.json'], cwd=ROOT),
            'Working tree data differs from the published base; prepare on current main')
    require(core.version_tuple(spec['targetDataVersion']) > core.version_tuple(baseline['baseDataVersion']),
            'Target dataVersion must increase')
    bundle = bundle_dir(spec['targetDataVersion'])
    require(not bundle.exists() or not any(bundle.iterdir()), 'Bundle already exists; use a new batch/version')
    records = core.record_list(spec)
    core.check_single_active(spec['targetDataVersion'], baseline['baseDataVersion'], records)
    spec = {**spec, 'baseCommit': base_commit}
    batches = core.review_batches(spec)
    core.validate_evidence_lock(spec['evidence']['lock'], records)
    dump(bundle / 'prepare.json', {'format': core.FORMAT, 'batchId': spec['batchId'], 'reviewedOn': spec['reviewedOn'],
                                   **baseline, 'targetDataVersion': spec['targetDataVersion']})
    dump(bundle / 'records.json', {'format': core.FORMAT, 'batchId': spec['batchId'], 'records': records})
    dump(bundle / 'excluded.json', spec['excluded'])
    dump(bundle / 'evidence-lock.json', spec['evidence']['lock'])
    dump(bundle / 'dossier.json', spec['dossier'])
    for batch in batches:
        dump(bundle / 'batches' / (batch['batchId'] + '.json'), batch)
    return bundle


def verify_originals(version, fetcher=None):
    bundle = bundle_dir(version)
    lock, records = load(bundle / 'evidence-lock.json'), load(bundle / 'records.json')['records']
    receipt = core.verify_originals(lock, records, WORK / load(bundle / 'prepare.json')['batchId'] / 'originals', fetcher)
    dump(bundle / 'original-verification.json', receipt)
    return receipt


def build(version):
    bundle = bundle_dir(version)
    meta = load(bundle / 'prepare.json')
    baseline, base = core.published_baseline(meta['baseCommit'])
    records = load(bundle / 'records.json')['records']
    lock, dossier, excluded = load(bundle / 'evidence-lock.json'), load(bundle / 'dossier.json'), load(bundle / 'excluded.json')
    batches = [load(p) for p in sorted((bundle / 'batches').glob('*.json'))]
    sources = core.validate_evidence_lock(lock, records)
    core.check_receipt(load(bundle / 'original-verification.json') if (bundle / 'original-verification.json').exists() else {},
                       lock)
    candidate = core.build_candidate(base, records, version)
    result = core.gate(base, candidate, records, batches, dossier, sources)
    dump(bundle / 'proposed-data.json', candidate)
    dump(bundle / 'coverage.json', result['coverage'])
    manifest = core.manifest_for(bundle, meta, baseline, candidate, records, lock, batches, dossier, excluded, result['coverage'])
    dump(bundle / 'manifest.json', manifest)
    (bundle / 'approval-text.txt').write_text(core.approval_text(manifest) + '\n')
    stale = bundle / 'approval.json'
    if stale.exists():
        stale.unlink()  # any rebuild voids an earlier approval
    return manifest, result


def record_approval(version, url, reader=None):
    bundle = bundle_dir(version)
    manifest = load(bundle / 'manifest.json')
    core.validate_bundle(bundle, reader=reader, require_approval=False)
    text = core.approval_text(manifest)
    comment = core.read_owner_comment(url, text, reader)
    record = {'format': core.FORMAT, 'batchId': manifest['batchId'], 'manifestSha256': sha(manifest),
              'approvalTextSha256': sha_bytes(text.encode()), 'comment': comment,
              'recordedAt': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
              'meaning': ('The Owner posted this exact text, binding the listed records and hashes. This is not a GitHub review '
                          'or signature and does not claim the Owner read every original. Merging the data PR is a separate '
                          'Owner decision.')}
    dump(bundle / 'approval.json', record)
    return record


def submit(version, create_pr=True):
    bundle = bundle_dir(version)
    proof = core.validate_bundle(bundle)
    m = proof['manifest']
    candidate = load(bundle / 'proposed-data.json')
    require(core.git('rev-parse', 'HEAD') == m['baseCommit'] or subprocess.run(
        ['git', 'merge-base', '--is-ancestor', m['baseCommit'], 'HEAD'], cwd=ROOT).returncode == 0, 'HEAD is not on the base')
    prefix = str(bundle.relative_to(ROOT)) + '/'
    dirty = [line[3:] for line in core.git('status', '--porcelain', '--untracked-files=all').splitlines()]
    require(all(path.startswith(prefix) for path in dirty), 'Only this batch bundle may be uncommitted when submitting')
    branch = 'data/human-' + m['batchId']
    core.git('checkout', '-q', '-b', branch)
    text = json.dumps(candidate, ensure_ascii=False, indent=2) + '\n'
    (ROOT / 'data/airports.json').write_text(text)
    snapshot = ROOT / ('test/curated-%s.json' % version)
    require(not snapshot.exists(), 'Immutable snapshot already exists')
    snapshot.write_text(text)
    package = load(ROOT / 'package.json')
    package['version'] = version
    (ROOT / 'package.json').write_text(json.dumps(package, indent=2, ensure_ascii=False) + '\n')
    workflows = ROOT / '.github/workflows'
    for name in core.LEGACY_WORKFLOWS:
        if (workflows / name).exists():
            (workflows / name).unlink()  # their exact steps run inside the human-v1 router (frozen + current)
    require((workflows / 'human-admission.yml').read_bytes() == (ROOT / 'admission/human-v1/release-ci.yml').read_bytes(),
            'Human-v1 CI workflow differs from its template')
    core.git('add', '-A')
    for var in ('GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT'):
        ident = core.git('var', var)
        require(ident.startswith('keepraw <49091395+keepraw@users.noreply.github.com>'), 'Wrong commit identity: ' + ident)
    core.git('commit', '-q', '-m', 'data: admit owner-approved human batch %s (%s)' % (m['batchId'], version))
    print('Committed %s on %s. Push and open a draft PR; merge stays with the Owner.' % (version, branch))
    return branch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare', help='Prepare one exact batch from a research spec')
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--base-commit')
    for name, helptext in (('verify-originals', 'Acquire and verify every original'), ('build', 'Build candidate and review files'),
                           ('approval-text', 'Print the exact Owner approval text'), ('validate', 'Re-run every check'),
                           ('submit', 'Create the formal data commit on a new branch')):
        s = sub.add_parser(name, help=helptext)
        s.add_argument('--version', required=True)
    r = sub.add_parser('record-approval', help='Read and verify the real Owner comment')
    r.add_argument('--version', required=True)
    r.add_argument('--url', required=True)
    sub.add_parser('ci', help='CI entry point')
    sub.add_parser('executor', help='Print the executor fingerprint')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            print('Prepared', prepare(args.spec, args.base_commit).relative_to(ROOT))
        elif args.command == 'verify-originals':
            receipt = verify_originals(args.version)
            print('Verified %d originals live; receipt written.' % len(receipt['sources']))
        elif args.command == 'build':
            manifest, result = build(args.version)
            print(json.dumps({'manifestSha256': sha(manifest), 'counts': manifest['counts'], 'coverage': result['coverage']}, indent=2))
        elif args.command == 'approval-text':
            print(core.approval_text(load(bundle_dir(args.version) / 'manifest.json')))
        elif args.command == 'record-approval':
            print(json.dumps(record_approval(args.version, args.url)['comment'], indent=2))
        elif args.command == 'validate':
            proof = core.validate_bundle(bundle_dir(args.version))
            print(json.dumps({'batchId': proof['manifest']['batchId'], 'coverage': proof['gate']['coverage'],
                              'approval': proof['approval'], 'originals': proof['originals']}, indent=2))
        elif args.command == 'submit':
            submit(args.version)
        elif args.command == 'ci':
            core.ci()
        elif args.command == 'executor':
            print(json.dumps(core.executor(), indent=2))
    except AdmissionError as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
