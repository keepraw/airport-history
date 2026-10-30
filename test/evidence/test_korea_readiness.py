"""Fail-closed regressions for real Korean NOTAM/date counterexamples."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/evidence'))
import korea_readiness as kr


def notice(number='A0001/25', kind='N', target=None, end='2505010000', estimated=False,
           start='2504171400', issued='2504171300', record_id='1'):
    text = f'({number} NOTAM{kind} ' + (target or '') + '\n'
    text += f'Q)RKRR/QMXLC/IV/BO/A/000/999/3728N12626E005\nA)RKSI B){start}'
    if end:
        text += f' C){end}' + ('EST' if estimated else '')
    text += '\nE)TWY CLOSED)'
    item = {'NOTAM_NO': number, 'FULL_TEXT': text, 'SEQ': record_id, 'LOCATION': 'RKSI',
            'QCODE': 'QMXLC', 'ISSUE_TIME': issued, 'EFFECTIVESTART': start,
            'EFFECTIVEEND': end, 'ECODE': 'TWY CLOSED'}
    return kr.metadata(item, 'fixture', 0)


class KoreaReadinessTests(unittest.TestCase):
    def test_package_reformat_preserves_binding_but_changed_values_invalidate_it(self):
        expected = kr.bindings()
        (kr.ROOT / 'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=kr.ROOT / 'work') as tmp:
            root = Path(tmp)
            for name in [*expected['executorFiles'], 'package.json']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(kr.ROOT / name, target)
            base = root / kr.BASE.relative_to(kr.ROOT)
            base.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kr.BASE / 'policy.json', base / 'policy.json')
            with patch.object(kr, 'ROOT', root), patch.object(kr, 'BASE', base):
                package = kr.load(root / 'package.json')
                (root / 'package.json').write_text(json.dumps(package, sort_keys=True, indent=2) + '\n')
                self.assertEqual(expected, kr.bindings())
                package['engines']['node'] = '^25.0.0'
                (root / 'package.json').write_text(json.dumps(package, sort_keys=True, indent=2) + '\n')
                self.assertNotEqual(expected['executorSha256'], kr.bindings()['executorSha256'])

    def test_research_policy_rejects_grants_and_expanded_scope(self):
        original = kr.load(kr.BASE / 'policy.json')
        for field, value in [('authorization', {'owner': 'keepraw'}), ('productionBound', True), ('status', 'authorized')]:
            policy = copy.deepcopy(original)
            policy[field] = value
            with self.assertRaises(ValueError):
                kr.validate_draft(policy)
        for field, value in [('namespace', 'IATA'), ('codes', ['RKSI', 'RKSS', 'RJAA']), ('newPhysicalIdentities', True)]:
            policy = copy.deepcopy(original)
            policy['scope'][field] = value
            with self.assertRaises(ValueError):
                kr.validate_draft(policy)

    def test_perm_and_est_never_expire_without_an_explicit_successor(self):
        for row in [notice(end='PERM'), notice(end='2504171401', estimated=True)]:
            result = kr.lifecycle(row, [row])
            self.assertEqual('unknown_lifecycle', result['disposition'])
            self.assertIsNone(result['effectiveEndUtc'])

    def test_cancellation_is_a_graph_event_not_an_open_ended_restriction(self):
        row = notice(kind='C', target='A9999/24', end=None)
        result = kr.lifecycle(row, [row])
        self.assertEqual('cancellation_event', result['disposition'])
        self.assertTrue(result['missingPredecessor'])
        self.assertFalse(result['codeAllocationChangeEstablished'])

    def test_successor_cannot_retroactively_erase_overlap_before_transmission(self):
        row = notice(end='PERM')
        successor = notice('A0002/25', 'C', 'A0001/25', None,
                           start='2504171400', issued='2504171600', record_id='2')
        self.assertEqual('overlap', kr.lifecycle(row, [row, successor])['disposition'])

    def test_cancellation_before_future_b_excludes_a_never_activated_notice(self):
        row = notice(end='PERM', start='2504180000', issued='2504160000')
        successor = notice('A0002/25', 'C', 'A0001/25', None,
                           start='2504170000', issued='2504170001', record_id='2')
        self.assertEqual('outside_window', kr.lifecycle(row, [row, successor])['disposition'])

    def test_duplicate_number_does_not_collapse_different_text_fingerprints(self):
        a = notice()
        b = copy.deepcopy(a)
        b['serverRecordId'] = '2'
        c = copy.deepcopy(a)
        c['serverRecordId'] = '3'
        c['fullTextSha256'] = 'different'
        self.assertEqual(['1', '2'], kr.lifecycle(a, [a, b, c])['duplicateServerRecordIds'])

    def test_multipart_checklist_uses_base_number_for_successor_relationship(self):
        row = notice('E0001/25A02', end='PERM')
        successor = notice('E0002/25', 'R', 'E0001/25', '2506010000',
                           start='2504010000', issued='2504010001', record_id='2')
        result = kr.lifecycle(row, [row, successor])
        self.assertEqual('outside_window', result['disposition'])
        self.assertEqual(['2'], result['successorServerRecordIds'])

    def test_official_snapshots_and_real_edges_are_not_promoted_to_authority(self):
        checks = kr.load(kr.BASE / 'checklist-reconciliation.json')
        self.assertTrue(checks['boundedAirportReconciliationPassed'])
        self.assertFalse(checks['archiveCompleteSince2001'])
        for c in checks['checklists']:
            self.assertEqual([], c['missingFromChecklist'])
            self.assertEqual([], c['missingFromLedger'])
        timeline = kr.load(kr.BASE / 'aip-timeline.json')
        self.assertIsNone(timeline['editions'][1]['effectiveInstantUtc'])
        self.assertEqual(27, (kr.END - kr.START).days)
        coverage = kr.load(kr.BASE / 'coverage.json')
        self.assertEqual(54, coverage['conditionalResolved'])
        self.assertEqual(0, coverage['gatedResolved'])
        self.assertEqual(0, coverage['formalNewResolved'])

    def test_corpus_receipt_replays_offline_without_claiming_fresh_sources(self):
        # The admission rehearsal mutates only its disposable formal/grant files.
        result = kr.verify(baseline=False)
        self.assertFalse(result['originalBytesObtainedHere'])
        self.assertEqual('no_go', result['productionDecision'])


if __name__ == '__main__':
    unittest.main()
