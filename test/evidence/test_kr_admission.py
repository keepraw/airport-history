"""Independent Korean authority, custody, date and real resolver regressions."""
from copy import deepcopy
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/admission'))
import kr_adapter as a
import kr_evidence as e
from kr_rehearsal import rehearse


def notice(number='A0001/25', kind='N', target='', end='2505010000', estimated=False, start='2504180000'):
    body = f'({number} NOTAM{kind} {target}\nQ)RKRR/QMXLC/IV/BO/A/000/999/3728N12626E005\nA)RKSI B){start}'
    if end:
        body += f' C){end}' + (' EST' if estimated else '')
    body += '\nE)TWY CLOSED)'
    return e.research.metadata({'NOTAM_NO': number, 'FULL_TEXT': body, 'SEQ': number,
        'LOCATION': 'RKSI', 'QCODE': 'QMXLC', 'ISSUE_TIME': '2504171300',
        'EFFECTIVESTART': start, 'EFFECTIVEEND': end, 'ECODE': 'TWY CLOSED'}, 'test-only', 0)


class KoreanAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = a.policy()
        cls.timeline = e.load(e.PACKET / 'aip-timeline.json')
        cls.result = e.evaluate(cls.p)

    def test_offline_recomputes_54_without_claiming_originals_or_authority(self):
        self.assertEqual(27, self.result['daysPerAirport'])
        self.assertEqual([51, 34], [r['counts']['overlap'] for r in self.result['candidates']])
        self.assertFalse(self.result['originalBytesReadHere'])
        self.assertFalse(self.result['freshNetworkAcquisition'])
        self.assertFalse(self.result['archiveCompleteSince2001'])

    def test_research_authorization_remains_null(self):
        self.assertIsNone(e.load(e.PACKET / 'policy.json')['authorization'])
        self.assertIsNone(e.load(e.PACKET / 'identity-batch.json')['authorization'])
        self.assertIsNone(e.load(e.PACKET / 'authorization-proposal.json')['productionAuthorizationText'])

    def test_unknown_or_indian_policy_never_selects_korean_authority(self):
        for key in ('kr-molit-bounded-icao', 'kr-molit-bounded-icao@0.2.0-draft',
                    'official-aip-bounded-icao@1.0.0', a.KEY + ' '):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'default deny'):
                a.policy(key)

    def test_iata_or_expanded_country_semantics_reject(self):
        real = a.load
        for field, value in [('namespace', 'IATA'), ('country', 'JP'), ('newPhysicalIdentities', True),
                             ('publishedCorrections', True), ('newIataAssignments', True)]:
            p = deepcopy(self.p)
            p['scope'][field] = value
            with self.subTest(field=field), patch.object(a, 'load', side_effect=lambda path: p if path.name == 'policy.json' else real(path)), self.assertRaises(ValueError):
                a.policy()

    def test_exact_bindings_and_all_executable_dependencies(self):
        bound = a.checked_bindings(self.p)
        self.assertNotEqual(bound['executorSha256'], 'cab2f8c5a97a8c1db6915f1cff0c48563b199dbbbbd582e19a9f43a0b9a8d2ae')
        self.assertNotEqual(bound['executorSha256'], '2415279526ff8c0eaf9ee1b3ee5afca8bde26e95bfac2c98930212f9f7992a3f')
        manifest = a.fingerprint()
        for p in ('scripts/reference/admissions.py', 'src/resolve.ts', 'src/evidence.ts',
                  'src/validate.ts', 'schema/dataset.schema.json', 'pnpm-lock.yaml',
                  'scripts/admission/kr_evidence.py', 'scripts/evidence/korea_readiness.py'):
            self.assertIn(p, manifest['files'])
        self.assertIn('package.json', manifest['canonicalJsonInputs'])

    def test_every_bound_dependency_change_invalidates_executor(self):
        original = a.fingerprint()
        with tempfile.TemporaryDirectory(dir=a.ROOT / 'work') as tmp:
            root = Path(tmp)
            for name in [*original['files'], 'package.json']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(a.ROOT / name, target)
            with patch.object(a, 'ROOT', root):
                self.assertEqual(original, a.fingerprint())
                for name in original['files']:
                    target = root / name
                    raw = target.read_bytes()
                    target.write_bytes(raw + b'\n')
                    self.assertNotEqual(original['executorSha256'], a.fingerprint()['executorSha256'], name)
                    target.write_bytes(raw)
                p = a.load(root / 'package.json')
                p['scripts']['build'] += ' altered'
                a.write(root / 'package.json', p)
                self.assertNotEqual(original['executorSha256'], a.fingerprint()['executorSha256'])

    def test_policy_and_scope_changes_require_new_authorization(self):
        for mutation in ('version', 'scope', 'gap'):
            p = deepcopy(self.p)
            if mutation == 'version': p['policyKey'] += '-next'
            elif mutation == 'scope': p['scope']['codes'].append('RKPC')
            else: p['maximumAiracGapDays'] = 56
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'changed'):
                a.checked_bindings(p)

    def test_identity_batch_hash_and_no_permanent_id_allocation(self):
        b = a.identity_batch()
        self.assertEqual('1bf46a730f0f1f750e3479bdfe032e653b6b2c63e113aa6eae908bff3948722c', b['batchSha256'])
        self.assertTrue(all(r['proposedPermanentAirportId'] is None for r in b['payload']['records']))
        changed = deepcopy(b)
        changed['payload']['records'][0]['arpDms'] = b['payload']['records'][1]['arpDms']
        real = a.load
        with patch.object(a, 'load', side_effect=lambda p: changed if p.name == 'identity-batch.json' else real(p)), self.assertRaisesRegex(ValueError, 'Invalid identity'):
            a.identity_batch()

    def test_stale_identity_batch_cannot_create_ids_after_formal_data_change(self):
        data = a.load(a.ROOT / 'test/curated-0.10.0.json')
        a.identity_baseline(a.identity_batch(), data)
        data['airports'].append(deepcopy(data['airports'][0]))
        with self.assertRaisesRegex(ValueError, 'renew physical-site competition'):
            a.identity_baseline(a.identity_batch(), data)

    def test_no_identity_approval_rejects_before_output(self):
        with tempfile.TemporaryDirectory(dir=a.ROOT / 'work') as tmp:
            path = Path(tmp) / 'must-not-exist'
            with self.assertRaisesRegex(ValueError, 'permanent identities missing'):
                a.prepare(self.p, path, '0.10.1')
            self.assertFalse(path.exists())

    def test_missing_real_policy_grant_rejects(self):
        with self.assertRaisesRegex(ValueError, 'real Owner policy authorization'):
            a.authorization(self.p, [])

    def test_no_json_approved_boolean_can_supply_authority(self):
        real = a.load
        registry = {'formatVersion': 1, 'authorizations': [{'approved': True, 'policyKey': a.KEY,
                    'bindings': {'executorSha256': 'fabricated'}, 'identitiesSha256': a.sha([])}]}
        with patch.object(a, 'load', side_effect=lambda p: registry if p.name == 'authorizations.json' else real(p)), self.assertRaises(ValueError):
            a.authorization(self.p, [])

    def comment_fixture(self):
        text = a.identity_text()
        url = 'https://github.com/keepraw/airport-history/pull/25#issuecomment-123'
        repo = {'owner': {**a.OWNER, 'type': 'User'}}
        comment = {'html_url': url, 'issue_url': 'https://api.github.com/repos/keepraw/airport-history/issues/25',
                   'user': {**a.OWNER, 'type': 'User'}, 'body': text,
                   'created_at': '2026-10-30T00:00:00Z', 'updated_at': '2026-10-30T00:00:00Z'}
        return text, url, repo, comment

    def test_owner_reader_verifies_actual_api_response(self):
        text, url, repo, comment = self.comment_fixture()
        with patch.object(a, 'github', side_effect=[repo, comment]) as api:
            result = a.read_owner_comment(url, text)
        self.assertEqual(2, api.call_count)
        self.assertEqual(a.OWNER, result['principal'])

    def test_forged_actor_body_repo_url_and_timestamp_reject(self):
        for mutation in ('actor', 'id', 'bot', 'body', 'url', 'issue', 'future', 'repo'):
            text, url, repo, c = self.comment_fixture()
            if mutation == 'actor': c['user']['login'] = 'someone-else'
            elif mutation == 'id': c['user']['id'] = 0
            elif mutation == 'bot': c['user']['type'] = 'Bot'
            elif mutation == 'body': c['body'] += ' Authorize all dates.'
            elif mutation == 'url': c['html_url'] += 'different'
            elif mutation == 'issue': c['issue_url'] += '0'
            elif mutation == 'future': c['updated_at'] = '2099-01-01T00:00:00Z'
            else: repo['owner']['id'] = 0
            with self.subTest(mutation=mutation), patch.object(a, 'github', side_effect=[repo, c]), self.assertRaises(ValueError):
                a.read_owner_comment(url, text)

    def test_identity_scope_is_separate_from_policy(self):
        text, url, repo, c = self.comment_fixture()
        with patch.object(a, 'github', side_effect=[repo, c]), self.assertRaises(ValueError):
            a.read_owner_comment(url, 'Authorize Korean policy ' + a.KEY)

    def test_unpublished_dataset_or_identity_registry_is_rejected(self):
        commit = {'commit': {'sha': 'f' * 40}}
        def encoded(value):
            return {'encoding': 'base64', 'type': 'file', 'content': base64.b64encode(json.dumps(value).encode()).decode()}
        with patch.object(a, 'github', side_effect=[commit, encoded({'published': True})]), self.assertRaisesRegex(ValueError, 'published main dataset'):
            a.require_published({'unmerged': True})
        with patch.object(a, 'github', side_effect=[commit, encoded({'published': True}), encoded({'identities': []})]), self.assertRaisesRegex(ValueError, 'not formally published'):
            a.require_published({'published': True}, {'identities': ['unmerged']})

    def test_arbitrary_comment_hosts_and_test_transports_reject(self):
        for url in ('test-fixture://kr/identity', 'https://github.com/other/airport-history/issues/1#issuecomment-123',
                    'https://github.com/keepraw/airport-history/issues/1#issuecomment-123?scope=all'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                a.read_owner_comment(url, a.identity_text())

    def test_airac_bounds_are_recomputed_and_ordinary_clock_stays_unknown(self):
        self.assertEqual(self.p['scope']['window'], e.window(self.timeline['editions'], 28))
        self.assertIsNone(self.result['ordinaryEffectiveInstantUtc'])
        editions = deepcopy(self.timeline['editions'])
        editions[-1]['effectiveUtc'] = '2025-05-15T16:00:00+00:00'
        with self.assertRaisesRegex(ValueError, 'gap'):
            e.window(editions, 28)

    def test_unknown_amendment_or_invented_ordinary_clock_rejects(self):
        for field, value in [('kind', 'unknown'), ('effectiveInstantUtc', '2025-05-01T16:00:00Z'),
                             ('ad21Or22Replaced', True), ('effectiveOn', '2025-05-02')]:
            editions = deepcopy(self.timeline['editions'])
            editions[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                e.window(editions, 28)

    def test_unknown_perm_and_est_are_fail_closed(self):
        for r in (notice(end='PERM'), notice(estimated=True)):
            with self.assertRaisesRegex(ValueError, 'Unresolved'):
                e.notice_checks([r], e.research.START, e.research.END)

    def test_replacement_missing_predecessor_rejects(self):
        with self.assertRaisesRegex(ValueError, 'predecessor'):
            e.notice_checks([notice(kind='R', target='A9999/24')], e.research.START, e.research.END)

    def test_different_original_bytes_for_same_number_reject(self):
        r = notice()
        other = deepcopy(r)
        other['fullTextSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'different original bytes'):
            e.notice_checks([r, other], e.research.START, e.research.END)

    def test_equal_bytes_duplicate_does_not_merge_away_records(self):
        r = notice()
        other = deepcopy(r)
        other['serverRecordId'] = 'another-server-row'
        self.assertEqual(2, e.notice_checks([r, other], e.research.START, e.research.END)['overlap'])

    def test_missing_multipart_rejects(self):
        with self.assertRaisesRegex(ValueError, 'multipart'):
            e.notice_checks([notice('A0001/25A02')], e.research.START, e.research.END)

    def test_complete_multipart_can_replay(self):
        self.assertEqual(2, e.notice_checks([notice('A0001/25A02'), notice('A0001/25B02')],
                                          e.research.START, e.research.END)['overlap'])

    def test_raw_text_date_code_and_location_conflicts_reject(self):
        item = {'NOTAM_NO': 'A0001/25', 'FULL_TEXT': '(A0001/25 NOTAMN\nQ)RKRR/QMXLC/IV/BO/A/000/999/3728N12626E005\nA)RKSI B)2504180000 C)2505010000\nE)TWY CLOSED)',
                'EFFECTIVESTART': '2504180000', 'EFFECTIVEEND': '2505010000', 'QCODE': 'QMXLC',
                'LOCATION': 'RKSI', 'ECODE': 'TWY CLOSED'}
        e.original_notice(item)
        multipart = {**item, 'NOTAM_NO': 'A0001/25A02',
                     'FULL_TEXT': item['FULL_TEXT'].replace('A0001/25 NOTAM', 'A0001/25A02 NOTAM')}
        e.original_notice(multipart)
        for field, value in [('EFFECTIVESTART', '2504190000'), ('EFFECTIVEEND', 'PERM'),
                             ('QCODE', 'QFALC'), ('LOCATION', 'RKSS'), ('ECODE', 'ICAO CODE WITHDRAWN')]:
            changed = {**item, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                e.original_notice(changed)

    def test_duplicate_fir_number_with_different_raw_bytes_rejects(self):
        r = notice()
        other = deepcopy(r)
        other['fullTextSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'duplicate FIR'):
            e.duplicate_bytes([r, other])

    def test_whole_airport_closure_is_not_partial_taxiway_closure(self):
        r = notice()
        self.assertEqual(1, e.notice_checks([r], e.research.START, e.research.END)['overlap'])
        r['qcode'] = 'QFALC'
        with self.assertRaisesRegex(ValueError, 'whole-airport'):
            e.notice_checks([r], e.research.START, e.research.END)

    def test_identity_change_signal_rejects(self):
        r = notice()
        r['identityChangeSignal'] = True
        with self.assertRaises(ValueError):
            e.notice_checks([r], e.research.START, e.research.END)

    def test_wrong_hash_or_missing_original_never_uses_offline_boolean(self):
        with patch.object(e.research, 'source_bytes', side_effect=ValueError('Missing original')):
            with self.assertRaisesRegex(ValueError, 'Missing original'):
                e.evaluate(self.p, originals=True)
        p = deepcopy(self.p)
        first = next(iter(p['evidenceFiles']))
        p['evidenceFiles'][first] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            e.evaluate(p)

    def test_detached_checklist_truncation_and_unknown_fir_are_rejected(self):
        real = e.load
        for filename, mutate in [
            ('notam-RKSI.json', lambda v: v.update(serverTotal=v['returnedRows']+1)),
            ('fir-screening.json', lambda v: v['segments'][0].update(returned=0)),
            ('checklist-reconciliation.json', lambda v: v['checklists'].pop()),
            ('publication-crosscheck.json', lambda v: v['supplementOriginals'][0].update(codeOrArpChangeEstablished=True))]:
            changed = deepcopy(real(e.PACKET / filename))
            mutate(changed)
            with self.subTest(filename=filename), patch.object(e, 'load', side_effect=lambda path: changed if path.name == filename else real(path)), self.assertRaises(ValueError):
                e.evaluate(self.p)

    def test_no_formal_output_paths(self):
        for path in (a.ROOT / 'data/proposal', a.ROOT / 'research/proposal', a.ROOT / 'work'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                a.new_output(path)

    def test_real_isolated_identity_admission_and_korean_policy_pipeline(self):
        report = rehearse()
        self.assertEqual(54, report['conditionalResolved'])
        self.assertEqual(37736, report['formalRegressionQueries'])
        self.assertEqual(0, report['boundaryExtraResolved'])
        self.assertTrue(report['productionRejectedTestAuthority'])
        self.assertTrue(report['realFilesUnchanged'])
        self.assertFalse(report['originalBytesReadHere'])
        self.assertEqual(9, len(report['isolatedNegativeChecks']))


if __name__ == '__main__':
    unittest.main()
