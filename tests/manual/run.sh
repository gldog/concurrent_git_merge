#!/bin/bash

#set -x

# https://bitbucket.org/jheger

REPOS_DIR="/Users/jo/prj-test/merge_git_repos/repos"
LOGS_DIR="/Users/jo/prj-test/merge_git_repos/logs"
rm -rf "$REPOS_DIR"

parameters=" --repos-data"
parameters+=" mb:origin/master:test-feature-branch:jheger/stash-mybranches"
parameters+=" td:origin/master:test-feature-branch:jheger/stash-tagdetails"
parameters+=" --repos-dir $REPOS_DIR"
parameters+=" --logs-dir $LOGS_DIR"
parameters+=" --log-level DEBUG"
parameters+=" --exec-pre-merge-script ../../pre-merge-script-examples/my/clone_repos_and_install_merge-drivers.sh"

# Merge-branch template as f-String, using dict-notation:
#parameters+=" --merge-branch-template maintain/dsm_{rm['source_branch'].replace('origin/','')}"
#parameters+="_into_{rm['dest_branch']}_{rm['task_start'].strftime('%b%d')}"

# Merge-branch template as f-String, using dot-notation:
#parameters+=" --merge-branch-template maintain/dsm_{rm.source_branch.replace('origin/','')}"
#parameters+="_into_{rm.dest_branch}_{rm.task_start.strftime('%b%d')}"

# Merge-branch template as Jinja2:
parameters+=" --merge-branch-template maintain/dsm_{{source_branch.replace('origin','')}}"
parameters+="_into_{{dest_branch}}_{{task_start.strftime('%b%d')}}"

#parameters+=" --local"

python3 ../../src/merge_git_repos.py $parameters
echo "Exit code: $?"
