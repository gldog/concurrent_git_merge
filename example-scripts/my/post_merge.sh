#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|
#
# Post-script for concurrent_git_merge.py
#
# TODO Description
#
# This script is called by concurrent_git_merge.py using parameter --post-script.

set -eu
#set -x

trap on_error ERR

function on_error() {
  echo "$0 for repo $MGR_REPO_DIR exited with FAILURE."
}

# For testing it could be useful to not push the merge-commit or the merge-branch.
: "${IS_PUSH_AFTER_MERGE:=true}"
: "${IS_CREATE_PULL_REQUEST_URLS:=true}"

# If concurrent_git_merge.py is called in Git-Bash, Python thinks it runs in a Windows environment and
# creates Windows-style paths. Make the paths Unix-style-paths.
export MGR_REPOS_DIR="${MGR_REPOS_DIR//\\//}"
export MGR_LOGS_DIR="${MGR_LOGS_DIR//\\//}"
export MGR_REPO_DIR="${MGR_REPO_DIR//\\//}"

echo ""
echo "# MGR_REPOS_DIR                 $MGR_REPOS_DIR"
echo "# MGR_LOGS_DIR:                 $MGR_LOGS_DIR"
echo "# MGR_REPO_DIR                  $MGR_REPO_DIR"
echo "# MGR_SOURCE_BRANCH:            $MGR_SOURCE_BRANCH"
echo "# MGR_DEST_BRANCH               $MGR_DEST_BRANCH"
echo "# IS_PUSH_AFTER_MERGE:          $IS_PUSH_AFTER_MERGE"
echo "# IS_CREATE_PULL_REQUEST_URLS:  $IS_CREATE_PULL_REQUEST_URLS"

PULL_REQUEST_URLS_FILE="$MGR_LOGS_DIR/pull-request-urls.txt"

echo "# PULL_REQUEST_URLS_FILE:       $PULL_REQUEST_URLS_FILE"

echo ""
cmd="git -C $MGR_REPO_DIR status"
echo "\$ $cmd"
eval "$cmd"

# In a clean workspace the following command prints nothing than a newline.
echo "# Check for merge conflict."
cmd="git -C $MGR_REPO_DIR status --porcelain"
echo "\$ $cmd"
git_status_output=$(eval "$cmd")
echo "$git_status_output"

if [[ ! -z "$git_status_output" ]]; then
  echo "ERROR: There is a merge conflict or the workspace not clean."
  exit 1
fi

echo ""
echo "# No merge conflict."

echo ""
echo "# The merge-commit is:"
cmd="git -C $MGR_REPO_DIR log -1"
echo "\$ $cmd"
eval "$cmd"

echo ""
if [[ $IS_PUSH_AFTER_MERGE == true ]]; then
  # Using HEAD we don't have to know the concrete current branch name.
  # If there is at least one commit to push, the server's response message contain a pull-request URL.
  echo "# There was something to merge and the merge finished without conflict. Push the current branch."
  cmd="git -C $MGR_REPO_DIR push --set-upstream origin HEAD"
  echo "\$ $cmd"
  # Output of 'git push':
  # The lines 1-6 are printed to stderr. Lline 7 is printed ot stdout.
  # Line 3 (the line of interest later on) might have trailing spaces!
  # Example-output:
  #
  #   1:  remote:
  #   2:  remote: Create pull request for f2:
  #   3:  remote:   http://localhost:7990/bitbucket/projects/PROJECT_1/repos/r1/pull-requests?create&sourceBranch=refs%2Fheads%2Ff2
  #   4:  remote:
  #   5:  To http://localhost:7990/bitbucket/scm/project_1/r1.git
  #   6:    6c09fe5..16585d0  HEAD -> f2
  #   7:  branch 'f2' set up to track 'origin/f2'.
  #
  git_push_output=$(eval "$cmd" 2>&1)
  # For testing.
  #git_push_output=$(cat ./print-git-push-output.sh)
  echo "$git_push_output"
else
  echo "# IS_PUSH_AFTER_MERGE is false, no push."
  git_push_output=""
fi

echo ""
if [[ "$IS_CREATE_PULL_REQUEST_URLS" == true ]]; then
  # If command "git push" has pushed at least one commit, it prints a message (returned from a
  # server's hook) containing a pull request URL with the source branch already set to the current
  # branch).
  if [[ "$IS_PUSH_AFTER_MERGE" != true ]]; then
    echo "ERROR: IS_CREATE_PULL_REQUEST_URLS is true but IS_PUSH_AFTER_MERGE isn't." \
      "Need the output of 'git push' to parse the pull request URL."
    exit 1
  fi
  if [[ -z "$git_push_output" ]]; then
    echo "ERROR: IS_CREATE_PULL_REQUEST_URLS is true but haven't found the pull request URL in output of 'git push'."
    exit 1
  fi

  # Extract the line with the pull request URL, and from that line the URL itself.
  pr_url=$(echo "$git_push_output" | grep -E "remote: +http" | tr -s ' ' | cut -f 2 -d ' ')
  if [[ -z "$pr_url" ]]; then
    echo "No pull request URL in output of 'git push'. Exit post-script."
    exit 0
  else
    # The source-branch or -tag is already part of the URL. Encode the dest-branch and append it.
    # It seems encoding the URL is not neeeded.
    #dest_branch_name_encoded="${MGR_DEST_BRANCH//\//%2F}"
    #pr_url="$pr_url&targetBranch=refs%2Fheads%2F$dest_branch_name_encoded"
    pr_url="$pr_url&targetBranch=refs/heads/$MGR_DEST_BRANCH"
    echo "$pr_url" >>"$PULL_REQUEST_URLS_FILE"
  fi
fi

echo "# Post-script finished."
