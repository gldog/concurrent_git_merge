#!/usr/bin/env python3

import argparse
import atexit
import concurrent.futures
import json
import logging
import os
import pathlib
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta
from typing import List

from jinja2 import Environment

__version__ = '1.0.0-dev'

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
DEFAULT_LOGLEVEL = 'INFO'
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]

g_script_start = datetime.now()
g_logger = logging.getLogger()


def configure_logger(log_level, logs_dir):
    logger = logging.getLogger()
    # Set basicConfig() to get levels less than WARNING running in our logger.
    # See https://stackoverflow.com/questions/56799138/python-logger-not-printing-info
    logging.basicConfig(level=logging.DEBUG)
    # See also https://docs.python.org/3/howto/logging.html:
    # The check for valid values have been done in parser.add_argument().
    # setLevel() takes string-names as well as numeric levels.
    # Must be set after logging.basicConfig(). If set before, the level is the one of basicConfig().
    logger.setLevel(log_level)
    log_formatter = logging.Formatter(f'%(asctime)s:{SCRIPT_NAME}:%(levelname)s: %(message)s')
    logger.handlers[0].setFormatter(log_formatter)
    # Add a file-handler.
    file_handler = logging.FileHandler(f'{logs_dir}/out.log')
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)


def init_argument_parser():
    # The '%' is a special character and has to be escaped by another '%'
    parser = argparse.ArgumentParser(
        # The RawTextHelpFormatter allows leves newlines. This allows formatted output of the --repos-data description.
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=120),

        # -- 50 --------------- | ---------------------------------------------------------------- 100 -- #
        description=textwrap.dedent("""\
        This script do merges in a list of repos. It was written to handle merges in projects comprising of
        multiple Git repositories but with shared source- and dest-branch names.
        
        The shared source- and dest-branch names can be given globally, but branch names specific to a repo
        can also be given individually.

        The merges are executed in concurrent merge-tasks. For each task a logfile is written.

        This script do not clone the repos. This is because you might post-process cloned repos before merging, e.g.
        define merge-drivers and register them in $GIT_DIR/info/attributes.

        At the begin of a task, an optional pre-script given in --pre-script can be executed. Also at the end
        of a task an optional post-script given in --post-script can be executed.
        
        Overview of commands:
            pre_script, if given in --pre-script
            git reset --hard
            git clean -fd
            git checkout {dest_branch}
            Create merge branch and checkout, if --merge-branch-template is given.
            git merge --no-edit {merge_options} {source_branch|merge-branch}
            post_script, if given in --post-script"""))
    parser.add_argument('-r', '--repos-data', required=True, nargs='+',
                        metavar='repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name]',
                        # ---------------------------------------------------------------- 100 -- #
                        help=textwrap.dedent("""\
                        Information about the repos and branches to be processed. They are given as
                        positional parts, delimited by colon ':'.
                          1. 'repo_local_name', mandatory
                              The name of the repo as it exists in the repos-directory.
                          2. 'source_branch', optional
                              The branch to be merged into the dest-branch. If omitted it falls
                              back to -S/--default-source-branch. At least one of the two must be
                              given.
                          3. 'dest_branch', optional
                              The branch to be updated from the source-branch. If omitted it falls
                              back to -D/--default-dest-branch. At lest one of the two must be given.
                          4. 'prj/repo_remote_name', optional
                              The remote project- and repo-name. Exposed as environment variable to
                              the script given in --pre-script.
                              The 'prj'-part is the Bitbucket-project or the Github-username or the
                              Gitlab-namespace.
                        The full notation is:
                                -r repo_local_name:source_branch:dest_branch:prj/repo_remote_name
                        Optional parts may be empty:
                                -r repo_local_name:::
                        Delimiters of empty parts can be omitted from right to left. The above
                        parameter can be given as:
                                -r repo_local_name
                        The repos given in this parameter should exist in -d/--repos-dir. This
                        script does not clone missing repos. If a repo is missing, its merge-task
                        will be aborted and an error-message will be printed, but the script will
                        continue and all existing repos will be merged.
                        Examples:
                          1) One Repo with source- and dest-branches given
                                -r my-repo-1:origin/master:my-feature
                            The last part 'prj/repo-remote-name' is not given, the last delimiter
                            ':' is omitted.
                          2) Two repos sharing source- and -dest-branch-names
                                -r product1-module1 product1-module2 \\
                                    -S origin/master -D my-feature
                            That is the short notation. As the parts are delimited by colon ':',
                            the full also valid notation would be:
                                -r product1-module1::: product1-module2::: \\
                                    -S origin/master -D my-feature
                          3) As example 2), but with abbreviated local repo-names, and
                            'prj/repo_remote_name' given as named on the remote, to be exposed to
                            the pre-merge-script. Because the parts are positional, the delimiters
                            must be given.
                                -r p1-m1:::products/product1-module1 \\
                                   p1-m2:::products/product1-module2 \\
                                -S origin/master  -D my-feature \\
                                -e clone_if_absent_and_install_merge-drivers.sh"""))
    parser.add_argument('-d', '--repos-dir', required=True,
                        help="Directory the repos resides.")
    parser.add_argument('-o', '--logs-dir', required=True,
                        help="Logs-directory.")
    parser.add_argument('-S', '--default-source-branch', default='',
                        help="Default source branch used for repos without given source-branch.")
    parser.add_argument('-D', '--default-dest-branch', default='',
                        help="Default destination branch used for repos without given dest-branch.")
    parser.add_argument('-m', '--merge-options', default='',
                        help=textwrap.dedent("""\
                        Options for git merge command. Must be given as one string, e.g.:
                          --merge-options '--no-ff -Xrenormalize -Xignore-space-at-eol'
                        The option --no-edit is always set internally."""))
    parser.add_argument('-t', '--merge-branch-template',
                        help=textwrap.dedent("""\
                        Create a merge-branch based on the dest-branch and do the merge in this
                        branch. If the merge-branch exists it will be reused. This allows continuing
                        a merge by calling the merge script again (if the merge-branch name doesn't
                        have a date generated at the time of calling the merge script).
                        A merge-branch typically is used in case you wan't to create a pull request
                        from the merge-result to an upstream-branch. Either because you want QA
                        on the PR, or you have no permission to merge into the target-branch
                        directly.
                        The template generating the name of the merge-branch is a jinja2-template
                        and understands the following placeholders:
                          o repo_local_name     From parameter -r/--repos-data the 1st part
                                                'repo_local_name'.
                          o source_branch       From parameter -r/--repos-data the 2nd part
                                                'source_branch', or the default-source-branch -S if
                                                absent.
                          o dest_branch         From parameter -r/--repos-data the 3rd part
                                                'dest-branch', or the default-dest-branch -D if
                                                absent.
                          o prj_and_repo_remote_name    From parameter -r/--repos-data the 4th
                                                part 'prj/repo-remote-name'.
                          o repo_data_from_parameter    From parameter -r/--repos-data the
                                                complete string.
                          o task_start          The timestamp the repo's task has been started.
                        The task_start is of Python-type 'datetime'. strftime() can be used to
                        generate a pretty-print timestamp. An example to be used in a bash-script:
                            parameters=" --merge-branch-template
                            parameters+=" merge/from_{{source_branch.replace('origin/','')}}"
                            parameters+="_into_{{dest_branch}}_{{task_start.strftime('%%Y%%m%%d-%%H%%M%%S')}}"
                        The task's timestamps are very close to the one the script was started. But you might
                        prefer a guaranteed common timestamp for all merge-branches (and for the logs-dir):
                            DATE_STR="$(date +'%%Y%%m%%d-%%H%%M%%S')"
                            merge_git_repos.py \\
                              --merge-branch-template "merge/...$DATE_STR" \\
                              --logs-dir "./logs/$DATE_STRING" \\
                              ... """))
    parser.add_argument('-l', '--log-level', choices=LOG_LEVELS, default=DEFAULT_LOGLEVEL,
                        help=f"Defaults to {DEFAULT_LOGLEVEL}.")
    parser.add_argument('--pre-script',
                        help=textwrap.dedent("""\
                        This script is executed at the begin of each repo's merge-task. Here you can
                        clone the repos, install merge-drivers, and others. This script doesn't run
                        in the repo's directory. Therefore the Git-command must be given with 
                        '-C $MGR_REPO_DIR', or you have to change to the repo's directory in the
                        script. This script runs in an environment with repo-specific environment
                        variables exposed:
                          o MGR_REPO_LOCAL_NAME From parameter -r/--repos-data the 1st part
                                                'repo_local_name'.
                          o MGR_SOURCE_BRANCH   From parameter -r/--repos-data the 2nd part
                                                'source_branch', or the default-source-branch -S if
                                                absent.
                          o MGR_DEST_BRANCH     From parameter -r/--repos-data the 3rd part
                                                'dest-branch', or the default-dest-branch -D if
                                                absent.
                          o MGR_PRJ_AND_REPO_REMOTE_NAME    From parameter -r/--repos-data the 4th
                                                part 'prj/repo-remote-name'.
                          o MGR_REPO_DATA_FROM_PARAMETER    From parameter -r/--repos-data the
                                                complete string.
                          o MGR_TASK_START      The timestamp the repo's task has been started.
                          o MGR_MERGE_BRANCH    From parameter -m/--merge-branch-template if given,
                                                with placeholders replaced.
                          o MGR_REPO_DIR        'repo_local_name' part of parameter -r/--repos-data,
                                                prefixed with parameter -d.
                          o MGR_REPOS_DIR       From parameter -d/--repos-dir.
                          o MGR_LOGS_DIR        From parameter -o/--logs-dir.
                        For cloning you'll use MGR_REPOS_DIR, and for commands inside a repo you'll
                        use MGR_REPO_DIR.
                        On Windows and Gitbash you should call the script with 'bash -c your-script.sh'
                        Otherwise it could be Windows opens it with the default-application, e.g. a
                        text editor."""))
    parser.add_argument('--post-script',
                        help=textwrap.dedent("""\
                        This script is executed at the end of each repo's merge-task, regardless of the
                        merge result. Here you can push the result, create pull requests, and others.
                        This script doesn't run in the repo's directory (see --pre-script). This script
                        runs in an environment with repo-specific environment variables exposed as
                        described in --pre-script.
                        A most simple post-script parameter could be:
                            --post-script 'bash -c "git push --set-upstream origin HEAD"'
                        (The push --set-upstream can be executed multiple times without error.)"""))
    return parser


