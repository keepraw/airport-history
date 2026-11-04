"""Run every test/evidence test except the two that pin the frozen 0.10.0 bytes.

Those two run unchanged in the frozen published tree (see core.DATA_PINNED).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN_ONLY = {
    'test_kr_admission.KoreanAdmissionTests',
    'test_korea_readiness.KoreaReadinessTests.test_corpus_receipt_replays_offline_without_claiming_fresh_sources',
}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'test/evidence'), top_level_dir=str(ROOT / 'test/evidence'))
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
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
    print('Frozen-tree-only (replayed there unchanged): ' + ', '.join(sorted(skipped)))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
