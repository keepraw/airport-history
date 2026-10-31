"""One batched candidate PR under a main lease; no merge/tag/release operation."""
import argparse
import io
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile

from runtime import ROOT, PUBLIC, PRIVATE, load, require, sha, write, private_path, policy
from release import validate
import release


def plan(bundle, output):
    bundle = Path(bundle)
    release.published_checkout(load(bundle / 'receipt.json')['baselineCommit'])
    proof = validate(bundle)  # Fresh raw replay and live Owner authentication, always.
    require(proof['productionValidationPassed'] and load(bundle / 'receipt.json')['originalBytesReadHere'],
            'Full original replay required before PR preparation')
    output = private_path(output, new=True)
    receipt = load(bundle / 'receipt.json')
    candidate = load(bundle / 'proposed-data.json')
    prefix = 'research/admissions/' + candidate['dataVersion'] + '/rule-v1'
    changes = {'data/airports.json': candidate, 'research/admission/rule-v1/identities.json': load(bundle / 'identities.json')}
    for file in sorted(bundle.glob('*.json')):
        changes[prefix + '/' + file.name] = load(file)
    package = load(ROOT / 'package.json')
    package['version'] = candidate['dataVersion']
    changes['package.json'] = package
    sites = sorted(r['siteKey'] for r in load(bundle / 'identities.json')['identities'])
    key = sha([sites, [p['policyKey'] for p in receipt['policies']]])[:24]
    result = {'formatVersion': 1, 'baselineCommit': receipt['baselineCommit'], 'branch': 'data/rule-admission-' + key,
        'title': 'data: admit a rule-reviewed Korean airport batch', 'changesSha256': sha(changes),
        'bundleSha256': sha(receipt), 'candidateSha256': proof['candidateSha256'],
        'humanMergeRequired': True, 'autoMerge': False, 'exceptions': load(bundle / 'exceptions.json'),
        'productionOriginalReplayPassed': True, 'simulation': False}
    write(output / 'changes.json', changes)
    write(output / 'plan.json', result)
    # These workflow updates are future candidate changes, not edits to any
    # frozen executor. Their exact template is part of the new executor binding.
    shutil.copy2(ROOT / 'admission/v1/release-ci.yml', output / 'ci.yml')
    return result



def audit_candidate_rights(checkout):
    """Use frozen research metadata while auditing the candidate's real Git index.

    The legacy rights command also checks its 0.10.0 working-tree baseline.
    Keep that metadata check intact; its Git reads must still inspect the new
    candidate's complete ancestry and staged bytes, never the baseline index.
    """
    checkout = Path(checkout).resolve()
    git_dir = Path(subprocess.check_output(
        ['git', 'rev-parse', '--absolute-git-dir'], cwd=checkout, text=True).strip())
    commit = policy('kr-code')['requirements']['frozenLegacyCommit']
    archive = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='rights-baseline-', dir=ROOT / 'work') as tmp:
        frozen = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(frozen, filter='data')
        env = {**os.environ, 'GIT_DIR': str(git_dir), 'GIT_WORK_TREE': str(frozen),
               'GIT_INDEX_FILE': str(git_dir / 'index')}
        return json.loads(subprocess.check_output(
            ['python3', 'scripts/evidence/korea_readiness.py', 'rights'],
            cwd=frozen, env=env, text=True))


