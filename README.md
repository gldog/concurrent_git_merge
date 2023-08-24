# README #

    $ python src/merge_git_repos.py -h
    usage: merge_git_repos.py [-h] -r repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name]
                              [repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name] ...] -d REPOS_DIR -o
                              LOGS_DIR [-S DEFAULT_SOURCE_BRANCH] [-D DEFAULT_DEST_BRANCH] [-m MERGE_BRANCH_TEMPLATE]
                              [--local] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-e EXEC_PRE_MERGE_SCRIPT]
    
    This script do merges in a list of repos. For each repo, a source-branch and a dest-branch must be
    given. Source- and dest-branches can be given individually for each repo, and as defaults to be
    used in multiple repos sharing these branch-names.
    
    The merges are executed in parallel. For each task a logfile is written.
    
    This script do not clone the repos. This is because you might post-process cloned repos, e.g.
    install merge-drivers.
    
    Before each merge, an optional pre-merge-script can be executed, given in parameter
    -e/--exec-pre-merge-script.
    
    optional arguments:
      -h, --help            show this help message and exit
      -r repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name] [repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name] ...], --repos-data repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name] [repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name] ...]
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
                                    -r product1-module1 product1-module2 \
                                        -S origin/master -D my-feature
                                That is the short notation. As the parts are delimited by colon ':',
                                the full also valid notation would be:
                                    -r product1-module1::: product1-module2::: \
                                        -S origin/master -D my-feature
                            3) As example 2), but with abbreviated local repo-names, and
                                'prj/repo_remote_name' given as named on the remote, to be exposed to
                                the pre-merge-script. Because the parts are positional, the delimiters
                                must be given.
                                    -r p1-m1:::products/product1-module1 \
                                       p1-m2:::products/product1-module2 \
                                       -S origin/master -D my-feature \
                                       -e clone_if_absent_and_install_merge-drivers.sh
      -d REPOS_DIR, --repos-dir REPOS_DIR
                            Directory the repos resides.
      -o LOGS_DIR, --logs-dir LOGS_DIR
                            Log-directory. Each run of this script creates a subdirectory with a
                            timestamp.
      -S DEFAULT_SOURCE_BRANCH, --default-source-branch DEFAULT_SOURCE_BRANCH
                            Default source branch used for repos without given source-branch.
      -D DEFAULT_DEST_BRANCH, --default-dest-branch DEFAULT_DEST_BRANCH
                            Default destination branch used for repos without given dest-branch.
      -m MERGE_BRANCH_TEMPLATE, --merge-branch-template MERGE_BRANCH_TEMPLATE
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
                                parameters+="_into_{{dest_branch}}_{{task_start.strftime('%b%d')}}" 
      --local               Skip the git pull command. Allows to merge a local-only source-branch that
                            has no tracking remote-branch.
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Defaults to INFO.
      -e EXEC_PRE_MERGE_SCRIPT, --exec-pre-merge-script EXEC_PRE_MERGE_SCRIPT
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
                                                    'repo_local_name' part of parameter -r/--repos-data.
