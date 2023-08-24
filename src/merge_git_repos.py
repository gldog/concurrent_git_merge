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

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
DEFAULT_LOGLEVEL = 'INFO'
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]

g_script_start = datetime.now()
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
                                The branch to be updated from the source-branch. If omitted it
                                falls back to -D/--default-dest-branch. At lest one of the two must
                                be given.
                            4. 'prj/repo_remote_name', optional
                                The remote project- and repo-name. Exposed as environment variable
                                to the script given in -e/--exec-pre-merge-script.
                                The 'prj'-part is the Bitbucket-project or the Github-username or 
                                the Gitlab-namespace.
                        The full notation is:
                                -r repo_local_name:source_branch:dest_branch:prj/repo_remote_name
                        Optional parts may be empty:
                                -r repo_local_name:::
                        Delimiters of empty parts can be omitted from right to left.
                        The above parameter can be given as:
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
                                   -S origin/master -D my-feature \\
                                   -e clone_if_absent_and_install_merge-drivers.sh"""))
    parser.add_argument('-d', '--repos-dir', required=True,
                        help="Directory the repos resides.")
    parser.add_argument('-o', '--logs-dir', required=True,
                        help=textwrap.dedent("""\
                        Log-directory. Each run of this script creates a subdirectory with a
                        timestamp."""))
    parser.add_argument('-S', '--default-source-branch', default='',
                        help="Default source branch used for repos without given source-branch.")
    parser.add_argument('-D', '--default-dest-branch', default='',
                        help="Default destination branch used for repos without given dest-branch.")
    parser.add_argument('-m', '--merge-branch-template',
                        help=textwrap.dedent("""\
                        Create a merge-branch based on the dest-branch and do the merge in this
                        branch. If the merge-branch exists it will be deleted and re-created.
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
                        The task_start is of Pythontype 'datetime'. strftime() can be used to
                        generate a pretty-print timestamp.
                        An example to be used in a  bash-script:
                            parameters=" --merge-branch-template"
                            parameters+=" merge/from_{{source_branch.replace('origin/','')}}"
                            parameters+="_into_{{dest_branch}}_{{task_start.strftime('%%b%%d')}}" 
                            """))
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
                        o MGR_REPO_LOCAL_NAME   From parameter -r/--repos-data the 1st part
                                                'repo_local_name'.
                        o MGR_SOURCE_BRANCH     From parameter -r/--repos-data the 2nd part 
                                                'source_branch', or the default-source-branch -S if
                                                absent.
                        o MGR_DEST_BRANCH       From parameter -r/--repos-data the 3rd part 
                                                'dest-branch', or the default-dest-branch -D if
                                                absent.
                        o MGR_PRJ_AND_REPO_REMOTE_NAME  From parameter -r/--repos-data the 4th
                                                part 'prj/repo-remote-name'.
                        o MGR_REPO_DATA_FROM_PARAMETER  From parameter -r/--repos-data the
                                                complete string.
                        o MGR_TASK_START        The timestamp the repo's task has been started.
                        o MGR_MERGE_BRANCH      From parameter -m/--merge-branch-template if given,
                                                with placeholders replaced.
                        o MGR_REPOS_DIR         From parameter -d/--repos-dir. 
                        o MGR_REPO_DIR          From parameter -d, extended by a timestamp and the
                                                'repo_local_name' part of parameter -r/--repos-data. """))

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


