#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|

set -u
#
# This script demonstrates the usage of concurrent_git_merge.py in combination of the merge driver
# keep_ours_paths_merge_driver (https://github.com/gldog/keep_ours_paths_merge_driver).
# The demo comprises of:
#   - This script merge-demo.sh
#       Set source- and dest-branches, and others.
#   - concurrent_git_merge.py (or the zipapp concurrent_git_merge.pyz)
#   - The pre-script clone_repos_and_install_mergedrivers.sh, called per repo.
#       Clones a repo if absent, installs merge drivers.
#   - The post-script post_merge.sh, called per repo.
#       Logs commit-diff, pushes merge commit, creates pull request URL
#
#   Examples for source branches, demonstrated with with COMMON_SOURCE_REF:
#
#   # The source branch is a branch, not a tag. The branch exists as remote branch in the clone,
#   but might not exist as local branch yet:
#   REMOTE="origin"
#   COMMON_SOURCE_REF=${REMOTE}/release/2.0
#
#   # The source branch is a branch, not a tag. The branch does definitely exist as local branch:
#   COMMON_SOURCE_REF=release/2.0
#
#   # The source branch is a tag. Tags are present after git clone or git fetch, the remote is not
#   # needed.
#   COMMON_SOURCE_REF=stable-build-4
#
#
# In pre-script, REMOTE is used as "pure" remote name, not as a prefix, and must not have any
# trailing slash. But removing a slash handles the pre-script itself.
# This allows setting the REMOTE with or without slash from external.
: "${REMOTE=origin/}"
export REMOTE
export COMMON_SOURCE_REF="${REMOTE}childbranch_packagejson_version_changed"
export COMMON_DEST_BRANCH="parentbranch_packagejson_version_changed"
#
#
#   The merge driver keep_ours_paths_merge_driver knows the merge-strategies "onconflict-ours"
#   and "always-ours". The default is "onconflict-ours".
#   For merges from parent to child branch choose "onconflict-ours". For merges from child to
#   parent choose "always-ours".
#   The terms "onconflict-ours" and "always-ours" relates to XPaths or JSON-paths in question,
#   not for all merge conflicts.
#
# Value for merge from parent branch to child branch.
# It is exported because the pre-script uses it (but its default is "onconflict-ours").
#
#export MERGE_DRIVER_MERGE_STRATEGY="onconflict-ours"
#
# Value for merge from child branch to parent branch.
#
export MERGE_DRIVER_MERGE_STRATEGY="always-ours"
#

# Used in pre-script, defaults to https://github.com.
export BASE_URL="https://bitbucket.org"
REPOS_DIR="./repos"
DATE_STRING_FOR_LOGS_DIR="$(date +'%Y%m%d-%H%M%S')"
LOGS_DIR="./logs/$DATE_STRING_FOR_LOGS_DIR"

# Test, they default to true in post-script.
: "${IS_PUSH_AFTER_MERGE:=false}"
: "${IS_CREATE_PULL_REQUEST_URLS:=false}"
export IS_PUSH_AFTER_MERGE
export IS_CREATE_PULL_REQUEST_URLS

# For repeating the same merge, set the date of the already created merge-branch here manually.
# A date granularity of "day" (without hours and minutes) achieves this if repeated merges are
# executed on the same day. Or without any date-part at all.
# For testing is could make sense to have one branch per execution which is achieved using a
# granularity of seconds.
#: "${DATE_STRING_FOR_MERGE_BRANCH:=$(date +'%Y%m%d-%H%M%S')}"
: "${DATE_STRING_FOR_MERGE_BRANCH:=$(date +'%Y%m%d')}"

# Jinja2 template.
# The source- and dest-branches can be distinct to each repo when different to the default branches.
# So the concurrent_git_merge.py has to create the merge-branch name (if either source- or dest-branch, or
# both, should be part of the name).
MERGE_BRANCH_TEMPLATE="--merge-branch-template "
MERGE_BRANCH_TEMPLATE+="merge/"
MERGE_BRANCH_TEMPLATE+="{{source_ref.replace('origin/','').replace('/','_')}}"
MERGE_BRANCH_TEMPLATE+="__into__"
MERGE_BRANCH_TEMPLATE+="{{dest_branch.replace('/','_')}}"
MERGE_BRANCH_TEMPLATE+="__$DATE_STRING_FOR_MERGE_BRANCH"

#MERGE_BRANCH_TEMPLATE="--merge-branch-template merge-branch"
#MERGE_BRANCH_TEMPLATE=""

# The file where the pull request URLs are collected.
# The LOGS_DIR is not yet created, create it.
mkdir -p "$LOGS_DIR"
PULL_REQUEST_URLS_FILE="$LOGS_DIR/pull-request-urls.txt"

# For testing and using a static log-dir: Make file empty. Create a new empty file rather than
# printing one empty line into it, because later one the lines of pull request URLs are counted.
rm -f "$PULL_REQUEST_URLS_FILE"
touch "$PULL_REQUEST_URLS_FILE"

