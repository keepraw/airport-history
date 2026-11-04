"""Full Human v1 release-CI route on a fictional 0.11.0-style release (not a unittest module).

Builds the fictional three-country batch of test_human_admission.py in a disposable
clone whose origin is a local bare repository standing in for GitHub main,
submits it, forms the merge GitHub would check, and then runs the real CLI entry
``human.py ci`` (``human.main(['ci'])``) end to end: live-style Owner comment read
(an in-process simulator injected here only; the production CLI has no switch),
original-receipt replay, release lineage, the complete frozen legacy CI and every
current-tree check, all executed for real.

Scenarios:
  pull_request  origin/main is still the approved base; HEAD is the test merge.
  push          origin/main is the merge itself (after the Owner merged).

Writes a JSON report with every executed command, its working tree, exit code and
duration. Nothing here touches the real repository or GitHub.
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('human_admission_fixture', HERE / 'test_human_admission.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', choices=('pull_request', 'push'), required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    env = types.SimpleNamespace()
    fixture.make_env(env)  # prepare -> verify-originals -> build -> approval -> record-approval
    core, cli, root = env.core, env.cli, env.root
    version = fixture.ns['version']
    original_github = core.github
    core.github = fixture.FakeGitHub(env.text)
    try:
        cli.submit(version)
    finally:
        core.github = original_github
    data = fixture.git(root, 'rev-parse', 'HEAD')
    tree = fixture.git(root, 'rev-parse', data + '^{tree}')
    merge = fixture.git(root, 'commit-tree', tree, '-p', env.base, '-p', data, '-m', 'Merge synthetic data PR')
    fixture.set_main(env, env.base if args.scenario == 'pull_request' else merge)
    subprocess.run(['git', 'checkout', '-q', '--detach', merge], cwd=root, check=True)

    executed = []
    real_run = core.run_all

    def logged_run_all(commands, cwd):
        for command in commands:
            started = time.time()
            print('::group::[%s] %s' % ('current' if Path(cwd) == root else 'frozen', command), flush=True)
            result = subprocess.run(command, shell=True, cwd=cwd)
            print('::endgroup::', flush=True)
            executed.append({'tree': 'current' if Path(cwd) == root else 'frozen', 'cwd': str(cwd), 'command': command,
                             'exitCode': result.returncode, 'seconds': round(time.time() - started, 1)})
            args.report.write_text(json.dumps(report(), indent=2))
            if result.returncode:
                raise subprocess.CalledProcessError(result.returncode, command)

    def report(status='running', error=None):
        frozen = [e['command'] for e in executed if e['tree'] == 'frozen']
        current = [e['command'] for e in executed if e['tree'] == 'current']
        return {'scenario': args.scenario, 'status': status, 'error': error, 'base': env.base, 'dataCommit': data,
                'head': merge, 'origin_main': fixture.git(root, 'rev-parse', 'origin/main'),
                'dataVersion': json.loads((root / 'data/airports.json').read_text())['dataVersion'],
                'executed': executed,
                'routing': {
                    'frozenEqualsLegacy': sorted(frozen) == sorted(core.LEGACY_CURRENT_COMMANDS),
                    'pinnedRanFrozen': sorted(p for p in core.DATA_PINNED if p in frozen),
                    'pinnedRanCurrent': sorted(p for p in core.DATA_PINNED if p in current),
                    'legacyMissing': sorted(c for c in set(core.LEGACY_CURRENT_COMMANDS) if c not in frozen),
                    'currentExpected': [x for c in dict.fromkeys(core.LEGACY_CURRENT_COMMANDS)
                                        for x in core.CURRENT_REPLACEMENTS.get(c, [] if c in core.DATA_PINNED else [c])],
                    'currentRan': current}}

    core.run_all = logged_run_all
    core.github = fixture.FakeGitHub(env.text)  # in-process Owner comment simulator for the fictional batch only
    error = None
    try:
        exit_code = cli.main(['ci'])
    except subprocess.CalledProcessError as failure:
        exit_code, error = 1, 'command failed: %s (exit %s)' % (failure.cmd, failure.returncode)
    final = report('passed' if exit_code == 0 else 'failed', error or (None if exit_code == 0 else 'human.py ci exit %d' % exit_code))
    r = final['routing']
    ok = (exit_code == 0 and r['frozenEqualsLegacy'] and not r['legacyMissing'] and not r['pinnedRanCurrent'] and
          sorted(r['pinnedRanFrozen']) == sorted(core.DATA_PINNED) and r['currentRan'] == r['currentExpected'])
    final['status'] = 'passed' if ok else 'failed'
    args.report.write_text(json.dumps(final, indent=2))
    print(json.dumps({k: final[k] for k in ('scenario', 'status', 'base', 'head', 'origin_main', 'dataVersion')}, indent=2))
    print(json.dumps(r, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