def submit(bundle, output):
    prepared = plan(bundle, output)
    require(subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/main'], cwd=ROOT, text=True).split()[0] ==
            prepared['baselineCommit'], 'Published main advanced; regenerate competition review and candidate')
    # Existing review branches are the cross-worker pending identity ledger.
    # Do not mint another PR/ID set when the stable site batch already exists.
    query = subprocess.check_output(['gh', 'pr', 'list', '--repo', 'keepraw/airport-history', '--state', 'open',
        '--head', prepared['branch'], '--json', 'url'], cwd=ROOT, text=True)
    existing = json.loads(query)
    if existing:
        return {'existingPullRequest': existing[0]['url'], 'newPullRequests': 0, 'mainUnchanged': True}
    existing_ref = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/' + prepared['branch']], cwd=ROOT, text=True)
    require(not existing_ref.strip(), 'Pending identity branch already exists; inspect/reuse its registry before regeneration')
    with tempfile.TemporaryDirectory(prefix='pr-submit-', dir=ROOT / 'work') as tmp:
        checkout = Path(tmp) / 'repo'
        subprocess.run(['git', 'clone', '--quiet', '--shared', str(ROOT), str(checkout)], check=True)
        subprocess.run(['git', 'switch', '--detach', prepared['baselineCommit']], cwd=checkout, check=True)
        subprocess.run(['git', 'switch', '-c', prepared['branch']], cwd=checkout, check=True)
        # Copy this independently reviewed engine/policy runtime from the current
        # main checkout. A future batch may not smuggle unreviewed engine edits.
        require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() ==
                prepared['baselineCommit'], 'Production submit requires the exact published main checkout')
        for path, value in load(Path(output) / 'changes.json').items():
            write(checkout / path, value)
        for name in ('ci.yml', 'kr-admission.yml', 'rule-admission.yml'):
            shutil.copy2(Path(output) / 'ci.yml', checkout / '.github/workflows' / name)
        for key, value in [('user.name', 'keepraw'), ('user.email', '49091395+keepraw@users.noreply.github.com'), ('user.useConfigOnly', 'true')]:
            subprocess.run(['git', 'config', '--local', key, value], cwd=checkout, check=True)
        for kind in ('GIT_AUTHOR_IDENT', 'GIT_COMMITTER_IDENT'):
            ident = subprocess.check_output(['git', 'var', kind], cwd=checkout, text=True)
            require(ident.startswith('keepraw <49091395+keepraw@users.noreply.github.com> '), 'Wrong commit identity')
        subprocess.run(['git', 'add', 'data', 'package.json', 'research/admissions', 'research/admission/rule-v1/identities.json', '.github/workflows'], cwd=checkout, check=True)
        print(json.dumps(audit_candidate_rights(checkout), sort_keys=True))
        subprocess.run(['python3', 'admission/v1/release_ci.py'], cwd=checkout, check=True)
        subprocess.run(['git', 'commit', '-m', prepared['title']], cwd=checkout, check=True)
        ident = subprocess.check_output(['git', 'log', '-1', '--format=%an <%ae>%n%cn <%ce>'], cwd=checkout, text=True).splitlines()
        require(ident == ['keepraw <49091395+keepraw@users.noreply.github.com>'] * 2, 'Wrong final commit identity')
        subprocess.run(['git', 'remote', 'set-url', 'origin', 'https://github.com/keepraw/airport-history.git'], cwd=checkout, check=True)
        subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/' + prepared['branch']], cwd=checkout, check=True)
        body = Path(tmp) / 'pr-body.md'
        body.write_text('Admit the batch reviewed by independent physical identity and bounded Korean ICAO rules.\n\n'
            'Fresh private-original replay, schema, immutable history and real resolver validation passed. '
            'CI reports its separate offline validation scope. Human merge required.\n\n'
            'Candidate SHA-256: `' + prepared['candidateSha256'] + '`.\n'
            'Exceptions are retained in the versioned bundle; no auto-merge, tags or releases.\n')
        url = subprocess.check_output(['gh', 'pr', 'create', '--repo', 'keepraw/airport-history', '--base', 'main',
            '--head', prepared['branch'], '--title', prepared['title'], '--body-file', str(body)], cwd=checkout, text=True).strip()
        return {'pullRequest': url, 'newPullRequests': 1, 'mainUnchanged': True}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['plan', 'submit'])
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps((plan if args.command == 'plan' else submit)(args.bundle, args.output)))