# Register the merge drivers in <repo>/.git/info/attributs rather than rely on <repo>/.gitattributes.
export IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES=true

# The merge driver executable. Only used in pre-script. But defined here to fail-fast in case it is
# not callable.
export MERGE_DRIVER_EXECUTABLE="keep_ours_paths_merge_driver.pyz"

# Make Git (called by concurrent_git_merge.py) and the pre-script find the merge driver.
# Setting the PATH in the pre-script is not sufficient, as Git must find it, and Git is called by
# concurrent_git_merge.py
PATH=$(pwd):$PATH
export PATH

if ! which "$MERGE_DRIVER_EXECUTABLE" >/dev/null; then
  echo "ERROR: Can't execute $MERGE_DRIVER_EXECUTABLE. Is it on PATH?"
  exit 1
fi

#rm -rf "$REPOS_DIR"

#
# About some options
#
# --repos-data:
#
#   Information about the repos and branches to be processed. They are given as
#   positional parts, delimited by colon ':'.
#     1. 'repo_local_name', mandatory
#       The name of the repo as it exists in the repos-directory.
#     2. 'source_ref', optional
#       The branch to be merged into the dest-branch. If omitted it falls
#       back to -S/--default-source-ref. At least one of the two must be
#       given.
#     3. 'dest_branch', optional
#       The branch to be updated from the source-ref. If omitted it falls
#       back to -D/--default-dest-branch. At lest one of the two must be given.
#     4. 'prj/repo_remote_name', optional
#       The remote project- and repo-name. Exposed as environment variable to
#       the script given in --pre-script.
#       The 'prj'-part is the Bitbucket-project or the Github-username or the
#       Gitlab-namespace.
#
# --pre-script, --post-script:
#
#   The "bash -c" is needed in Gitbash, and can be omitted otherwise.
#
# --post-script:
#
#   One simple universal command for pushing the current branch:
#       'bash -c "git push --set-upstream origin HEAD"'
#

#../../concurrent_git_merge.pyz \
python ../../src/concurrent_git_merge.py \
  --repos-data \
  mdtr:$COMMON_SOURCE_REF:$COMMON_DEST_BRANCH:jheger/mergedriver-testrepo \
  --default-source-ref "$COMMON_SOURCE_REF" \
  --default-dest-branch "$COMMON_DEST_BRANCH" \
  $MERGE_BRANCH_TEMPLATE \
  --merge-options "--no-ff -Xrenormalize -Xignore-space-at-eol" \
  --repos-dir "$REPOS_DIR" \
  --logs-dir "$LOGS_DIR" \
  --log-level INFO \
  --pre-script "bash -c clone_repos_and_install_mergedrivers.sh" \
  --post-script "bash -c post_merge.sh"

exit_code=$?

# Start logging all output to console and logfile.
# out.log is defined by concurrent_git_merge.py.
#exec > >(tee -a "${LOGS_DIR}/out.log") 2>&1

echo ""
if [[ $exit_code != 0 ]]; then
  echo "ERROR: $0 finished with exit code $exit_code. Look at the logs."
  exit $exit_code
else
  echo "$0 finished with exit code 0."
fi

#
# Handle pull requests.
# Each merge-task potentially creates a pull request URL and writes it to PULL_REQUEST_URLS_FILE.
#
# I don't know if the "sleep 0.5" is really needed. But in my calls against Bitbucket Server I got
# (once) somthing about "Server did not response" or so. Maybe the sleep is more polite and
# prevents this.
if [[ "$IS_CREATE_PULL_REQUEST_URLS" == true ]]; then
  pr_url_count=$(wc -l <"$PULL_REQUEST_URLS_FILE")
  if ((pr_url_count != 0)); then
    echo ""
    echo "Script prepared $((pr_url_count)) pull request URLs in $PULL_REQUEST_URLS_FILE."
    sort -o "$PULL_REQUEST_URLS_FILE" "$PULL_REQUEST_URLS_FILE"
    # 'read' returns a non-zero exit code.
    set +e
    read -r -d '' footer <<EOF
Create Pull-Requests separately:
Each instance of --post-script created a pull-request-URL in case there was a commit-diff to be
pushed to the remote. The pull request URL was appended to the common file '$PULL_REQUEST_URLS_FILE'.
You can create all pull-requests at once calling one of the following commands.
  - In Gitbash or cmd.exe:  cat $PULL_REQUEST_URLS_FILE | xargs -t -I{} bash -c "start '{}' ; sleep 0.5"
  - Otherwise:              cat $PULL_REQUEST_URLS_FILE | xargs -t -I{} bash -c "open '{}' ; sleep 0.5"
If 'open' doesn't work in your Linux, try 'xdg-open' or 'browse'.
EOF
    set -e
    echo ""
    echo "$footer"
  fi
fi

echo ""