def make_mergebranch_name(merge_branch_template, repo_metadata):
    """
    Make the formatted string, with values from "repo_metadata" replaced.

    Example:

    The following bash-script composes the command line for merge_git_repos.py. The last two "parameters+=" lines
    defines the template for the merge-branch.

        #!/bin/bash
        parameters=" --repos-data"
        parameters+=" mb:origin/master:test-feature-branch:prj/repo1"
        parameters+=" td:origin/master:test-feature-branch:prj/repo2"
        parameters+=" --repos-dir $REPOS_DIR"
        parameters+=" --logs-dir $LOGS_DIR"
        parameters+=" --log-level DEBUG"
        parameters+=" --exec-pre-merge-script clone_repos_and_install_merge-drivers.sh"
        parameters+=" --merge-branch-template maintain/dsm_{{source_branch.replace('origin/','')}}"
        parameters+="_into_{{dest_branch}}_{{task_start.strftime('%b%d')}}"
        python3 ../../src/merge_git_repos.py $parameters

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
    repo_metadata['repos_dir'] = g_cl_args.repos_dir

    if g_cl_args.merge_branch_template:
        repo_metadata['merge_branch'] = make_mergebranch_name(g_cl_args.merge_branch_template, repo_metadata)

    logfile_name = f'repo--{repo_local_name}.log'
    log_msg = f"Started merge-task for {repo_local_name}."
    g_logger.info(log_msg)
    log_task(logfile_name, f"{log_msg}\n")
    log_task(logfile_name, "repo_metadata at task-begin:\n" +
             f"{json.dumps(repo_metadata, indent=2, default=serialize_datetime_or_propagate)}\n")

    task_finish_status = "successfully"
    # try: run_command() might raise an exception.
    try:
        repo_displayname_for_logging = repo_local_name
        if g_cl_args.exec_pre_merge_script:
            env = os.environ.copy()
            # Expose all members of repo_metadata as environment-vars, prefixed with "MGR_".
            for key, value in repo_metadata.items():
                env_var_name = f"MGR_{key.upper()}"
                if isinstance(value, datetime):
                    value = value.isoformat()
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

        if g_cl_args.merge_branch_template:
            # Delete the merge-branch if it exists.
            command = f'git -C {repo_dir} show-ref --verify --quiet refs/heads/{repo_metadata["merge_branch"]}'
            command_pretty_print_for_log = command.replace(f' -C {repo_dir}', '')
            r = run_command(command, command_pretty_print_for_log, repo_displayname_for_logging, logfile_name,
                            honor_returncode=False)
            if r.returncode == 0:
                commands.append(f'git -C {repo_dir} branch -D {repo_metadata["merge_branch"]}')
            else:
                log_task(logfile_name, "  (Merge-branch not present)\n\n")
            commands.append(f'git -C {repo_dir} checkout -b {repo_metadata["merge_branch"]}')

        commands.append(
            f'git -C {repo_dir} merge --no-ff --no-edit -Xrenormalize -Xignore-space-at-eol {source_branch}')
        run_commands(commands, f' -C {repo_dir}', repo_displayname_for_logging, logfile_name)

    except Exception as e:
        task_finish_status = "with error"
        return str(e)
    finally:
        task_end_timestamp = datetime.now()
        repo_metadata['task_end'] = task_end_timestamp
        task_duration = task_end_timestamp - task_start_timestamp
        repo_metadata['task_duration'] = str(task_duration)
        log_msg = f"Finished merge-task for '{repo_local_name}' {task_finish_status}."
        g_logger.info(log_msg)
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


def exit_handler():
    g_logger.info(f"Script finished, took {get_formatted_timediff_mmss(datetime.now() - g_script_start)}")


def main():
    atexit.register(exit_handler)

    cl_parser = init_argument_parser()
    global g_cl_args
    g_cl_args = cl_parser.parse_args()

    # The g_logsdir_with_timestamped_subdir can't be set at the beginning of the script because it contains data
    # from the arg-parser.
    global g_logsdir_with_timestamped_subdir
    start_timestamp_formatted_str = g_script_start.strftime('%Y%m%d-%H%M%S')
    g_logsdir_with_timestamped_subdir = pathlib.Path(g_cl_args.logs_dir, start_timestamp_formatted_str)
    os.makedirs(g_logsdir_with_timestamped_subdir, exist_ok=True)

    configure_logger(g_cl_args.log_level, g_logsdir_with_timestamped_subdir)

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
