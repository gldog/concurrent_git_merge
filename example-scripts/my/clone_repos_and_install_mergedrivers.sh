#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|
#
# This script clones a Git repo if absent and installs custom merge driver(s).
#
# This script is called by merge_git_repos.py using parameter --pre-script. It is an example.
# merge_git_repos.py calls this pre-script for each repo to be merged parallel.
#
# While merge_git_repos.py is a general purpose script for merging, this pre-script is specific
# for someone's workflow.
#
# Using a custom merge driver means:
#   - The custom merge driver is set in the "merge" attribute in .gitattributes or .git/info/attributes.
#   - The custom merge driver is defined in .git/config
#   - The custom merge driver's executable file can be executed (is present, is in PATH, is executable).
#
# About merge drivers, from "gitattributes - Defining attributes per path"
#   https://git-scm.com/docs/gitattributes ($GIT_DIR is ".git"):
#
#     When deciding what attributes are assigned to a path, Git consults $GIT_DIR/info/attributes
#     file (which has the highest precedence), .gitattributes file in the same directory as the path
#     in question, and its parent directories up to the toplevel of the work tree (the further the
#     directory that contains .gitattributes is from the path in question, the lower its precedence).
#     Finally global and system-wide files are considered (they have the lowest precedence).
#
# This means there are multiple ways to register merge drivers. Two of them are:
#   - In .gitattributes. It is expected someone has checked-in the "merge" setting before merging.
#   - In .git/info/attributes. This works without checking-in anything and is done in this pre-script.
#
# The "merge" setting in .gitattributes and .git/info/attributes are the same, e.g.:
#     pom.xml merge=maven-pomxml-keep-ours-xpath-merge-driver
#     package.json merge=npm-packagejson-keep-ours-jpath-merge-driver
#
# The "maven-pomxml-keep-ours-xpath-merge-driver" and "npm-packagejson-keep-ours-jpath-merge-driver"
# are the logical names of the merge drivers, not the names of the merge driver's executable.
#

set -eu
#set -x

trap on_error ERR

function on_error() {
  echo "Pre-script for repo $MGR_REPO_DIR exited with FAILURE."
}

# Set to bitbucket.org if unset.
: "${BASE_URL:=https://github.com}"
# Tell this script to register the merge driver in .git/info/attributes. Set to false if unset. In
# case of false it is expected the merge drivers are registered in the checked-in .gitattributes file.
: "${REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES:=false}"

# The merge driver executable, set by the overall calling script. This line is also the check if it
# is set.
echo "MERGE_DRIVER_EXECUTABLE is ${MERGE_DRIVER_EXECUTABLE}."
echo "Environment-vars exposed by merge_git_repos.py:"
printenv | sort | grep MGR_

# If merge_git_repos.py is called in Git-Bash, Python thinks it runs in a Windows environment and
# creates Windows-style paths. Make the paths Unix-style-paths.
export MGR_REPO_DIR="${MGR_REPO_DIR//\\//}"
export MGR_REPOS_DIR="${MGR_REPOS_DIR//\\//}"
export MGR_LOGS_DIR="${MGR_LOGS_DIR//\\//}"

echo "Cloning the repo $MGR_REPO_DIR if absent."
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
else
  echo "  Repo $MGR_REPO_DIR is preset."
  # No action here. The "git pull" will be made by merge_git_repos.py.
fi

# The same merge-driver can be defined repeatedly without error. So we don't care if it is already
# installed.
echo "Defining the merge drivers."
echo "  Defining the XML Maven merge driver:"
git_cmd="git -C $MGR_REPO_DIR config --local merge.maven-pomxml-keep-ours-xpath-merge-driver.driver"
git_cmd+=" '"
git_cmd+="$MERGE_DRIVER_EXECUTABLE -O %O -A %A -B %B -P ./%P"
git_cmd+=" -p ./version ./parent/version ./properties/revision ./properties/:.+[.]version"
git_cmd+="'"
echo "  Git-command: $git_cmd"
eval "$git_cmd"

echo "  Defining the JSON NPM merge driver:"
git_cmd="git -C $MGR_REPO_DIR config --local merge.npm-packagejson-keep-ours-jpath-merge-driver.driver"
git_cmd+=" '"
git_cmd+="$MERGE_DRIVER_EXECUTABLE -t JSON -O %O -A %A -B %B -P ./%P"
git_cmd+=" -p version dependencies:@mycompany/.+"
git_cmd+="'"
echo "  Git-command: $git_cmd"
eval "$git_cmd"

# Set the "merge" attribute in .git/info/attributes if REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES
# is true und the setting is absent in .git/info/attributes.
if [[ $REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES == true ]]; then
  ATTRIBUTES_FILE="$MGR_REPO_DIR/.git/info/attributes"
  echo "REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES is true." \
    "Registering merge drivers in $ATTRIBUTES_FILE if not yet registered."
  MAVEN_POM_REGISTRATION="pom.xml merge=maven-pomxml-keep-ours-xpath-merge-driver"
  NPM_PACKAGE_JSON_REGISTRATION="package.json merge=npm-packagejson-keep-ours-jpath-merge-driver"
  if [[ ! -f "$ATTRIBUTES_FILE" ]]; then
    echo "  File $ATTRIBUTES_FILE is not present, creating it."
    echo "  Registering Maven Pom merge driver in $ATTRIBUTES_FILE: $MAVEN_POM_REGISTRATION"
    echo "$MAVEN_POM_REGISTRATION" >>"$ATTRIBUTES_FILE"
    echo "  Registering NPM package.json merge driver in $ATTRIBUTES_FILE: $NPM_PACKAGE_JSON_REGISTRATION"
    echo "$NPM_PACKAGE_JSON_REGISTRATION" >>"$ATTRIBUTES_FILE"
  else
    echo "  File $ATTRIBUTES_FILE already present."
    echo "  Checking if Maven Pom merge driver already registered in $ATTRIBUTES_FILE."
    if ! grep -Fq "$MAVEN_POM_REGISTRATION" "$ATTRIBUTES_FILE"; then
      echo "  Is not present. Registering Maven Pom merge driver in $ATTRIBUTES_FILE: $MAVEN_POM_REGISTRATION"
      echo "$MAVEN_POM_REGISTRATION" >>"$ATTRIBUTES_FILE"
    fi
    echo "  Checking if NPM package.json merge driver already registered in $ATTRIBUTES_FILE."
    if ! grep -Fq "$NPM_PACKAGE_JSON_REGISTRATION" "$ATTRIBUTES_FILE"; then
      echo "  Is not present. Registering NPM package.json merge driver in $ATTRIBUTES_FILE: $NPM_PACKAGE_JSON_REGISTRATION"
      echo "$NPM_PACKAGE_JSON_REGISTRATION" >>"$ATTRIBUTES_FILE"
    fi
  fi
fi

echo "Pre-script $0 called for repo $MGR_REPO_DIR exited successfully."
