"""Registration must verify live Owner comments without changing signed executors."""
import copy
import datetime as dt
import subprocess
import unittest
from unittest.mock import patch

import runtime as r
from verify import registered_authorizations


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.registry = r.load(r.PUBLIC / 'authorizations.json')
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
        expected = {
            'official-aip-stable-physical-identity@0.1.0-draft': 'https://github.com/keepraw/airport-history/issues/27#issuecomment-6539831536',
            'kr-molit-bounded-icao@2.0.0-draft': 'https://github.com/keepraw/airport-history/issues/27#issuecomment-6539832668'}
        self.assertEqual(expected, {g['policyKey']: g['approval']['html_url'] for g in self.registry['authorizations']})
        self.assertEqual(2, len(self.registry['authorizations']))

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
            comment = self.comments['6539831536']
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