def make_repo_metadata(repo_data_from_parameter: str):
    # Spit the parameter repo_data_from_parameter into:
    #   o repo_local_name
    #   o source_branch
    #   o dest_branch
    #   o prj/repo_remote_name
    #
    parts = re.split(':', repo_data_from_parameter)
    error_msg = f"Given repo_data '{repo_data_from_parameter}' has unexpected format. " + \
                "See help for parameter -r/--repos-data for accepted formats."

    # Expect a length between 1 and 4.
    if len(parts) not in range(1, 5):
        raise ValueError(error_msg)

    # Extend to 5 entries.
    parts = [*parts, *([''] * (4 - len(parts)))]
    repo_metadata = {'repo_data_from_parameter': repo_data_from_parameter}
    repo_local_name = parts[0].strip()
    if repo_local_name:
        repo_metadata['repo_local_name'] = repo_local_name
    source_branch = parts[1].strip()
    if source_branch:
        repo_metadata['source_branch'] = source_branch
    dest_branch = parts[2].strip()
    if dest_branch:
        repo_metadata['dest_branch'] = dest_branch
    prj_and_repo_remote_name = parts[3].strip()
    if prj_and_repo_remote_name:
        repo_metadata['prj_and_repo_remote_name'] = prj_and_repo_remote_name

    return repo_metadata


