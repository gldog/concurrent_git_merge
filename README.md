# README #

# Manual

    $ python3 ../../src/concurrent_git_merge.py -h
    usage: concurrent_git_merge.py [-h] -r repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name]
                              [repo_local_name:[source_branch]:[dest_branch]:[prj/repo_remote_name] ...] -d REPOS_DIR -o
                              LOGS_DIR [-S DEFAULT_SOURCE_BRANCH] [-D DEFAULT_DEST_BRANCH] [-m MERGE_OPTIONS]
                              [-t MERGE_BRANCH_TEMPLATE] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--pre-script PRE_SCRIPT]
                              [--post-script POST_SCRIPT]
    
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
        post_script, if given in --post-script
    
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
                                    -S origin/master  -D my-feature \
                                    -e clone_if_absent_and_install_merge-drivers.sh
      -d REPOS_DIR, --repos-dir REPOS_DIR
                            Directory the repos resides.
      -o LOGS_DIR, --logs-dir LOGS_DIR
                            Logs-directory.
      -S DEFAULT_SOURCE_BRANCH, --default-source-branch DEFAULT_SOURCE_BRANCH
                            Default source branch used for repos without given source-branch.
      -D DEFAULT_DEST_BRANCH, --default-dest-branch DEFAULT_DEST_BRANCH
                            Default destination branch used for repos without given dest-branch.
      -m MERGE_OPTIONS, --merge-options MERGE_OPTIONS
                            Options for git merge command. Must be given as one string, e.g.:
                              --merge-options '--no-ff -Xrenormalize -Xignore-space-at-eol'
                            The option --no-edit is always set internally.
      -t MERGE_BRANCH_TEMPLATE, --merge-branch-template MERGE_BRANCH_TEMPLATE
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
                                parameters+="_into_{{dest_branch}}_{{task_start.strftime('%Y%m%d-%H%M%S')}}"
                            The task's timestamps are very close to the one the script was started. But you might
                            prefer a guaranteed common timestamp for all merge-branches (and for the logs-dir):
                                DATE_STR="$(date +'%Y%m%d-%H%M%S')"
                                concurrent_git_merge.py \
                                  --merge-branch-template "merge/...$DATE_STR" \
                                  --logs-dir "./logs/$DATE_STRING" \
                                  ... 
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Defaults to INFO.
      --pre-script PRE_SCRIPT
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
                            text editor.
      --post-script POST_SCRIPT
                            This script is executed at the end of each repo's merge-task, regardless of the
                            merge result. Here you can push the result, create pull requests, and others.
                            This script doesn't run in the repo's directory (see --pre-script). This script
                            runs in an environment with repo-specific environment variables exposed as
                            described in --pre-script.
                            A most simple post-script parameter could be:
                                --post-script 'bash -c "git push --set-upstream origin HEAD"'
                            (The push --set-upstream can be executed multiple times without error.)

# Create a fully self-contained executable zipapp

You can create a fully self-contained executable zipapp `concurrent_git_merge.pyz` with all dependencies bundled into one
file. This allows simple distribution without letting the uses install dependencies.

In Linux and macOS:

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python -m shiv -c src -o concurrent_git_merge.pyz .

In Windows Gitbash:

    python -m venv venv
    source venv/Scripts/activate
    pip install -r requirements.txt
    # Parameter -p may differ on your system.
    python -m shiv -c src -p /c/Programme/Python3/python -o concurrent_git_merge.pyz .

In Windows CMD:

    python -m venv venv
    venv\Scripts\activate.bat
    pip install -r requirements.txt
    python -m shiv -c src -o concurrent_git_merge.pyz .
