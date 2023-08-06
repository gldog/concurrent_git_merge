import unittest
from datetime import datetime

from src import merge_repos as main


class Test03(unittest.TestCase):

    def test_valid_placeholders(self):
        main.g_start_timestamp = datetime.strptime('2023-01-01', '%Y-%m-%d')
        source_branch = 'SOURCE-BRANCH'
        dest_branch = 'DEST-BRANCH'
        merge_branch_pattern = 'merge/from_%SBR_into_%DBR_%DATE(%b%d)'
        merge_branch = main.make_mergebranch_name(merge_branch_pattern, source_branch, dest_branch)
        expected_merge_branch = 'merge/from_SOURCE-BRANCH_into_DEST-BRANCH_Jan01'
        self.assertEqual(expected_merge_branch, merge_branch)

        main.g_start_timestamp = datetime.strptime('2023-01-01', '%Y-%m-%d')
        source_branch = 'SOURCE-BRANCH'
        dest_branch = 'DEST-BRANCH'
        merge_branch_pattern = 'merge/from_%SBR_into_%DBR'
        merge_branch = main.make_mergebranch_name(merge_branch_pattern, source_branch, dest_branch)
        expected_merge_branch = 'merge/from_SOURCE-BRANCH_into_DEST-BRANCH'
        self.assertEqual(expected_merge_branch, merge_branch)

    def test_invalid_date_placeholder(self):
        main.g_start_timestamp = datetime.strptime('2023-01-01', '%Y-%m-%d')
        source_branch = 'SOURCE-BRANCH'
        dest_branch = 'DEST-BRANCH'
        merge_branch_pattern = 'merge/from_%SBR_into_%DBR_%DATE()'
        merge_branch = main.make_mergebranch_name(merge_branch_pattern, source_branch, dest_branch)
        expected_merge_branch = 'merge/from_SOURCE-BRANCH_into_DEST-BRANCH_%DATE()'
        self.assertEqual(expected_merge_branch, merge_branch)
