import textwrap
import unittest

from src import merge_git_repos as main


class Test01(unittest.TestCase):

    def test_make_report_html_content(self):
        repos_metadata = [
            {
                "repo_data_from_parameter": "repo1:::prj1/repository1",
                "repo_local_name": "repo1",
                "prj_and_repo_remote_name": "prj1/repository1",
                "source_branch": "origin/master",
                "dest_branch": "my-feature",
                "task_start": "2023-01-01T08:00:00.000000",
                "repo_dir": "repos/repo1",
                "repos_dir": "./repos",
                "task_end": "2023-01-01T08:00:11.000000",
                "task_duration": "0:00:11.000000",
                "task_finish_status": "successfully",
                "task_finish_details": ""
            },
            {
                "repo_data_from_parameter": "repo2",
                "repo_local_name": "repo2",
                "prj_and_repo_remote_name": "",
                "source_branch": "origin/master",
                "dest_branch": "my-feature",
                "task_start": "2023-01-01T08:00:01.000000",
                "repo_dir": "repos/repo1",
                "repos_dir": "./repos",
                "task_end": "2023-01-01T08:00:09.000000",
                "task_duration": "0:00:08.000000",
                "task_finish_status": "with error",
                "task_finish_details": "This is the error-message"
            }]

        report_xml = main.make_report_xml_content(repos_metadata)
        # print(report_xml)

        exprected_report_xml = textwrap.dedent("""\
        <table>
        <tr><td>repo_local_name</td><td>task_finish_status</td><td>source_branch</td><td>dest_branch</td><td>task_duration</td><td>task_finish_details</td></tr>
        <tr><td>repo1</td><td>successfully</td><td>origin/master</td><td>my-feature</td><td>0:00:11.000000</td><td></td></tr>
        <tr><td>repo2</td><td>with error</td><td>origin/master</td><td>my-feature</td><td>0:00:08.000000</td><td>This is the error-message</td></tr>
        </table>""")

        self.assertEquals(exprected_report_xml, report_xml)