def make_repos_metadata(repos_data: List[str], default_source_branch: str, default_dest_branch: str):
    """
    Transform the repos given in command line parameter -r/--repo-names into dict of following format:

        [
            {
                'repo_local_name': 'repo1',
                'source_branch': 'stable-tag-1',
                'dest_branch': 'my-feature-branch',
                'prj_and_repo_remote_name': 'prj1/repository-with-long-name1',
            },
            ...
        ]
    """
    default_source_branch = default_source_branch.strip()
    default_dest_branch = default_dest_branch.strip()
    repos_metadata = []
    for repo_data in repos_data:
        # repo_data is the value given in parameter -r/--repos-data.
        repo_metadata = make_repo_metadata(repo_data)
        if 'source_branch' not in repo_metadata:
            repo_metadata['source_branch'] = default_source_branch
        if 'dest_branch' not in repo_metadata:
            repo_metadata['dest_branch'] = default_dest_branch
        repos_metadata.append(repo_metadata)
    return repos_metadata


def validate_repos_metadata(repos_metadata):
    """
    Check for completeness of each repo's metadata.

    Each repo needs a source-branch and a dest-branch. They can be given in parameter -r/--repos-data, or as default
    in -S/--default-source-branch and -D/--default-dest-branch. But if not given, the merge can't be started. This
    is a configuration error.
    """

    errors = []
    # Collect the repo-local-names to check if they are unique.
    repo_local_names = set()
    for repo_metadata in repos_metadata:
        repo_data_from_parameter = repo_metadata['repo_data_from_parameter']
        repo_local_name = repo_metadata['repo_local_name']
        if not repo_local_name:
            errors.append(f"Missing repo-local-name in repo-data '{repo_data_from_parameter}'")
        else:
            repo_local_names.add(repo_local_name)
        if not repo_metadata['source_branch']:
            errors.append(f"Missing source-branch in or for repo-data '{repo_data_from_parameter}'")
        if not repo_metadata['dest_branch']:
            errors.append(f"Missing dest-branch in or for repo-data '{repo_data_from_parameter}'")
        # The 'prj/repo-remote-name' part ist optional.
    if len(repo_local_names) < len(repos_metadata):
        errors.append(f"Repo-short-names not unique.")

    return errors


