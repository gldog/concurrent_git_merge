# README #

    usage: merge_git_repos.py [-h] -r repo-local-name:[source-branch]:[dest-branch]:[prj/repo-remote-name]
                              [repo-local-name:[source-branch]:[dest-branch]:[prj/repo-remote-name] ...] -d REPOS_DIR -o
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
      -r repo-local-name:[source-branch]:[dest-branch]:[prj/repo-remote-name] [repo-local-name:[source-branch]:[dest-branch]:[prj/repo-remote-name] ...], --repos-data repo-local-name:[source-branch]:[dest-branch]:[prj/repo-remote-name] [repo-local-name:[source-branch]:[dest-branch]:[prj/repo-remote-name] ...]
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
                                    -r product1-module-a product1-module-b \
                                        -S origin/master -D my-feature
                                That is the short notation. As the parts are delimited by colon ':',
                                the full also valid notation would be:
                                    -r product1-module-a::: product1-module-b::: \
                                        -S origin/master -D my-feature
                            3) As example 2), but with abbreviated local repo-names, and
                                'prj/repo-remote-name' given to be exposed to the pre-merge-script as
                                named on the remote. Because the parts are positional, the delimiters
                                must be given.
                                    -r p1-m-a:::products/product1-module-a \
                                       p1-m-b:::products/product1-module-a \
                                       -S origin/master -D my-feature \
                                       -e clone_if_absent_and_install_merge-drivers.sh
      -d REPOS_DIR, --repos-dir REPOS_DIR
                            Directory the repos resides.
      -o LOGS_DIR, --logs-dir LOGS_DIR
                            Log-directory. Each run of this script creates a subdirectory with a
                            timestamp.
      -S DEFAULT_SOURCE_BRANCH, --default-source-branch DEFAULT_SOURCE_BRANCH
                            Default source branch used for repos without given source-branch .
      -D DEFAULT_DEST_BRANCH, --default-dest-branch DEFAULT_DEST_BRANCH
                            Default destination branch used for repos without given dest-branch.
      -m MERGE_BRANCH_TEMPLATE, --merge-branch-template MERGE_BRANCH_TEMPLATE
                            Create a merge-branch based on the dest-branch and do the merge in this
                            branch. If the merge-branch exists it will be deleted and re-created.
                            The template generating the name of the merge-branch understands the
                            following placeholders (rm means repo-metadata):
                              o rm['dest_branch']       Dest-branch name.
                              o rm['branch_branch']     From parameter -m/--merge-branch-template if given.
                              o rm['prj_and_repo_remote_name']  From parameter -r/--repos-data, the 4th
                                                        part.
                              o rm['repos_dir']         From parameter -d/--repos-dir.
                              o rm['repo_dir']          From parameter -d/--repos-dir, supplemented by
                                                        the repo_local_name.
                              o rm['repo_local_name']   From parameter -r/--repos-data, the 1st part.
                              o rm['source_branch']     Source-branch name.
                              o rm['task_start']        Timestamp the repo's task started (Python
                                                        datetime object).
                            The rm['task_start'] is of Python type datetime. strftime() can be used to
                                                        generate a pretty-print timestamp.
                            An example to be used in a  bash-script:
                                parameters=" --merge-branch-template"
                                parameters+=" merge/from_{rm['source_branch'].replace('origin/','')}"
                                parameters+="_into_{rm['dest_branch']}_{rm['task_start'].strftime('%b%d')}" 
      --local               Skip the git pull command. Allows to merge a local-only source-branch that
                            has no tracking remote-branch.
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Defaults to INFO.
      -e EXEC_PRE_MERGE_SCRIPT, --exec-pre-merge-script EXEC_PRE_MERGE_SCRIPT
                            This script is executed in each repo's merge-task, means it runs parallel.
                            Here you can clone the repos, install merge-drivers, and others.
                            This script runs in an environment with repo-specific environment variables
                            exposed:                        
                            o MR_DEST_BRANCH        From parameter -r the 'dest-branch' part, or the
                                                    default-dest-branch -D if absent.
                            o MR_MERGE_BRANCH       From parameter -m/--merge-branch-template if given.
                            o MR_PRJ_AND_REPO_REMOTE_NAME   From parameter -r the part 'prj/repo-remote-name'.
                            o MR_REPOS_DIR          From parameter -d/--repos-dir. 
                            o MR_REPO_DATA_FROM_PARAMETER   From parameter -r/--repos-data.
                            o MR_REPO_DIR           Parameter -d, extended by a timestamp and the
                                                    'repo-local-name' part of parameter -r. 
                            o MR_REPO_LOCAL_NAME    From parameter -r the 'repo-local-name' part.
                            o MR_SOURCE_BRANCH      From parameter -r the 'source-branch' part, or the
                                                    default-source-branch -S if absent.
                            o MR_TASK_START         Timestamp the repo's task has been started. 
