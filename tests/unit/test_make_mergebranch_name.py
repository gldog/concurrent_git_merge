import unittest
from datetime import datetime

from src import concurrent_git_merge as main


class Test03(unittest.TestCase):

    def test_valid_placeholders(self):
        repo_metadata = {
            'task_start': datetime.strptime('2023-01-01', '%Y-%m-%d'),
            'source_branch': 'origin/SOURCE-BRANCH',
            'dest_branch': 'DEST-BRANCH'
        }

        merge_branch_template = 'merge/from_{{source_branch.replace("origin/","")}}' \
                                '_into_{{dest_branch}}'
        merge_branch = main.make_mergebranch_name(merge_branch_template, repo_metadata)
        expected_merge_branch = 'merge/from_SOURCE-BRANCH_into_DEST-BRANCH'
        self.assertEqual(expected_merge_branch, merge_branch)

        merge_branch_template = 'merge/from_{{source_branch.replace("origin/","")}}' \
                                '_into_{{dest_branch}}_{{task_start.strftime(("%b%d"))}}'
        merge_branch = main.make_mergebranch_name(merge_branch_template, repo_metadata)
        expected_merge_branch = 'merge/from_SOURCE-BRANCH_into_DEST-BRANCH_Jan01'
        self.assertEqual(expected_merge_branch, merge_branch)
