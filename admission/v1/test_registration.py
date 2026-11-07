"""Isolated API fixtures; tests never rewrite the real canonical registry."""
import copy
import json
import datetime as dt
import subprocess
import unittest
from unittest.mock import patch

import runtime as r
from verify import registered_authorizations


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.actual = r.load(r.PUBLIC / 'authorizations.json')
        self.registry = copy.deepcopy(self.actual)
        # Current-executor unit fixtures, not claims about real GitHub comments.
        for i, grant in enumerate(self.registry['authorizations'], 1):
            kind = 'identity' if 'physical' in grant['policyKey'] else 'kr-code'
            grant['bindings'] = r.checked_bindings(r.policy(kind))
            grant['approval']['body'] = r.authority_text(r.policy(kind))
            grant['approval']['html_url'] = 'https://github.com/keepraw/airport-history/issues/27#issuecomment-' + str(i)
        self.repo = {'owner': {'login': 'keepraw', 'id': 49091395, 'type': 'User'}}
        self.comments = {}
        for grant in self.registry['authorizations']:
            approval = grant['approval']
            self.comments[approval['html_url'].split('-')[-1]] = {
                'html_url': approval['html_url'],
                'issue_url': 'https://api.github.com/repos/keepraw/airport-history/issues/27',
                'user': {'login': 'keepraw', 'id': 49091395, 'type': 'User'},
                'body': approval['body'], 'created_at': approval['created_at'], 'updated_at': approval['updated_at']}

    def api(self, path):
        if path == 'repos/keepraw/airport-history':
            return self.repo
        return self.comments[path.rsplit('/', 1)[-1]]

    def test_actual_registration_has_only_the_two_requested_comments(self):
        self.assertEqual({r.policy(k)['policyKey'] for k in ('identity', 'kr-code')},
                         {g['policyKey'] for g in self.actual['authorizations']})
        self.assertEqual(2, len(self.actual['authorizations']))
        for grant in self.actual['authorizations']:
            self.assertRegex(grant['approval']['html_url'], r'^https://github.com/keepraw/airport-history/issues/27#issuecomment-[0-9]+$')

    def test_original_signed_registry_cannot_authorize_modified_executor(self):
        original = json.loads(subprocess.check_output(['git', 'show',
            '86b094df59f7654ffd1511bc16186f8a4cc35c9d:research/admission/rule-v1/authorizations.json'], cwd=r.ROOT, text=True))
        with patch.object(r.legacy, 'github') as api, self.assertRaisesRegex(ValueError, 'binding mismatch'):
            registered_authorizations(original)
        api.assert_not_called()

    def test_complete_registry_rechecks_both_api_comments(self):
        before = r.canonical(self.registry)
        with patch.object(r.legacy, 'github', side_effect=self.api) as api:
            self.assertEqual(2, registered_authorizations(self.registry))
        self.assertEqual(4, api.call_count)
        self.assertEqual(before, r.canonical(self.registry))

    def test_prior_empty_registry_is_still_inactive(self):
        with patch.object(r.legacy, 'github') as api:
            self.assertEqual(0, registered_authorizations({'formatVersion': 1, 'authorizations': []}))
        api.assert_not_called()

    def test_partial_duplicate_foreign_or_extra_grants_reject(self):
        cases = []
        partial = copy.deepcopy(self.registry); partial['authorizations'].pop(); cases.append(partial)
        duplicate = copy.deepcopy(self.registry); duplicate['authorizations'][1] = duplicate['authorizations'][0]; cases.append(duplicate)
        foreign = copy.deepcopy(self.registry); foreign['authorizations'][1]['policyKey'] = 'another-rule@1'; cases.append(foreign)
        extra = copy.deepcopy(self.registry); extra['authorizations'].append(extra['authorizations'][0]); cases.append(extra)
        for registry in cases:
            with self.subTest(registry=registry['authorizations'][0]['policyKey']), patch.object(r.legacy, 'github') as api, self.assertRaises(ValueError):
                registered_authorizations(registry)
            api.assert_not_called()

    def test_changed_policy_scope_or_executor_binding_rejects(self):
        for field in ('policySha256', 'scopeSha256', 'executorSha256'):
            registry = copy.deepcopy(self.registry)
            registry['authorizations'][0]['bindings'][field] = '0' * 64
            with self.subTest(field=field), patch.object(r.legacy, 'github') as api, self.assertRaises(ValueError):
                registered_authorizations(registry)
            api.assert_not_called()

    def test_forged_owner_or_issue_body_and_timestamps_reject(self):
        original = copy.deepcopy(self.comments)
        for mutation in ('login', 'id', 'bot', 'repo-owner', 'issue', 'body', 'future', 'reversed', 'edited'):
            self.comments = copy.deepcopy(original)
            self.repo['owner']['id'] = 49091395
            comment = self.comments['1']
            if mutation == 'login': comment['user']['login'] = 'someone-else'
            elif mutation == 'id': comment['user']['id'] = 0
            elif mutation == 'bot': comment['user']['type'] = 'Bot'
            elif mutation == 'repo-owner': self.repo['owner']['id'] = 0
            elif mutation == 'issue': comment['issue_url'] += '0'
            elif mutation == 'body': comment['body'] += ' '
            elif mutation == 'future': comment['updated_at'] = '2099-01-01T00:00:00Z'
            elif mutation == 'reversed': comment['updated_at'] = '2020-01-01T00:00:00Z'
            else:
                changed = dt.datetime.fromisoformat(comment['updated_at'].replace('Z', '+00:00')) + dt.timedelta(seconds=1)
                comment['updated_at'] = changed.strftime('%Y-%m-%dT%H:%M:%SZ')
            with self.subTest(mutation=mutation), patch.object(r.legacy, 'github', side_effect=self.api), self.assertRaises(ValueError):
                registered_authorizations(self.registry)

    def test_stored_approval_cannot_replace_a_live_api_read(self):
        with patch.object(r.legacy, 'github', side_effect=subprocess.CalledProcessError(1, ['gh', 'api'])), self.assertRaises(subprocess.CalledProcessError):
            registered_authorizations(self.registry)

    def test_isolated_test_transport_cannot_be_registered(self):
        registry = copy.deepcopy(self.registry)
        registry['authorizations'][0]['approval']['html_url'] = 'test-fixture://owner/1'
        with patch.object(r.legacy, 'github') as api, self.assertRaises(ValueError):
            registered_authorizations(registry)
        api.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
