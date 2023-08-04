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
        # The RawTextHelpFormatter allows leves newlines. This allows formatted output of the --repo-names description.
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=120),

        # -- 50 --------------- | ---------------------------------------------------------------- 100 -- #
        description=textwrap.dedent("""\
        This script do merges in a list of repos. For each repo, a source-branch and a dest-branch must be
        given. Source- and dest-branches can be given individually for each repo, and as defaults to be used
        in multiple repos sharing these branch-names.

        The merges are executed in parallel.

        This script do not clone the repos. This is because you might post-process cloned repo, e.g. install
        merge-drivers.

        Before each merge, an optional pre-merge-script can be executed, given in parameter
        -e/--exec-pre-merge-script. This script is executed in each repo's merge-task, means it runs parallel.
        Here you can clone the repos, install merge-drivers, and others.
        This script runs in an environment with following environment variables exported:
            o BASE_URL          As parameter -u
            o PROJECT_KEY       From parameter -n the 'PRJ' part
            o REPO_NAME         From parameter -n the 'REPO' part
            o SOURCE_BRANCH     From parameter -n the 'SOURCE_BRANCH' part, or the default-source-branch -S if absent
            o DEST_BRANCH       From parameter -n the 'DEST_BRANCH' part, or the default-dest-branch -D if absent
            o REPO_DIR          Parameter -d, extended by the 'REPO' part of parameter -n """))
    parser.add_argument('-u', '--base-url', help="Remote base URL.")
    parser.add_argument('-n', '--repo-names', required=True, nargs='+',
                        metavar='PRJ/REPO|PRJ/REPO:SOURCE_BRANCH:DEST_BRANCH',
                        # ---------------------------------------------------------------- 100 -- #
                        help=textwrap.dedent("""\
                        Names of the repos to be processed in the format prj/repo:source-branch:dest-branch.
                        'prj' means the bitbucket-project-key, and 'repo' the name of the cloned repo
                        in the filesystem.
                        Valid formats are:
                          o prj/repo:source-branch:dest-branch  (no defaults taken into account)
                          o prj/repo  (branches default to --default-source-branch and --default-dest-branch)
                          o prj/repo:source-branch:  (dest-branch omitted, defaults to --default-dest-branch)
                          o prj/repo::dest-branch  (source-branch omitted, defaults to --default-source-branch)
                          o prj/repo::  (same as PRJ/repo)
                        The repos given in this parameter should exist in --repos-dir. This script does
                        not clone missing repos. If a repo is missing, its merge will be skipped and an
                        error-message will be printed. But all existing repos will be merged."""))
    parser.add_argument('-d', '--repos-dir', required=True,
                        help="Directory the repos resides.")
    parser.add_argument('-o', '--logs-dir', required=True,
                        help=textwrap.dedent("""\
                        Log-directory. Each run of this script creates a subdirectory with a timestamp."""))
    parser.add_argument('-S', '--default-source-branch', default='',
                        help="Default source branch.")
    parser.add_argument('-D', '--default-dest-branch', default='',
                        help="Default destination branch.")
    parser.add_argument('-m', '--merge-branch-pattern',
                        help=textwrap.dedent("""\
                        Create a merge-branch based on the dest-branch and do the merge in this branch.
                        if the merge-branch exists it will be deleted and re-created.
                        The pattern understands the following placeholders:
                          o %%SBR           Source-branch name
                          o %%DBR           Dest-branch name
                          o %%DATE(format)  Date. For format see 'strftime() and strptime() Format Codes'
                                https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes.
                                E.g. %%DATE(%%d%%b) will be replaced with '01Jan'.
                                In a Unix shell you can also use $(date +%%d%%b). But the %%DATE()
                                placeholder is portable because Python does the formatting rather than an
                                external command."""))
    parser.add_argument('-l', '--log_level', choices=LOG_LEVELS, default=DEFAULT_LOGLEVEL,
                        help=f"Defaults to {DEFAULT_LOGLEVEL}.")
    parser.add_argument('-e', '--exec-pre-merge-script',
                        help="Execute this script for each repo before the merge starts.")

    return parser


