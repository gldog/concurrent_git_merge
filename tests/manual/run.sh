#!/bin/bash

REPOS_DIR="/Users/jo/prj-test/merge_git_repos/repos"
LOGS_DIR="/Users/jo/prj-test/merge_git_repos/logs/$(date +'%Y%m%d-%H%M%S')"
rm -rf "$REPOS_DIR"

python3 ../../src/merge_git_repos.py \
  --repos-data \
  mb:origin/master:test-feature-branch:jheger/stash-mybranches \
  td:origin/master:test-feature-branch:jheger/stash-tagdetails \
  --merge-options '--no-ff -Xrenormalize -Xignore-space-at-eol' \
  --repos-dir $REPOS_DIR \
  --logs-dir $LOGS_DIR \
  --log-level DEBUG \
  --exec-pre-merge-script ../../pre-merge-script-examples/my/clone_repos_and_install_merge-drivers.sh \
  --merge-branch-template \
  "maintain/dsm_{{source_branch.replace('origin/','')}}_into_{{dest_branch}}_{{task_start.strftime('%b%d')}}"

echo "Exit code: $?"
