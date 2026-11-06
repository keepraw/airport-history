"""Offline integrity of batch 6 research; receipt checks do not reacquire originals."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'research/evidence/priority-market-batch-6'
ORDER = ['中国', '韩国', '日本', '美国', '欧洲']


def read(name):
    return json.loads((SNAPSHOT / name).read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class PriorityMarketBatch6(unittest.TestCase):
    def test_existing_units_are_not_double_counted_as_new_research(self):
        backlog = read('backlog.json')
        cases = {c['caseId']: c for c in backlog['cases']}
        self.assertEqual(len(cases), len(backlog['cases']))
        self.assertEqual(backlog['marketOrder'], ORDER)
        crosswalk = read('unit-crosswalk.json')
        self.assertEqual(len(crosswalk), 60)
        self.assertEqual(len({c['originalUnit'] for c in crosswalk}), 60)
        self.assertTrue(all(c['canonicalCaseId'] in cases for c in crosswalk))
        mapping = {c['originalUnit']: c['canonicalCaseId'] for c in crosswalk}
        self.assertEqual(mapping['chubu'], mapping['komaki'])
        self.assertEqual(backlog['summary']['priorDeduplicatedCases'], 66)
        self.assertEqual(len(read('priority-code-reuse-leads.json')), 127)
        self.assertTrue(all(not c['countAsFormalData'] for c in read('priority-code-reuse-leads.json')))

    def test_research_packages_preserve_priority_without_review_requests(self):
        cases = {c['caseId']: c for c in read('backlog.json')['cases']}
        seen = []
        priorities = []
        for batch in read('research-batches.json'):
            self.assertTrue(batch['preparationOnly'])
            self.assertFalse(batch['readyToAdmit'])
            self.assertEqual(batch['eventCount'], len(batch['caseIds']))
            self.assertLessEqual(batch['eventCount'], 20)
            self.assertEqual(batch['marketOrder'], ORDER.index(batch['market']) + 1)
            self.assertTrue(all(cases[c]['market'] == batch['market'] for c in batch['caseIds']))
            priorities.append(batch['marketOrder'])
            seen.extend(batch['caseIds'])
        self.assertEqual(priorities, sorted(priorities))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), set(cases))

    def test_new_source_receipts_and_minimal_citations_are_bound(self):
        lock = read('source-lock.json')
        sources = {s['sourceId']: s for s in lock['sources']}
        self.assertEqual(len(sources), len(lock['sources']))
        self.assertEqual(lock['marketOrder'], ORDER)
        receipts = read('original-verification.json')
        self.assertEqual(receipts['mode'], 'actual-local-original-replay')
        self.assertIn('no claim', receipts['offlineCiMeaning'])
        for receipt in receipts['sources']:
            source = sources[receipt['sourceId']]
            self.assertTrue(source['originalBytesReadHere'])
            for field in ('originalSha256', 'extractedTextSha256', 'normalizedTextSha256'):
                self.assertRegex(source[field], r'^[0-9a-f]{64}$')
                self.assertEqual(receipt[field], source[field])
            self.assertEqual(receipt['citationsBound'], len(source['citations']))
            self.assertEqual(receipt['automatedTextCitationsReplayed'] + receipt['visualCitationsBoundToInspectedPage'] + receipt['decodedHtmlAttributeCitationsReplayed'],
                             len(source['citations']))
        for source in sources.values():
            self.assertIn(source['market'], ORDER)
            self.assertFalse(source['productionEligible'])
            for citation in source.get('citations', []):
                self.assertLessEqual(len(citation['quote']), 240)
                self.assertGreater(len(citation['quote']), 0)
                self.assertEqual(citation['characterEnd'] - citation['characterStart'], len(citation['quote']))
                self.assertEqual(citation['quoteSha256'], digest(citation['quote'].encode()))

    def test_prior_provenance_inputs_and_published_records_are_unchanged(self):
        lock = read('input-lock.json')
        for name, expected in lock['files'].items():
            value = expected['sha256'] if isinstance(expected, dict) else expected
            current_path = ROOT / name
            raw = current_path.read_bytes() if current_path.exists() else b''
            if digest(raw) != value:
                # Research provenance belongs to its historical commit. A later
                # data/reference update must not be forced to equal this snapshot.
                raw = subprocess.check_output(['git', 'show', lock['baseCommit'] + ':' + name], cwd=ROOT)
            self.assertEqual(digest(raw), value, name)
        frozen = (ROOT / 'test/curated-0.10.0.json').read_bytes()
        self.assertEqual(digest(frozen), lock['files']['data/airports.json']['sha256'])
        data = json.loads(frozen)
        self.assertEqual([len(data[k]) for k in ('airports', 'assignments', 'sources', 'names')], [37, 52, 101, 3])
        current = json.loads((ROOT / 'data/airports.json').read_text())
        for collection, field in (('airports', 'airportId'), ('assignments', 'assignmentId'), ('sources', 'sourceId'), ('names', 'nameId')):
            actual = {r[field]: r for r in current[collection]}
            self.assertTrue(all(actual.get(r[field]) == r for r in data[collection]))

    def test_unpublished_identity_candidate_does_not_claim_code_admission(self):
        audit = read('identity-candidate/audit.json')
        self.assertEqual(audit['status'], 'UNPUBLISHED_IDENTITY_CANDIDATE_ONLY')
        self.assertFalse(audit['completeReleaseBundle'])
        self.assertFalse(audit['productionValidationPassed'])
        self.assertEqual(audit['candidateAirportIdsAdded'], 2)
        self.assertEqual(audit['candidateAssignmentsAdded'], 0)
        self.assertEqual(audit['newPublishedAirportIds'], 0)
        candidate = read('identity-candidate/proposed-data.json')
        base = json.loads((ROOT / 'test/curated-0.10.0.json').read_text())
        self.assertEqual(candidate['assignments'], base['assignments'])
        self.assertEqual(candidate['names'], base['names'])
        self.assertEqual(candidate['airports'][:len(base['airports'])], base['airports'])
        self.assertEqual(len(candidate['airports']) - len(base['airports']), 2)
        canonical = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(audit['candidateSha256'], digest(canonical))

    def test_project_source_rule_suggestions_do_not_inherit_authority(self):
        proposal = read('source-rule-proposal.json')
        self.assertEqual(proposal['status'], 'proposal-only')
        self.assertIsNone(proposal['authorization'])
        self.assertFalse(proposal['productionBound'])
        self.assertEqual([p['market'] for p in proposal['profiles']], ORDER)
        self.assertTrue(all(p['authorization'] is None for p in proposal['profiles']))


if __name__ == '__main__':
    unittest.main()