def split_into_repo_metadata(repo: str):
    # Spit the parameter repo into project_key, repo_name, source_branch, dest_branch.
    #
    # A repo is given either bare 'prj/repo' or with source- and dest-branch 'prj/repo:source-branch:dest-branch'.
    # Emtpy branches are valid, they default to the default-source-branch or default-dest-branch.
    # Valid forms of repo are:
    #   o prj/repo:source-branch:dest-branch  (no defaults taken into account)
    #   o prj/repo  (branches default to --default-source-branch and --default-dest-branch)
    #   o prj/repo:source-branch:  (dest-branch omitted, defaults to --default-dest-branch)
    #   o prj/repo::dest-branch  (source-branch omitted, defaults to --default-source-branch)
    #   o prj/repo::  (same as PRJ/repo)
    #
    parts = re.split(':', repo)
    error_msg = f"Given repo '{repo}' has unexpected format. " + \
                "See help for parameter -n/--repo-names for accepted formats."
    if len(parts) not in [1, 3]:
        raise ValueError(error_msg)
    project_and_repo = parts[0].strip()
    if not project_and_repo:
        raise ValueError(error_msg)
    url_parts = re.split('/', project_and_repo)
    if not len(url_parts) == 2:
        # Expect e.g. 'PRJ/repo'
        raise ValueError(error_msg)
    project_key = url_parts[0].strip()
    repo_name = url_parts[1].strip()
    if not project_key or not repo_name:
        raise ValueError(error_msg)
    if len(parts) == 3:
        source_branch = parts[1].strip()
        dest_branch = parts[2].strip()
    else:
        source_branch = ''
        dest_branch = ''
    return project_key, repo_name, source_branch, dest_branch


def make_repos_metadata(repos: List[str], default_source_branch: str, default_dest_branch: str):
    """
    Transform the repos given in command line parameter -n/--repo-names into dict of following format:

        [
            {
                'project_key': 'prj1',
                'repo_name': 'repo1',
                'source_branch':
                'stable-tag-1',
                'dest_branch': 'my-feature-branch'
            },
            {
                'project_key': 'prj1',
                'repo_name': 'repo2',
                'source_branch':
                'stable-tag-1',
                'dest_branch': 'my-feature-branch'
            },
            ...
        ]
    """
    default_source_branch = default_source_branch.strip()
    default_dest_branch = default_dest_branch.strip()
    repos_metadata = []
    for repo in repos:
        project_key, repo_name, source_branch, dest_branch = split_into_repo_metadata(repo)
        if not source_branch:
            source_branch = default_source_branch
        if not dest_branch:
            dest_branch = default_dest_branch
        repos_metadata.append(
            {'project_key': project_key, 'repo_name': repo_name,
             'source_branch': source_branch, 'dest_branch': dest_branch})
    return repos_metadata


def validate_repos_metadata(repos_metadata):
    """
    Check for completeness of each repo's metadata.

    Each repo needs a source-branch and a dest-branch. They can be given in parameter -n/--repo-names, or as default
    in -S/--default-source-branch and -D/--default-dest-branch. But if not given, the merge can't be started. This
    is an configuration error.
    """
    error = None
    for repo_metadata in repos_metadata:
        project_key = repo_metadata['project_key']
        repo_name = repo_metadata['repo_name']
        if not repo_metadata['source_branch']:
            error = f"Missing source-branch for repo '{project_key}/{repo_name}'"
        if not repo_metadata['dest_branch']:
            error = f"Missing dest-branch for repo '{project_key}/{repo_name}'"
    return error


def log_task(logfile_name: str, logfile_content: str):
    logfile_path = pathlib.Path(g_logsdir_with_timestamped_subdir, logfile_name)
    with open(logfile_path, 'a', newline='') as f:
        f.write(logfile_content)


