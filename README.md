# README #

# Manual

This script do merges in a list of repos. It was written to handle merges in projects comprising of
multiple Git repositories but with shared source- and dest-branch names.

The shared source- and dest-branch names can be given globally, but branch names specific to a repo
can also be given individually.

The merges are executed in concurrent merge tasks. For each task a logfile is written.

This script do not clone the repos. This is because you might post-process cloned repos before merging, e.g.
define merge drivers and register them in $GIT_DIR/info/attributes.

At the beginning of a task, an optional pre-script given in --pre-script can be executed. Also at the end
of a task an optional post-script given in --post-script can be executed.

Overview of commands the concurrent_git_merge.py executes internally always:

* {pre_script}, if given in --pre-script
* git reset --hard
* git clean -fd
* git checkout {dest_branch}
* Create merge branch and checkout, if --merge-branch-template is given.
* git merge --no-edit {merge_options} {source_ref | merge-branch}
* {post_script}, if given in --post-script

`concurrent_git_merge.py` works purely locally, but can orchestrate cloning or fetching using the pre-script,
and pushing and creating pull requests using the post-script.

# Simple example

    # It is assumed the repos are already cloned.
    # Default remote.
    : "${REMOTE=origin}"
    export REMOTE
    export BASE_URL_WITH_USERNAME="https://github.com/my-name"
    export COMMON_SOURCE_REF="${REMOTE}/parent-branch"
    export COMMON_DEST_BRANCH="child-branch"
    REPOS_DIR="./repos"
    LOGS_DIR="./logs/$(date +'%Y%m%d-%H%M%S')"    

    concurrent_git_merge.pyz \
      --repos-data \
      repo-a:$COMMON_SOURCE_REF:$COMMON_DEST_BRANCH:$BASE_URL_WITH_USERNAME/repo-a \
      repo-b:$COMMON_SOURCE_REF:$COMMON_DEST_BRANCH:$BASE_URL_WITH_USERNAME/repo-b \
      --default-source-ref "$COMMON_SOURCE_REF" \
      --default-dest-branch "$COMMON_DEST_BRANCH" \
      --merge-options "--no-ff -Xrenormalize -Xignore-space-at-eol" \
      --repos-dir "$REPOS_DIR" \
      --logs-dir "$LOGS_DIR" \
      --pre-script "bash -c 'git fetch --tags'" \
      --post-script "bash -c 'git push --set-upstream origin HEAD'"

# Complex example

Code example-scripts/my.

This demo combines two topics:

1. Demonstrate how to configure the concurrent_git_merge.py.
2. Demonstrate how to use a merge driver.

Directory content:

