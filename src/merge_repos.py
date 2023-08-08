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

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
DEFAULT_LOGLEVEL = 'INFO'
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]

g_start_timestamp = datetime.now()
g_logsdir_with_timestamped_subdir = ''
g_logger = logging.getLogger()


def configure_logger(log_level, logs_dir):
    logger = logging.getLogger()
    # See also https://docs.python.org/3/howto/logging.html:
    # The check for valid values have been done in parser.add_argument().
    # setLevel() takes string-names as well as numeric levels.
    logger.setLevel(log_level)
    # Set basicConfig() to get levels less than WARNING running in our logger.
    # See https://stackoverflow.com/questions/56799138/python-logger-not-printing-info
    logging.basicConfig(level=logging.DEBUG)
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
        This script do merges in a list of repos. For each repo, a source-branch and a dest-branch must be
        given. Source- and dest-branches can be given individually for each repo, and as defaults to be
        used in multiple repos sharing these branch-names.

        The merges are executed in parallel. For each task a logfile is written.

        This script do not clone the repos. This is because you might post-process cloned repos, e.g.
        install merge-drivers.

        Before each merge, an optional pre-merge-script can be executed, given in parameter
        -e/--exec-pre-merge-script."""))
    parser.add_argument('-r', '--repos-data', required=True, nargs='+',
                        metavar='repo-local-name:[source-branch]:[dest-branch]:[prj/repo-remote-name]',
                        # ---------------------------------------------------------------- 100 -- #
                        help=textwrap.dedent("""\
                        Information about the repos and branches to be processed. They are given as
                        positional parts, delimited by colon ':'.
                            1. 'repo-local-name', mandatory. 
                                The name of the repo as it exists in the repos-directory.
                            2. 'source-branch', optional
                                The branch to be merged into the dest-branch. If omitted it falls
                                back to -S/--default-source-branch. At lest one of the two must be
                                given.
                            3. 'dest-branch', optional
                                The branch to be updated from the source-branch. If omitted it
                                falls back to -D/--default-dest-branch. At lest one of the two must
                                be given.
                            4. 'prj/repo-remote-name', optional
                                The remote project- and repo-name. Exposed as environment variable
                                to the script given in -e/--exec-pre-merge-script.
                                The 'prj'-part is the Bitbucket-project or the Github-username or 
                                the Gitlab namespace.
                        The full notation is:
                                -r repo-local-name:source-branch:dest-branch:prj/repo-remote-name
                        Optional parts may be empty:
                                -r repo-local-name:::
                        But delimiters of empty parts can be omitted from right to left.
                        The above parameter can be given as:
                                -r repo-local-name 
                        The repos given in this parameter should exist in -d/--repos-dir. This
                        script does not clone missing repos. If a repo is missing, its merge-task
                        will be aborted and an error-message will be printed. But all existing
                        repos will be merged.
                        Examples:
                        1) One Repo with source- and dest-branches given
                                -r my-repo-1:origin/master:my-feature
                            The last part 'prj/repo-remote-name' is not given, the last delimiter
                            ':' can be omitted.
                        2) Two Repos sharing source- and -dest-branch-names
                                -r product1-module-a product1-module-b \\
                                    -S origin/master -D my-feature
                            That is the short notation. As the parts are delimited by colon ':',
                            the full also valid notation would be:
                                -r product1-module-a::: product1-module-b::: \\
                                    -S origin/master -D my-feature
                        3) As example 2), but with abbreviated local repo-names, and
                            'prj/repo-remote-name' given to be exposed to the pre-merge-script as
                            named on the remote. Because the parts are positional, the delimiters
                            must be given.
                                -r p1-m-a:::products/product1-module-a \\
                                   p1-m-b:::products/product1-module-a \\
                                   -S origin/master -D my-feature \\
                                   -e clone_if_absent_and_install_merge-drivers.sh"""))
    parser.add_argument('-d', '--repos-dir', required=True,
                        help="Directory the repos resides.")
    parser.add_argument('-o', '--logs-dir', required=True,
                        help=textwrap.dedent("""\
                        Log-directory. Each run of this script creates a subdirectory with a
                        timestamp."""))
    parser.add_argument('-S', '--default-source-branch', default='',
                        help="Default source branch used for repos without given source-branch .")
    parser.add_argument('-D', '--default-dest-branch', default='',
                        help="Default destination branch used for repos without given dest-branch.")
    parser.add_argument('-m', '--merge-branch-pattern',
                        help=textwrap.dedent("""\
                        Create a merge-branch based on the dest-branch and do the merge in this
                        branch. If the merge-branch exists it will be deleted and re-created.
                        The pattern understands the following placeholders:
                          o %%SBR           Source-branch name
                          o %%DBR           Dest-branch name
                          o %%DATE(format)  Date.
                                For format see 'strftime() and strptime() Format Codes'
                                https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes.
                                E.g. %%DATE(%%d%%b) will be replaced with '01Jan'.
                                In a Unix shell you can also use $(date +%%d%%b). But the %%DATE()
                                placeholder is portable because Python does the formatting rather
                                than an external command."""))
    parser.add_argument('--local', default=False, action='store_true',
                        help=textwrap.dedent("""\
                        Skip the git pull command. Allows to merge a local-only source-branch that
                        has no tracking remote-branch."""))
    parser.add_argument('-l', '--log-level', choices=LOG_LEVELS, default=DEFAULT_LOGLEVEL,
                        help=f"Defaults to {DEFAULT_LOGLEVEL}.")
    parser.add_argument('-e', '--exec-pre-merge-script',
                        help=textwrap.dedent("""\
                        This script is executed in each repo's merge-task, means it runs parallel.
                        Here you can clone the repos, install merge-drivers, and others.
                        This script runs in an environment with repo-specific environment variables
                        exposed:                        
                        o MR_REPO_LOCAL_NAME    From parameter -r the 'repo-local-name' part.
                        o MR_SOURCE_BRANCH      From parameter -r the 'source-branch' part, or the
                                                default-source-branch -S if absent.
                        o MR_DEST_BRANCH        From parameter -r the 'dest-branch' part, or the
                                                default-dest-branch -D if absent.
                        o MR_REPO_DIR           Parameter -d, extended by a timestamp and the
                                                'repo-local-name' part of parameter -r.
                        o MR_PRJ_REPO_REMOTE_NAME   From parameter -r the part 'prj/repo-remote-name'."""))

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


def log_task(logfile_name: str, logfile_content: str):
    logfile_path = pathlib.Path(g_logsdir_with_timestamped_subdir, logfile_name)
    with open(logfile_path, 'a', newline='') as f:
        f.write(logfile_content)


def run_command(command, command_pretty_print_for_log, repo_displayname_for_log, logfile_name, honor_returncode=True,
                env=None):
    g_logger.info(f"{repo_displayname_for_log}: $ {command_pretty_print_for_log}")
    log_task(logfile_name, f"$ {command}\n")
    timestamp_begin = datetime.now()
    r = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, env=env)
    timestamp_end = datetime.now()
    log_task(logfile_name,
             f"Returncode: {r.returncode}; " +
             f"Duration: {timestamp_end - timestamp_begin}; " +
             f"Output:\n{r.stdout.decode()}\n")
    if honor_returncode and r.returncode != 0:
        error_msg = f"{repo_displayname_for_log}: The following command exited with exit-code {r.returncode}:\n" \
                    f"{command}\n{r.stdout.decode()}"
        raise Exception(error_msg)
    return r


def run_commands(commands: List[str], remove_str, repo_displayname_for_logging, logfile_name):
    for command in commands:
        command_pretty_print_for_log = command.replace(remove_str, '')
        run_command(command, command_pretty_print_for_log, repo_displayname_for_logging, logfile_name)


def make_mergebranch_name(merge_branch_pattern, source_branch, dest_branch):
    merge_branch = merge_branch_pattern.replace('%SBR', source_branch).replace('%DBR', dest_branch)
    m = re.search(r'%DATE\((.+)\)', merge_branch_pattern)
    if m:
        strftime_format = m.group(1)
        formatted_date = g_start_timestamp.strftime(strftime_format)
        merge_branch = re.sub(r'%DATE\(.+\)', formatted_date, merge_branch)
    return merge_branch


def execute_merge(repo_metadata):
    task_start_timestamp = datetime.now()
    repo_local_name = repo_metadata['repo_local_name']
    source_branch = repo_metadata['source_branch']
    dest_branch = repo_metadata['dest_branch']
    repo_dir = pathlib.Path(g_cl_args.repos_dir, repo_local_name)
    # Need str() here to avoid "TypeError: Object of type PosixPath is not JSON serializable".
    repo_metadata['repo_dir'] = str(pathlib.Path(g_cl_args.repos_dir, repo_local_name))
    repo_metadata['repos_dir'] = g_cl_args.repos_dir
    logfile_name = f'repo--{repo_local_name}.log'
    log_msg = f"Started merge-task for {repo_local_name}."
    g_logger.info(log_msg)
    log_task(logfile_name, f"{log_msg}\n")
    log_task(logfile_name, f"repo_metadata at task-begin:\n{json.dumps(repo_metadata, indent=2)}\n")

    task_finish_status = "successfully"
    try:
        repo_displayname_for_logging = repo_local_name

        if g_cl_args.exec_pre_merge_script:
            env = os.environ.copy()
            for key, value in repo_metadata.items():
                env_var_name = f"MR_{key.upper()}"
                env[env_var_name] = value
            command = g_cl_args.exec_pre_merge_script
            run_command(command, command, repo_displayname_for_logging, logfile_name, env=env)

        # The repo is expected to be present.
        if not pathlib.Path(repo_dir, '.git').is_dir():
            raise Exception(
                f"Repo '{repo_local_name}' is given in parameter " +
                f"-r/--repos-data {repo_metadata['repo_data_from_parameter']}, " +
                f"but it is missing in parameter -d/--repos-dir {g_cl_args.repos_dir}.")

        commands = [
            f'git -C {repo_dir} reset --hard',
            f'git -C {repo_dir} clean -fd',
            f'git -C {repo_dir} checkout {dest_branch}'
        ]
        if not g_cl_args.local:
            commands.append(f'git -C {repo_dir} pull --ff')

        run_commands(commands, f' -C {repo_dir}', repo_displayname_for_logging, logfile_name)
        commands.clear()

        if g_cl_args.merge_branch_pattern:
            merge_branch = make_mergebranch_name(g_cl_args.merge_branch_pattern, source_branch, dest_branch)
            # Delete the merge-branch if it exists.
            command = f'git -C {repo_dir} show-ref --verify --quiet refs/heads/{merge_branch}'
            command_pretty_print_for_log = command.replace(f' -C {repo_dir}', '')
            r = run_command(command, command_pretty_print_for_log, repo_displayname_for_logging, logfile_name,
                            honor_returncode=False)
            if r.returncode == 0:
                commands.append(f'git -C {repo_dir} branch -D {merge_branch}')
            else:
                log_task(logfile_name, "  (Merge-branch not present)\n\n")
            commands.append(f'git -C {repo_dir} checkout -b {merge_branch}')

        commands.append(
            f'git -C {repo_dir} merge --no-ff --no-edit -Xrenormalize -Xignore-space-at-eol {source_branch}')
        run_commands(commands, f' -C {repo_dir}', repo_displayname_for_logging, logfile_name)

    except Exception as e:
        task_finish_status = "with error"
        return str(e)
    finally:
        task_end_timestamp = datetime.now()
        repo_metadata['task_start'] = task_start_timestamp.isoformat()
        repo_metadata['task_end'] = task_end_timestamp.isoformat()
        task_duration = task_end_timestamp - task_start_timestamp
        repo_metadata['task_duration'] = str(task_duration)
        log_msg = f"Finished merge-task for '{repo_local_name}' {task_finish_status}."
        g_logger.info(log_msg)
        log_task(logfile_name, log_msg)
        log_task(logfile_name, f"repo_metadata at task-end:\n{json.dumps(repo_metadata, indent=2)}\n")


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
    formatted_diff = f'{minutes:02.0f}:{seconds:02.2f}'

    return formatted_diff


def exit_handler():
    g_logger.info(f"Script finished, took {get_formatted_timediff_mmss(datetime.now() - g_start_timestamp)}")


def main():
    atexit.register(exit_handler)

    cl_parser = init_argument_parser()
    global g_cl_args
    g_cl_args = cl_parser.parse_args()

    # The g_logsdir_with_timestamped_subdir can't be set at the beginning of the script because it contains data
    # from the arg-parser.
    global g_logsdir_with_timestamped_subdir
    start_timestamp_formatted_str = g_start_timestamp.strftime('%Y%m%d-%H%M%S')
    g_logsdir_with_timestamped_subdir = pathlib.Path(g_cl_args.logs_dir, start_timestamp_formatted_str)
    os.makedirs(g_logsdir_with_timestamped_subdir, exist_ok=True)

    configure_logger(g_cl_args.log_level, g_logsdir_with_timestamped_subdir)

    g_logger.debug(f"args: {g_cl_args}")

    repos_metadata = make_repos_metadata(g_cl_args.repos_data, g_cl_args.default_source_branch,
                                         g_cl_args.default_dest_branch)
    g_logger.debug(f"repos_metadata: {repos_metadata}")
    errors = validate_repos_metadata(repos_metadata)
    if errors:
        g_logger.error(errors)
        sys.exit(1)

    os.makedirs(g_cl_args.repos_dir, exist_ok=True)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        errors = list(executor.map(execute_merge, repos_metadata))

    # with multiprocessing.Pool() as pool:
    #    errors = list(pool.map(execute_merge, repos_metadata))

    g_logger.debug(f"repos_metadata: {repos_metadata}")
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
