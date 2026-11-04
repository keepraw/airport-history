"""Split ``pnpm test:evidence`` (python3 -m unittest discover -s test/evidence) between the two trees.

Default (release tree): every test/evidence test except FROZEN_ONLY, which pin the
frozen 0.10.0 bytes. ``--frozen-only`` (run with the frozen published tree as the
working directory): exactly the FROZEN_ONLY tests, unchanged. Together the two
runs cover the whole suite once (see core.DATA_PINNED / FROZEN_REPLACEMENTS).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN_ONLY = {
    'test_kr_admission.KoreanAdmissionTests',
    'test_korea_readiness.KoreaReadinessTests.test_corpus_receipt_replays_offline_without_claiming_fresh_sources',
    # The Global Batch 5 research validator asserts formal data is still exactly 0.10.0.
    'test_global_batch_5.GlobalBatchFiveTests.test_offline_validation_and_resolver_replay',
}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    frozen_only = argv == ['--frozen-only']
    if argv and not frozen_only:
        raise SystemExit('usage: evidence_tests.py [--frozen-only]')
    root = Path.cwd() if frozen_only else ROOT
    suite = unittest.defaultTestLoader.discover(str(root / 'test/evidence'), top_level_dir=str(root / 'test/evidence'))
    tests, skipped = [], []
    for test in flatten(suite):
        name = test.id()
        if any(name == f or name.startswith(f + '.') for f in FROZEN_ONLY):
            skipped.append(name)
        else:
            tests.append(test)
    found = {f for f in FROZEN_ONLY if any(s == f or s.startswith(f + '.') for s in skipped)}
    if found != FROZEN_ONLY:
        raise SystemExit('Frozen-only test list is stale: %s' % sorted(FROZEN_ONLY - found))
    if frozen_only:
        tests, skipped = [t for t in flatten(suite) if t.id() in skipped], tests
        print('Frozen published tree %s: running only the data-pinned tests (%d); the other %d run on the release tree.'
              % (root, len(tests), len(skipped)), flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
    if not frozen_only:
        print('Frozen-tree-only (replayed there unchanged): ' + ', '.join(sorted(skipped)))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
