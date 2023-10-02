#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|

REPOS_DIR="/Users/jo/prj-test/merge_git_repos/repos"
DATE_STRING="$(date +'%Y%m%d-%H%M%S')"
LOGS_DIR="/Users/jo/prj-test/merge_git_repos/logs/$DATE_STRING"

COMMON_DEST_BRANCH="ours-branch"

# Register the merge drivers in <repo>/.git/info/attributs rather than rely on <repo>/.gitattributes.
export REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES=true
# The merge driver.
export MERGE_DRIVER_EXECUTABLE="keep_ours_paths_merge_driver.pyz"
# Make Git (called by merge_git_repos.py) and the pre-script find the merge driver.
# Setting the PATH in the pre-script is not sufficient, as Git must find it, and Git is called by
# merge_git_repos.py
PATH=$(pwd):$PATH
export PATH

if ! which "$MERGE_DRIVER_EXECUTABLE"; then
  echo "Can't execute $MERGE_DRIVER_EXECUTABLE. Is it on PATH?"
  exit 1
fi

rm -rf "$REPOS_DIR"

# --pre-script: The "bash -c" is needed in Git-Bash, and can be omitted otherwise.
#
# Call-variants:
#   Call the module (for development):
#     python3 ../../src/merge_git_repos.py
#   Call a fresh generated zipapp (for development):
#     ../../merge_git_repos.pyz
#   Call the zipapp from anywhere (production-like):
#     merge_git_repos.pyz

../../merge_git_repos.pyz \
  --repos-data \
  mt-m:origin/theirs-branch:$COMMON_DEST_BRANCH:gldog/mergetest-maven \
  --merge-options '--no-ff -Xrenormalize -Xignore-space-at-eol' \
  --repos-dir $REPOS_DIR \
  --logs-dir $LOGS_DIR \
  --log-level DEBUG \
  --pre-script 'bash -c ./clone_repos_and_install_mergedrivers.sh' \
  --post-script 'bash -c "echo 'FINISHED' ; printenv | grep MGR_ ; git -C $MGR_REPO_DIR status"' \
  --merge-branch-template \
  "maintain/{{source_branch.replace('origin/','')}}_into_{{dest_branch}}_$DATE_STRING"

# --post-script 'bash -c "git push --set-upstream origin HEAD"' \

exit_code=$?
echo "Exit code: $exit_code"
if [[ $exit_code == 0 ]]; then
  echo "$0: SUCCESS"
else
  echo "$0: FAILURE"
fi
