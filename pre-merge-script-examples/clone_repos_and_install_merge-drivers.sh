#!/bin/bash

set -eu
set -x

BASE_URL="https://bitbucket.org"

echo "Env-vars exposed by merge_repos.py:"
printenv | sort | grep MR_

# Clone the repo if absent and install the merge-drivers.
# If the repo is present, assume the merge-drivers are already installed. Just report them.
if [[ ! -d "$MR_REPO_DIR" ]]; then

  # The ref-repo is named as the remote-repo.
  # MR_PRJ_AND_REPO_REMOTE_NAME is the value given to merge_git_repos.py in parameter -r/--repos-data in
  # part 'prj/repo-remote-name'. Get the repo-name.
  REPO_REMOTE_NAME=${MR_PRJ_AND_REPO_REMOTE_NAME##*/}
  REF_REPO="./referencerepos/${REPO_REMOTE_NAME}.git"

  # git clone should use a reference-repo if possible.
  # There are the two options --reference and --reference-if-able. With the option --reference Git
  # expects the given reference-repo. If missing, Git aborts with a non-zero exit-code.
  # With the option --reference-if-able Git tries to use the reference-repo. If missing, Git makes
  # a full clone. This Option was introduced in Git version 2.11.4.
  # There might be Git-versions less than 2.11.4. Therefore the behaviour of --reference-if-able
  # is simulated.
  git_cmd="git -C $MR_REPOS_DIR clone --branch $MR_DEST_BRANCH ${BASE_URL}/${MR_PRJ_AND_REPO_REMOTE_NAME}.git $MR_REPO_LOCAL_NAME"
  if [[ -d "$REF_REPO" ]]; then
    echo "Found reference-repo $REF_REPO, add Git-option --reference."
    git_cmd+=" --reference $REF_REPO"
  else
    echo "Haven't found reference-repo $REF_REPO, make a full clone (without option --reference)."
  fi
  eval "$git_cmd"

  echo "Install the XML Maven merge-driver."
  git_cmd="git -C $MR_REPO_DIR config --local merge.maven-pomxml-keep-ours-xpath-merge-driver.driver"
  git_cmd+=" '"
  git_cmd+="keep_ours_paths_merge_driver.pyz -O %O -A %A -B %B -P ./%P"
  git_cmd+=" -p ./version ./parent/version ./properties/revision ./properties/:.+[.]version"
  git_cmd+="'"
  eval "$git_cmd"

  echo "Install the JSON NPM merge-driver."
  git_cmd="git -C $MR_REPO_DIR config --local merge.npm-packagejson-keep-ours-jpath-merge-driver.driver"
  git_cmd+=" '"
  git_cmd+="keep_ours_paths_merge_driver.pyz -t JSON -O %O -A %A -B %B -P ./%P"
  git_cmd+=" -p version dependencies:@mycompany/.+"
  git_cmd+="'"
  eval "$git_cmd"

else
  set +e
  echo "Expected installed merge-drivers. The following command exits with a non-zero value in case no merge-driver is installed."
  echo "Installed merge-drivers:"
  git -C "$MR_REPO_DIR" config --local --get-regexp merge-driver
  if [[ $? != 0 ]]; then
    echo "No merge-driver installed."
    exit 1
  fi
fi
