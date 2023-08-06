import unittest

from src import merge_repos as main


class Test02(unittest.TestCase):

    def test01(self):
        repos_metadata = [
            {'repo_data_from_parameter': 'repo-a', 'repo_local_name': 'repo-a',
             'source_branch': 'source-branch', 'dest_branch': 'dest-branch'}
        ]
        errors = main.validate_repos_metadata(repos_metadata)
        expected = []
        self.assertEqual(expected, errors)

        repos_metadata = [
            {'repo_data_from_parameter': 'repo-a', 'repo_local_name': 'repo-a',
             'source_branch': '', 'dest_branch': 'dest-branch'}
        ]
        errors = main.validate_repos_metadata(repos_metadata)
        expected = ["Missing source-branch in or for repo-data 'repo-a'"]
        self.assertEqual(expected, errors)

        repos_metadata = [
            {'repo_data_from_parameter': 'repo-a', 'repo_local_name': 'repo-a',
             'source_branch': 'source-branch', 'dest_branch': ''}
        ]
        errors = main.validate_repos_metadata(repos_metadata)
        expected = ["Missing dest-branch in or for repo-data 'repo-a'"]
        self.assertEqual(expected, errors)

        repos_metadata = [
            {'repo_data_from_parameter': 'repo-a', 'repo_local_name': 'repo-a',
             'source_branch': '', 'dest_branch': ''}
        ]
        errors = main.validate_repos_metadata(repos_metadata)
        expected = ["Missing source-branch in or for repo-data 'repo-a'",
                    "Missing dest-branch in or for repo-data 'repo-a'"]
        self.assertEqual(expected, errors)