def serialize_datetime_or_propagate(obj):
    """Tell json.dumps() how to serialize datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


def log_task(logfile_name: str, logfile_content: str):
    logfile_path = pathlib.Path(g_cl_args.logs_dir, logfile_name)
    with open(logfile_path, 'a', newline='') as f:
        f.write(logfile_content)


def run_command(command, repo_name, logfile_name, honor_returncode=True, suppress_stdout=False, env=None):
    g_logger.info(f"{repo_name}: $ {command}")
    log_task(logfile_name, f"$ {command}\n")
    timestamp_begin = datetime.now()
    r = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, text=True, env=env)
    timestamp_end = datetime.now()
    output = f"Returncode: {r.returncode}; Duration: {timestamp_end - timestamp_begin}"
    if not suppress_stdout:
        output += f"; Output:\n{r.stdout}"
    log_task(logfile_name, f"{output}\n")
    if honor_returncode and r.returncode != 0:
        error_msg = f"{repo_name}: The following command exited with exit-code {r.returncode}:\n" \
                    f"{command}\n{r.stdout}"
        raise Exception(error_msg)
    return r


def make_mergebranch_name(merge_branch_template, repo_metadata):
    """
    Make the formatted string, with values from "repo_metadata" replaced.

    Example:

    --merge-branch-template \
      "maintain/{{source_branch.replace('origin/','')}}_into_{{dest_branch}}_{{task_start.strftime('%b%d')}}"

    :param merge_branch_template: jinja2-template.
    :param repo_metadata: repo_metadata dict.
    :return: The template-string with the values replaced.
    """

    jinja_environment = Environment()
    tmpl = jinja_environment.from_string(merge_branch_template)
    merge_branch = tmpl.render(repo_metadata)

    return merge_branch


def execute_merge(repo_metadata):
    task_start_timestamp = datetime.now()
    repo_local_name = repo_metadata['repo_local_name']
    source_branch = repo_metadata['source_branch']
    dest_branch = repo_metadata['dest_branch']
    repo_dir = pathlib.Path(g_cl_args.repos_dir, repo_local_name)
    repo_metadata['task_start'] = task_start_timestamp
    # Need str() here to avoid "TypeError: Object of type PosixPath is not JSON serializable".
    repo_metadata['repo_dir'] = str(pathlib.Path(g_cl_args.repos_dir, repo_local_name))
    # Add some global data.
    repo_metadata['repos_dir'] = g_cl_args.repos_dir
    repo_metadata['logs_dir'] = g_cl_args.logs_dir

    if g_cl_args.merge_branch_template:
        repo_metadata['merge_branch'] = make_mergebranch_name(g_cl_args.merge_branch_template, repo_metadata)

    logfile_name = f'repo--{repo_local_name}.log'
    log_msg = f"Started merge-task for {repo_local_name}."
    g_logger.info(log_msg)
    log_task(logfile_name, f"{log_msg}\n")
    log_task(logfile_name, "repo_metadata at task-begin:\n" +
             f"{json.dumps(repo_metadata, indent=2, default=serialize_datetime_or_propagate)}\n")

    task_finish_status = "successfully"
    repo_metadata['task_finish_details'] = ''
    # try: run_command() might raise an exception.
    try:
        extended_env = os.environ.copy()
        if g_cl_args.pre_script or g_cl_args.post_script:
            # Expose all members of repo_metadata as environment-vars, prefixed with "MGR_".
            for key, value in repo_metadata.items():
                env_var_name = f"MGR_{key.upper()}"
                if isinstance(value, datetime):
                    value = value.isoformat()
                extended_env[env_var_name] = value
        if g_cl_args.pre_script:
            log_task(logfile_name, "PRE-SCRIPT BEGIN >>>>>\n")
            log_task(logfile_name, "# Pre-script called by command:\n")
            command = g_cl_args.pre_script
            run_command(command, repo_local_name, logfile_name, env=extended_env)
            log_task(logfile_name, ">>>>> PRE-SCRIPT END\n")

        # The repo is expected to be present.
        if not pathlib.Path(repo_dir, '.git').is_dir():
            raise Exception(
                f"Repo '{repo_local_name}' is given in parameter " +
                f"-r/--repos-data {repo_metadata['repo_data_from_parameter']}, " +
                f"but it is missing in parameter -d/--repos-dir {g_cl_args.repos_dir}.")

        run_command(f'git -C {repo_dir} reset --hard', repo_local_name, logfile_name)
        run_command(f'git -C {repo_dir} clean -fd', repo_local_name, logfile_name)
        run_command(f'git -C {repo_dir} checkout {dest_branch}', repo_local_name, logfile_name)

        if g_cl_args.merge_branch_template:
            # Delete the merge-branch if it exists.
            # suppress_stdout=True: The command returns an empty line. This looks a bit confusing in the logfile. Avoid
            # that.
            r = run_command(f'git -C {repo_dir} show-ref --verify --quiet refs/heads/{repo_metadata["merge_branch"]}',
                            repo_local_name, logfile_name, honor_returncode=False, suppress_stdout=True)
            if r.returncode == 0:
                log_task(logfile_name, "  (Merge-branch present, reuse it)\n\n")
                b = ''
            else:
                log_task(logfile_name, "  (Merge-branch not present)\n\n")
                b = '-b '

            run_command(f'git -C {repo_dir} checkout {b}{repo_metadata["merge_branch"]}', repo_local_name,
                        logfile_name)

        # On merge-conflicts, git merge exists with 1. Ignore this exit code to allow running the post-script regardless
        # of the merge result. But signal that after the post-script has been run.
        r_merge = run_command(f'git -C {repo_dir} merge --no-edit {g_cl_args.merge_options} {source_branch}',
                              repo_local_name, logfile_name, honor_returncode=False)

        if g_cl_args.post_script:
            log_task(logfile_name, "POST-SCRIPT BEGIN >>>>>\n")
            command = g_cl_args.post_script
            run_command(command, repo_local_name, logfile_name, env=extended_env)
            log_task(logfile_name, ">>>>> POST-SCRIPT END\n")

        if r_merge.returncode != 0:
            # Signal the merge failed.
            error_msg = f"{repo_dir}: git merge exited with non-zero status. Output: {r_merge.stdout}"
            raise Exception(error_msg)

    except Exception as e:
        task_finish_status = "with FAILURE"
        repo_metadata['task_finish_details'] = str(e)
        return str(e)
    finally:
        task_end_timestamp = datetime.now()
        repo_metadata['task_end'] = task_end_timestamp
        task_duration = task_end_timestamp - task_start_timestamp
        repo_metadata['task_duration'] = str(task_duration)
        repo_metadata['task_finish_status'] = task_finish_status
        log_msg = f"Finished merge-task for '{repo_local_name}' {task_finish_status}."
        if task_finish_status == "successfully":
            g_logger.info(log_msg)
        else:
            g_logger.warning(log_msg)
        log_task(logfile_name, f"{log_msg}\n")
        log_task(logfile_name, "repo_metadata at task-end:\n" +
                 f"{json.dumps(repo_metadata, indent=2, default=serialize_datetime_or_propagate)}\n")


def get_formatted_timediff_mmss(time_diff: timedelta) -> str:
    """
    Convert the given time_diff to format "MM:SS.00".
    The MM can be > 60 min.
    :param time_diff: The time-diff
    :return: Time-diff in MM:SS.00, where "00" represents milliseconds.
    """

    total_seconds = time_diff.total_seconds()
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    # Seconds-format "05.2f": 5 = 2 digits for seconds + dot + 2 digits for millis.
    formatted_diff = f'{minutes:02.0f}:{seconds:05.2f}'

    return formatted_diff


def make_report_xml_content(repos_metadata):
    EMPTY_CELL_DEFAULT = '&nbsp;'
    lines = []
    line = []

    lines.append('<table>')
    line.append('<tr>')
    line.append('<td>repo_local_name</td>')
    line.append('<td>task_finish_status</td>')
    line.append('<td>source_branch</td>')
    line.append('<td>dest_branch</td>')
    line.append('<td>task_duration</td>')
    line.append('<td>task_finish_details</td>')
    line.append('</tr>')
    lines.append(''.join(line))

    for repo_metadata in repos_metadata:
        line.clear()
        line.append('<tr>')
        line.append(f'<td>{dict.get(repo_metadata, "repo_local_name", EMPTY_CELL_DEFAULT)}</td>')
        line.append(f'<td>{dict.get(repo_metadata, "task_finish_status", EMPTY_CELL_DEFAULT)}</td>')
        line.append(f'<td>{dict.get(repo_metadata, "source_branch", EMPTY_CELL_DEFAULT)}</td>')
        line.append(f'<td>{dict.get(repo_metadata, "dest_branch", EMPTY_CELL_DEFAULT)}</td>')
        line.append(f'<td>{dict.get(repo_metadata, "task_duration", EMPTY_CELL_DEFAULT)}</td>')
        line.append(f'<td>{dict.get(repo_metadata, "task_finish_details", EMPTY_CELL_DEFAULT)}</td>')
        line.append('</tr>')
        lines.append(''.join(line))

    lines.append('</table>')

    return '\n'.join(lines)


def exit_handler():
    g_logger.info(f"Script finished, took {get_formatted_timediff_mmss(datetime.now() - g_script_start)}")


def main():
    atexit.register(exit_handler)

    cl_parser = init_argument_parser()
    global g_cl_args
    g_cl_args = cl_parser.parse_args()

    os.makedirs(g_cl_args.logs_dir, exist_ok=True)

    configure_logger(g_cl_args.log_level, g_cl_args.logs_dir)

    g_logger.debug(f"args: {g_cl_args}")

    repos_metadata = make_repos_metadata(g_cl_args.repos_data, g_cl_args.default_source_branch,
                                         g_cl_args.default_dest_branch)
    g_logger.debug(f"repos_metadata: {json.dumps(repos_metadata, default=serialize_datetime_or_propagate)}")
    errors = validate_repos_metadata(repos_metadata)
    if errors:
        g_logger.error(errors)
        sys.exit(1)

    os.makedirs(g_cl_args.repos_dir, exist_ok=True)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        errors = list(executor.map(execute_merge, repos_metadata))

    # with multiprocessing.Pool() as pool:
    #    errors = list(pool.map(execute_merge, repos_metadata))

    # Write HTML-report
    report_html_file = pathlib.Path(g_cl_args.logs_dir, 'report.xml')
    with open(report_html_file, 'w') as f:
        f.write(make_report_xml_content(repos_metadata))

    g_logger.debug(f"repos_metadata: {json.dumps(repos_metadata, default=serialize_datetime_or_propagate)}")
    # The list "errors" contains one entry per thread. An entry is either an error-message or None. Remove all
    # None-values.
    errors = [error for error in errors if error is not None]
    if errors:
        for error in errors:
            if error is not None:
                g_logger.error(error)
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
