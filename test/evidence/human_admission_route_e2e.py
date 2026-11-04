"""Full Human v1 release-CI route on a fictional 0.11.0-style release (not a unittest module).

Builds the fictional three-country batch of test_human_admission.py in a disposable
clone whose origin is a local bare repository standing in for GitHub main,
submits it, forms the merge GitHub would check, and then runs the real CLI entry
``human.py ci`` (``human.main(['ci'])``) end to end: live-style Owner comment read
(an in-process simulator injected here only; the production CLI has no switch),
original-receipt replay, release lineage, the complete frozen legacy CI and every
current-tree check, all executed for real.

Scenarios:
  pull_request  origin/main is still the approved base; HEAD is the test merge. The
                complete route runs for real: every frozen and current command executes.
  push          origin/main is the merge itself (after the Owner merged). The same route
                runs with every quick command executed for real and the heavy ones
                (policy:rehearse, the evidence suites) recorded as planned, since the
                pull_request job already executes them on the same trees; then the
                publishing relationships are exercised: squash merge and a later main
                commit accepted, an old PR re-run after main advanced and a merge onto a
                newer main refused, all before any command runs.

Writes a JSON report with every command, its working tree, exit code and duration
(or ``planned``). Nothing here touches the real repository or GitHub.
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
    real_execute = core.execute
    mode = {'run': 'all' if args.scenario == 'pull_request' else 'quick'}  # all | quick | none

    def logged_execute(command, cwd):
        tree = 'current' if Path(cwd) == root else 'frozen'
        started = time.time()
        if mode['run'] == 'none' or (command in core.HEAVY and mode['run'] != 'all'):
            executed.append({'tree': tree, 'cwd': str(cwd), 'command': command, 'exitCode': None, 'planned': True,
                             'seconds': 0})
            print('[route-e2e] planned only: ' + command, flush=True)
            return
        result = subprocess.run(command, shell=True, cwd=cwd)
        executed.append({'tree': tree, 'cwd': str(cwd), 'command': command, 'exitCode': result.returncode,
                         'planned': False, 'seconds': round(time.time() - started, 1)})
        args.report.write_text(json.dumps(report(), indent=2))
        if result.returncode:
            raise subprocess.CalledProcessError(result.returncode, command)

    gates = []

    def report(status='running', error=None):
        frozen = [e['command'] for e in executed if e['tree'] == 'frozen']
        current = [e['command'] for e in executed if e['tree'] == 'current']
        expected_frozen, expected_current = core.route_plan(core.LEGACY_CURRENT_COMMANDS)
        return {'scenario': args.scenario, 'status': status, 'error': error, 'base': env.base, 'dataCommit': data,
                'head': merge, 'origin_main': fixture.git(root, 'rev-parse', 'origin/main'),
                'dataVersion': json.loads((root / 'data/airports.json').read_text())['dataVersion'],
                'executed': executed, 'gates': gates,
                'totals': {'executed': sum(not e['planned'] for e in executed), 'planned': sum(e['planned'] for e in executed),
                           'seconds': round(sum(e['seconds'] for e in executed), 1)},
                'routing': {
                    'frozenExpected': expected_frozen, 'frozenRan': frozen,
                    'currentExpected': expected_current, 'currentRan': current,
                    'pinnedRanCurrent': sorted(p for p in core.DATA_PINNED if p in current),
                    'unpinnedRanFrozen': sorted(c for c in frozen if c in core.LEGACY_CURRENT_COMMANDS and c not in core.DATA_PINNED),
                    'legacyMissing': sorted(
                        c for c in set(core.LEGACY_CURRENT_COMMANDS)
                        if not (set(core.FROZEN_REPLACEMENTS.get(c, [c])) <= set(frozen) if c in core.DATA_PINNED
                                else set(core.CURRENT_REPLACEMENTS.get(c, [c])) <= set(current)))}}

    def ci_at(head, main):
        fixture.set_main(env, main)
        subprocess.run(['git', 'checkout', '-q', '--detach', '--force', head], cwd=root, check=True)
        return cli.main(['ci'])

    def refused_without_commands(name, head, main, message):
        before = len(executed)
        try:
            fixture.set_main(env, main)
            subprocess.run(['git', 'checkout', '-q', '--detach', '--force', head], cwd=root, check=True)
            core.ci()
            outcome = 'not refused'
        except core.AdmissionError as refusal:
            outcome = 'refused' if message in str(refusal) else 'refused for another reason: %s' % refusal
        gates.append({'gate': name, 'expected': 'refused: ' + message, 'outcome': outcome,
                      'commandsRun': len(executed) - before})
        return outcome == 'refused' and len(executed) == before

    core.execute = logged_execute
    core.github = fixture.FakeGitHub(env.text)  # in-process Owner comment simulator for the fictional batch only
    error = None
    try:
        exit_code = ci_at(merge, env.base if args.scenario == 'pull_request' else merge)
    except subprocess.CalledProcessError as failure:
        exit_code, error = 1, 'command failed: %s (exit %s)' % (failure.cmd, failure.returncode)
    final = report('passed' if exit_code == 0 else 'failed', error or (None if exit_code == 0 else 'human.py ci exit %d' % exit_code))
    r = final['routing']
    ok = (exit_code == 0 and not r['legacyMissing'] and not r['pinnedRanCurrent'] and not r['unpinnedRanFrozen'] and
          r['frozenRan'] == [c for c in core.phases(r['frozenExpected'])[0]] + core.phases(r['frozenExpected'])[1] and
          r['currentRan'] == core.phases(r['currentExpected'])[0] + core.phases(r['currentExpected'])[1] and
          all(e['exitCode'] == 0 for e in executed if not e['planned']) and
          (args.scenario == 'push' or not any(e['planned'] for e in executed)))
    route_main = fixture.git(root, 'rev-parse', 'origin/main')
    if ok and args.scenario == 'push':
        mode['run'] = 'none'  # the gates below concern publishing relationships, all decided before any command
        main_route = len(executed)
        tree = fixture.git(root, 'rev-parse', data + '^{tree}')
        squash = fixture.git(root, 'commit-tree', tree, '-p', env.base, '-m', 'Squash synthetic data PR')
        later = fixture.git(root, 'commit-tree', tree, '-p', merge, '-m', 'Later unrelated main commit')
        advanced = fixture.git(root, 'commit-tree', fixture.git(root, 'rev-parse', env.base + '^{tree}'), '-p', env.base,
                               '-m', 'Unrelated main change')
        onto_newer = fixture.git(root, 'commit-tree', tree, '-p', advanced, '-p', data, '-m', 'Merged onto a newer main')
        for name, head, main in (('squash merge published', squash, squash), ('later main commit', later, later)):
            before = len(executed)
            accepted = ci_at(head, main) == 0
            gates.append({'gate': name, 'expected': 'accepted', 'outcome': 'accepted' if accepted else 'refused',
                          'commandsRun': len(executed) - before})
            ok = ok and accepted
        ok = ok and refused_without_commands('old PR re-run after main advanced', merge, advanced, 'Published main advanced')
        ok = ok and refused_without_commands('merge onto a newer main', onto_newer, onto_newer, 'not on its approved base')
    if args.scenario == 'push' and ok:
        del executed[main_route:]  # the accepted gates' own (all planned) routes are summarized in gates
    final = report('passed' if ok else 'failed', final['error'])
    final['origin_main'] = route_main  # the route's own main, not the last gate's
    args.report.write_text(json.dumps(final, indent=2))
    print(json.dumps({k: final[k] for k in ('scenario', 'status', 'base', 'head', 'origin_main', 'dataVersion', 'totals')}, indent=2))
    print(json.dumps({k: v for k, v in final['routing'].items()}, indent=2))
    print(json.dumps(gates, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