* clone_repos_and_install_mergedrivers.sh: pre-script cloning or fetching a repo, installing merge drivers.
* keep_ours_paths_merge_driver.pyz: Merge driver, located here but not checked-in.
  See [keep_ours_paths_merge_driver](https://github.com/gldog/keep_ours_paths_merge_driver).
* merge-demo.sh: Wrapper for concurrent_git_merge.pyz.
* post-script.sh: post-script pushing the result and creating a pull request URL.

The overall script merge-demo.sh configures and calls concurrent_git_merge.py.
concurrent_git_merge.py calls the pre-script, then triggers the `git merge`, then calls the post-script.
The `git merge` calls the merge driver.

# Command line reference

    $ python3 ../../src/concurrent_git_merge.py -h
    usage: concurrent_git_merge.py [-h] -r repo_local_name:[source_ref]:[dest_branch]:[prj/repo_remote_name]
                                   [repo_local_name:[source_ref]:[dest_branch]:[prj/repo_remote_name] ...] -d REPOS_DIR -o
                                   LOGS_DIR [-S DEFAULT_SOURCE_REF] [-D DEFAULT_DEST_BRANCH] [-m MERGE_OPTIONS]
                                   [-t MERGE_BRANCH_TEMPLATE] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                   [--pre-script PRE_SCRIPT] [--post-script POST_SCRIPT]
    
    This script do merges in a list of repos. It was written to handle merges in projects comprising of
    multiple Git repositories but with shared source- and dest-branch names.
    
    The shared source- and dest-branch names can be given globally, but branch names specific to a repo
    can also be given individually.
    
    The merges are executed in concurrent merge tasks. For each task a logfile is written.
    
    This script do not clone the repos. This is because you might post-process cloned repos before merging, e.g.
    define merge drivers and register them in $GIT_DIR/info/attributes.
    
    At the beginning of a task, an optional pre-script given in --pre-script can be executed. Also at the end
    of a task an optional post-script given in --post-script can be executed.
    
    Overview of commands the concurrent_git_merge.py executes internally always:
        {pre_script}, if given in --pre-script
        git reset --hard
        git clean -fd
        git checkout {dest_branch}
        Create merge branch and checkout, if --merge-branch-template is given.
        git merge --no-edit {merge_options} {source_ref|merge-branch}
        {post_script}, if given in --post-script
    
    optional arguments:
      -h, --help            show this help message and exit
      -r repo_local_name:[source_ref]:[dest_branch]:[prj/repo_remote_name] [repo_local_name:[source_ref]:[dest_branch]:[prj/repo_remote_name] ...], --repos-data repo_local_name:[source_ref]:[dest_branch]:[prj/repo_remote_name] [repo_local_name:[source_ref]:[dest_branch]:[prj/repo_remote_name] ...]
                            Information about the repos and branches to be processed. They are given as
                            positional parts, delimited by colon ':'.
                              1. 'repo_local_name', mandatory
                                  The name of the repo as it exists in the repos-directory.
                              2. 'source_ref', optional
                                  The branch/tag/commit to be merged into the dest-branch. If omitted it
                                  falls back to -S/--default-source-ref. At least one of the two must be
                                  given.
                              3. 'dest_branch', optional
                                  The branch to be updated from the source-ref. If omitted it falls back
                                  to -D/--default-dest-branch. At lest one of the two must be given.
                              4. 'prj/repo_remote_name', optional
                                  The remote project- and repo-name. Exposed as environment variable to
                                  the scripts given in --pre-script and --post-script.
                                  The 'prj'-part is the Bitbucket-project or the Github-username or the
                                  Gitlab-namespace.
                            The full notation is:
                                    -r repo_local_name:source_ref:dest_branch:prj/repo_remote_name
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
                                the scripts given in --pre-script and --post-script. Because the parts
                                are positional, the delimiters must be given.
                                    -r p1-m1:::products/product1-module1 \
                                       p1-m2:::products/product1-module2 \
                                    -S origin/master  -D my-feature \
                                    --pre-script clone_if_absent_and_install_merge-drivers.sh
      -d REPOS_DIR, --repos-dir REPOS_DIR
                            Directory the repos resides.
      -o LOGS_DIR, --logs-dir LOGS_DIR
                            Logs-directory.
      -S DEFAULT_SOURCE_REF, --default-source-ref DEFAULT_SOURCE_REF
                            Default source branch used for repos without given source-ref.
      -D DEFAULT_DEST_BRANCH, --default-dest-branch DEFAULT_DEST_BRANCH
                            Default destination branch used for repos without given dest-branch.
      -m MERGE_OPTIONS, --merge-options MERGE_OPTIONS
                            Options for git merge command. Must be given as one string, e.g.:
                              --merge-options '--no-ff -Xrenormalize -Xignore-space-at-eol'
                            The option --no-edit is always set internally.
      -t MERGE_BRANCH_TEMPLATE, --merge-branch-template MERGE_BRANCH_TEMPLATE
                            Create a merge-branch based on the dest-branch and do the merge in this
                            branch. If the merge-branch exists it will be reused. This allows continuing
                            a merge by calling the merge script again.
                            A merge-branch is typically used in case you're going to create a pull request
                            from the merge-result to an upstream-branch. Either because you want QA
                            on the PR, or you have no permission to merge into the target-branch
                            directly.
                            The template generating the name of the merge-branch is a jinja2-template
                            and understands the following placeholders:
                              o repo_local_name     From parameter -r/--repos-data the 1st part
                                                    'repo_local_name'.
                              o source_ref       From parameter -r/--repos-data the 2nd part
                                                    'source_ref', or the default-source-ref -S if
                                                    absent.
                              o dest_branch         From parameter -r/--repos-data the 3rd part
                                                    'dest-branch', or the default-dest-branch -D if
                                                    absent.
                              o prj_and_repo_remote_name    From parameter -r/--repos-data the 4th
                                                    part 'prj/repo-remote-name'.
                              o repo_data_from_parameter    From parameter -r/--repos-data the
                                                    complete string.
                              o task_start          The timestamp the repo's task has been started.
                            The task_start is of Python-type 'datetime'.
                            Example:
                                DATE_STR="$(date +'%Y%m%d')"
                                MERGE_BRANCH_TEMPLATE="--merge-branch-template merge/"
                                MERGE_BRANCH_TEMPLATE+="{{source_ref.replace('origin/','').replace('/', '_')}}"
                                MERGE_BRANCH_TEMPLATE+="_into_"
                                MERGE_BRANCH_TEMPLATE+="{{dest_branch.replace('/', '_')}}"
                                MERGE_BRANCH_TEMPLATE+="_$DATE_STR"
                                concurrent_git_merge.pyz \\
                                  --merge-branch-template "$MERGE_BRANCH_TEMPLATE" \\
                                  --logs-dir "./logs/$DATE_STRING" \\
                                  ... 
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Defaults to INFO.
      --pre-script PRE_SCRIPT
                            This script is executed at the beginning of each repo's merge-task. Here
                            you can clone the repos, install merge-drivers, and others. This script
                            doesn't run in the repo's directory. Therefore, Git-commands must be called 
                            with '-C $CGM_REPO_DIR', or you have to change to the repo's directory in
                            the script. This script runs in an environment with repo-specific environment
                            variables exposed:
                              o CGM_REPO_LOCAL_NAME From parameter -r/--repos-data the 1st part
                                                    'repo_local_name'.
                              o CGM_SOURCE_REF      From parameter -r/--repos-data the 2nd part
                                                    'source_ref', or the default-source-ref -S if
                                                    absent.
                              o CGM_DEST_BRANCH     From parameter -r/--repos-data the 3rd part
                                                    'dest-branch', or the default-dest-branch -D if
                                                    absent.
                              o CGM_PRJ_AND_REPO_REMOTE_NAME    From parameter -r/--repos-data the
                                                    4th part 'prj/repo-remote-name'.
                              o CGM_REPO_DATA_FROM_PARAMETER    From parameter -r/--repos-data the
                                                    complete string.
                              o CGM_TASK_START      The timestamp the repo's task has been started.
                              o CGM_MERGE_BRANCH    From parameter -m/--merge-branch-template if given,
                                                    with placeholders replaced.
                              o CGM_REPO_DIR        'repo_local_name' part of parameter -r/--repos-data,
                                                    prefixed with parameter -d.
                              o CGM_REPOS_DIR       From parameter -d/--repos-dir.
                              o CGM_LOGS_DIR        From parameter -o/--logs-dir.
                            For cloning you'll use CGM_REPOS_DIR, and for commands inside a repo you'll
                            use CGM_REPO_DIR.
                            On Windows and Gitbash you should call the script with 'bash -c script.sh'
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

# Merge use cases

Update child branch from parent branch:

    ------------------------------------------------------  Parent, SOURCE_REF
              \                  |
               \           merge |
                \                ↓
                 ----------------*------------------------  Child, DEST_BRANCH

Merge back child branch to parent branch:

    -----------------------------*------------------------  Parent, DEST_BRANCH
              \                  ↑
               \           merge |
                \                |
                 -----------------------------------------  Child, SOURCE_REF

Update child branch from parent branch using a merge branch and pull request:

    ------------------------------------------------------  Parent, SOURCE_REF
              \           1. merge ↓
               \           --------*----------------------  merge-branch (generated)
                \        /         M    ↓ 2. PR
                 -----------------------------------------  Child, DEST_BRANCH

Merge back child branch to parent branch using a merge branch and pull request:

    ------------------------------------------------------  Parent, DEST_BRANCH
              \          \              ↑ 2. PR
               \           --------*----------------------  merge-branch (generated)
                \         1. merge ↑ M
                 -----------------------------------------  Child, SOURCE_REF

# Create a fully self-contained executable zipapp

You can create a fully self-contained executable zipapp `concurrent_git_merge.pyz` with all dependencies bundled into
one
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
