#!/bin/bash

set -eu
#set -x

trap on_error ERR

function on_error() {
  echo "Pre-script for repo $MGR_REPO_DIR exited with FAILURE."
}

# Set to bitbucket.org if unset.
: "${BASE_URL:=https://github.com}"

# The merge dirver executable. This line is also the check if it is set.
echo "MERGE_DRIVER_EXECUTABLE is ${MERGE_DRIVER_EXECUTABLE}."
echo "Environment-vars exposed by merge_git_repos.py:"
printenv | sort | grep MGR_

# If merge_git_repos.py is called in Git-Bash, Python thinks it runs in a Windows environment and
# creates Windows-style paths. Make the paths Unix-style-paths.
export MGR_REPO_DIR="${MGR_REPO_DIR//\\//}"
export MGR_REPOS_DIR="${MGR_REPOS_DIR//\\//}"
export MGR_LOGS_DIR="${MGR_LOGS_DIR//\\//}"

echo "Clone the repo $MGR_REPO_DIR if absent."
if [[ ! -d "$MGR_REPO_DIR" ]]; then
  echo "  Repo $MGR_REPO_DIR is absent."

  # The ref-repo is named as the remote-repo.
  # MGR_PRJ_AND_REPO_REMOTE_NAME is the value given to merge_git_repos.py in parameter
  # -r/--repos-data in part 'prj/repo-remote-name'. Get the repo-name.
  REPO_REMOTE_NAME=${MGR_PRJ_AND_REPO_REMOTE_NAME##*/}
  REF_REPO="./referencerepos/${REPO_REMOTE_NAME}.git"

  # git clone shall use a reference-repo if present.
  # There are the two options --reference and --reference-if-able. With the option --reference Git
  # expects the given reference-repo is present. If missing, Git aborts with a non-zero exit-code.
  # With the option --reference-if-able Git tries to use the reference-repo. If missing, Git makes
  # a full clone. This Option was introduced in Git version 2.11.4.
  # There might be Git-versions less than 2.11.4. Therefore the behaviour of --reference-if-able
  # is simulated.
  git_cmd="git -C $MGR_REPOS_DIR clone --branch $MGR_DEST_BRANCH"
  git_cmd+=" ${BASE_URL}/${MGR_PRJ_AND_REPO_REMOTE_NAME}.git $MGR_REPO_LOCAL_NAME"
  echo "  Prepared base Git-command for cloning: $git_cmd"
  echo "  Use reference-repo if present."
  if [[ -d "$REF_REPO" ]]; then
    echo "  Found reference-repo $REF_REPO, using option --reference."
    git_cmd+=" --reference $REF_REPO"
  else
    echo "  Haven't found reference-repo $REF_REPO, making a full clone (without option --reference)."
  fi
  echo "  Calling resulting Git-command for cloning: $git_cmd"
  eval "$git_cmd"

  # No else here. The "git pull" will be made by merge_git_repos.py.
fi

# The same merge-driver can be defined repeatedly without error. So we don't care if it is already
# installed.
# MERGE_DRIVER_EXECUTABLE is defined in the overall-calling script.
echo "Defining the merge drivers."
echo "  Defining the XML Maven merge-driver:"
git_cmd="git -C $MGR_REPO_DIR config --local merge.maven-pomxml-keep-ours-xpath-merge-driver.driver"
git_cmd+=" '"
git_cmd+="$MERGE_DRIVER_EXECUTABLE -O %O -A %A -B %B -P ./%P"
git_cmd+=" -p ./version ./parent/version ./properties/revision ./properties/:.+[.]version"
git_cmd+="'"
echo "  Git-command: $git_cmd"
eval "$git_cmd"

echo "  Defining the JSON NPM merge-driver:"
git_cmd="git -C $MGR_REPO_DIR config --local merge.npm-packagejson-keep-ours-jpath-merge-driver.driver"
git_cmd+=" '"
git_cmd+="$MERGE_DRIVER_EXECUTABLE -t JSON -O %O -A %A -B %B -P ./%P"
git_cmd+=" -p version dependencies:@mycompany/.+"
git_cmd+="'"
echo "  Git-command: $git_cmd"
eval "$git_cmd"

echo "Pre-script for repo $MGR_REPO_DIR exited successfully."