def run_command(command, command_shorten_for_log, repo_displayname_for_log, logfile_name, honor_returncode=True,
                env=None):
    g_logger.info(f"{repo_displayname_for_log}: $ {command_shorten_for_log}")
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
        command_shorten_for_log = command.replace(remove_str, '')
        run_command(command, command_shorten_for_log, repo_displayname_for_logging, logfile_name)


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
    project_key = repo_metadata['project_key']
    repo_name = repo_metadata['repo_name']
    source_branch = repo_metadata['source_branch']
    dest_branch = repo_metadata['dest_branch']
    logfile_name = f'{project_key}--{repo_name}.log'
    g_logger.info(f"Started merge-task for {project_key}/{repo_name}.")
    log_task(logfile_name, f"Started merge-task for {project_key}/{repo_name}.")

    task_finish_status = "successfully"
    try:
        global g_cl_args
        repo_dir = pathlib.Path(g_cl_args.repos_dir, repo_name)
        repo_displayname_for_logging = f'{project_key}/{repo_name}'

        if g_cl_args.exec_pre_merge_script:
            env = os.environ.copy()
            env['REPOS_DIR'] = g_cl_args.repos_dir
            if g_cl_args.base_url:
                env['BASE_URL'] = g_cl_args.base_url.rstrip('/')
            env['PROJECT_KEY'] = project_key
            env['REPO_NAME'] = repo_name
            env['SOURCE_BRANCH'] = source_branch
            env['DEST_BRANCH'] = dest_branch
            env['REPO_DIR'] = str(repo_dir)
            command = g_cl_args.exec_pre_merge_script
            run_command(command, command, repo_displayname_for_logging, logfile_name, env=env)

        # The repo is expected to be present.
        if not pathlib.Path(repo_dir, '.git').is_dir():
            raise Exception(
                f"Repo '{project_key}/{repo_name}' is given in parameter -n/--repo-names, " +
                f"but it is missing in {g_cl_args.repos_dir} given in parameter -d/--repos-dir.")

        commands = [
            f'git -C {repo_dir} reset --hard',
            f'git -C {repo_dir} clean -fd',
            f'git -C {repo_dir} checkout {dest_branch}',
            f'git -C {repo_dir} pull --ff'
        ]
        run_commands(commands, f' -C {repo_dir}', repo_displayname_for_logging, logfile_name)

        if g_cl_args.merge_branch_pattern:
            merge_branch = make_mergebranch_name(g_cl_args.merge_branch_pattern, source_branch, dest_branch)
            # Delete the merge-branch if it exists.
            command = f'git -C {repo_dir} show-ref --verify --quiet refs/heads/{merge_branch}'
            command_shorten_for_log = command.replace(f' -C {repo_dir}', '')
            r = run_command(command, command_shorten_for_log, repo_displayname_for_logging, logfile_name,
                            honor_returncode=False)
            commands.clear()
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
        g_logger.info(f"Finished merge-task for {project_key}/{repo_name} {task_finish_status}.")
        log_task(logfile_name, f"Finished merge-task for {project_key}/{repo_name} {task_finish_status}.")
        log_task(logfile_name, f"Merge-task statistics:\n{json.dumps(repo_metadata, indent=2)}")


def get_formatted_timediff_mmss(time_diff: timedelta) -> str:
    """Convert the given time_diff to format "MM:SS". If the time-diff is < 1s, overwrite it to 1s.
    The MM can be > 60 min.
    :param time_diff: The time-diff
    :return: Time-diff in MM:SS, but min. 1s.
    """

    # Convert to integer because nobody will be interested in the milliseconds-precision. If the diff is 0,
    # overwrite it to 1 (second).
    s = int(time_diff.total_seconds())
    if s == 0:
        s = 1
    minutes = s // 60
    seconds = s % 60
    formatted_diff = f'{minutes:02d}:{seconds:02d}'

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

    repos_metadata = make_repos_metadata(g_cl_args.repo_names, g_cl_args.default_source_branch,
                                         g_cl_args.default_dest_branch)
    g_logger.debug(f"repos_metadata: {repos_metadata}")
    error = validate_repos_metadata(repos_metadata)
    if error:
        g_logger.error(error)
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
