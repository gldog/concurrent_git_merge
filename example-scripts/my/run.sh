#!/bin/bash

REPOS_DIR="/Users/jo/prj-test/merge_git_repos/repos"
DATE_STRING="$(date +'%Y%m%d-%H%M%S')"
LOGS_DIR="/Users/jo/prj-test/merge_git_repos/logs/$DATE_STRING"

rm -rf "$REPOS_DIR"

#The "bash -c" is needed in Git-Bash, and can be omitted otherwise.
python3 ../../src/merge_git_repos.py \
  --repos-data \
  mb:origin/master:test-feature-branch:jheger/stash-mybranches \
  td:origin/master:test-feature-branch:jheger/stash-tagdetails \
  --merge-options '--no-ff -Xrenormalize -Xignore-space-at-eol' \
  --repos-dir $REPOS_DIR \
  --logs-dir $LOGS_DIR \
  --log-level DEBUG \
  --pre-script 'bash -c ../../example-scripts/my/pre/clone_repos_and_install_merge-drivers.sh' \
  --post-script 'bash -c "echo 'FINISHED' ; printenv | grep MGR_ ; git -C $MGR_REPO_DIR status"' \
  --merge-branch-template \
    "maintain/{{source_branch.replace('origin/','')}}_into_{{dest_branch}}_$DATE_STRING"

# --post-script 'bash -c "git push --set-upstream origin HEAD"' \

echo "Exit code: $?"
