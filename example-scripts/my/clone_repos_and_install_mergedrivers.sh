#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|
#
# Pre-script for concurrent_git_merge.py
#
# This script clones a Git repo if absent and installs custom merge driver(s).
#
# This script is called by concurrent_git_merge.py using parameter --pre-script. It is an example.
# concurrent_git_merge.py calls this pre-script for each repo to be merged concurrently.
#
# While concurrent_git_merge.py is a general purpose script for merging, this pre-script is specific
# for someone's workflow.
#
# Using a custom merge driver means in general:
#   - The custom merge driver is set in the "merge" attribute in .gitattributes or .git/info/attributes.
#   - The custom merge driver is defined in .git/config
#   - The custom merge driver's executable file can be executed (is present, is in PATH, is executable).
#
# About merge drivers, from "gitattributes - Defining attributes per path"
#   https://git-scm.com/docs/gitattributes: ($GIT_DIR is ".git")
#
#     When deciding what attributes are assigned to a path, Git consults $GIT_DIR/info/attributes
#     file (which has the highest precedence), .gitattributes file in the same directory as the path
#     in question, and its parent directories up to the toplevel of the work tree (the further the
#     directory that contains .gitattributes is from the path in question, the lower its precedence).
#     Finally global and system-wide files are considered (they have the lowest precedence).
#
# This means there are multiple ways to register merge drivers. Two of them are:
#
#   - In .gitattributes. It is expected someone has checked-in the "merge" setting before merging.
#   - In .git/info/attributes. This works without checking-in anything and is done in this pre-script.
#
# The "merge" setting in .gitattributes and .git/info/attributes are the same, e.g.:
#
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

# Defaults to github.com if unset.
: "${BASE_URL:=https://github.com}"
# Tell this script to register the merge driver in .git/info/attributes rather than rely on
# .gitattributes. Set to true if unset. In case of false it is expected the merge drivers are
# registered in the checked-in .gitattributes.
: "${IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES:=true}"
# The merge driver keep_ours_paths_merge_driver knows the merge-strategies "onconflict-ours"
# and "always-ours". The default is "onconflict-ours".
# For merges from parent to child branch choose "onconflict-ours". For merges back from child to
# parent choose "always-ours" ("ours" then is the parent).
: "${MERGE_DRIVER_MERGE_STRATEGY:='onconflict-ours'}"

# The merge driver executable, set by the overall calling script. This line is also the check if it
# is set. The merge diver is only used in this pre-script. But it is defined in concurrent_git_merge.sh
# to fail-fast in case it is not callable.
echo ""
echo "# MERGE_DRIVER_EXECUTABLE: ${MERGE_DRIVER_EXECUTABLE}."
echo "# Environment-vars exposed by concurrent_git_merge.py:"
cmd="printenv | sort | grep MGR_"
echo "\$ $cmd"
eval "$cmd"

# If concurrent_git_merge.py is called in Gitbash, Python in fact runs it in a Windows environment and
# creates Windows-style paths. Make the paths Unix-style-paths.
export MGR_REPO_DIR="${MGR_REPO_DIR//\\//}"
export MGR_REPOS_DIR="${MGR_REPOS_DIR//\\//}"
export MGR_LOGS_DIR="${MGR_LOGS_DIR//\\//}"

echo ""
echo "# Cloning the repo $MGR_REPO_DIR if absent."
if [[ ! -d "$MGR_REPO_DIR" ]]; then
  echo "#   Repo $MGR_REPO_DIR is absent."

  # The ref-repo is named as the remote-repo.
  # MGR_PRJ_AND_REPO_REMOTE_NAME is the value given to concurrent_git_merge.py in parameter
  # -r/--repos-data in part 'prj/repo-remote-name'. Get the repo-name.
  REPO_REMOTE_NAME=${MGR_PRJ_AND_REPO_REMOTE_NAME##*/}
  REF_REPO="./referencerepos/${REPO_REMOTE_NAME}.git"

  # git clone shall use a reference-repo if present.
  # There are the two Git options --reference and --reference-if-able. With the option --reference
  # Git expects the given reference-repo is present. If missing, Git aborts with a non-zero exit-code.
  # With the option --reference-if-able Git tries to use the reference-repo. If missing, Git makes
  # a full clone. This Option was introduced in Git version 2.11.4.
  # There might be Git-versions less than 2.11.4. Therefore the behaviour of --reference-if-able
  # is simulated.
  #
  # Git clones all tags per default, and has the option --no-tags to not clone them. But surprisingly
  # using --not-tags is slower. So don't use this option.
  cmd="git -C $MGR_REPOS_DIR clone --branch $MGR_DEST_BRANCH"
  cmd+=" ${BASE_URL}/${MGR_PRJ_AND_REPO_REMOTE_NAME}.git $MGR_REPO_LOCAL_NAME"
  echo "#   Use reference-repo if present."
  if [[ -d "$REF_REPO" ]]; then
    echo "#   Found reference-repo $REF_REPO, using option --reference."
    cmd+=" --reference $REF_REPO"
  else
    echo "#   Haven't found reference-repo $REF_REPO, making a full clone (without option --reference)."
  fi
  echo "\$ $cmd"
  eval "$cmd"
else
  echo ""
  echo "#   Repo $MGR_REPO_DIR is present."
  echo "#   Fetching all tags."
  cmd="git -C $MGR_REPO_DIR fetch --tags $REMOTE"
  echo "\$ $cmd"
  eval "$cmd"
fi

# The same merge-driver can be defined repeatedly without error. Don't care if it is already
# installed.
echo ""
echo "# Defining the merge drivers."
echo "#   Defining the XML Maven merge driver:"
cmd="git -C $MGR_REPO_DIR config --local merge.maven-pomxml-keep-ours-xpath-merge-driver.driver"
cmd+=" '"
cmd+="$MERGE_DRIVER_EXECUTABLE -O %O -A %A -B %B -P ./%P"
cmd+=" -p ${MERGE_DRIVER_MERGE_STRATEGY}:./version"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./parent/version"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./properties/revision"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./properties/:.+[.]version"
cmd+="'"
echo "\$ $cmd"
eval "$cmd"

echo "#   Defining the JSON NPM merge driver:"
cmd="git -C $MGR_REPO_DIR config --local merge.npm-packagejson-keep-ours-jpath-merge-driver.driver"
cmd+=" '"
cmd+="$MERGE_DRIVER_EXECUTABLE -t JSON -O %O -A %A -B %B -P ./%P"
cmd+=" -p ${MERGE_DRIVER_MERGE_STRATEGY}:version"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:dependencies:@mycompany/.+"
cmd+="'"
echo "\$ $cmd"
eval "$cmd"

# Set the "merge" attribute in .git/info/attributes if IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES
# is true and the setting is absent in .git/info/attributes.
echo ""
if [[ $IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES == true ]]; then
  ATTRIBUTES_FILE="$MGR_REPO_DIR/.git/info/attributes"
  echo "# IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES is true." \
    "Registering merge drivers in $ATTRIBUTES_FILE if not yet registered."
  MAVEN_POM_REGISTRATION="pom.xml merge=maven-pomxml-keep-ours-xpath-merge-driver"
  NPM_PACKAGE_JSON_REGISTRATION="package.json merge=npm-packagejson-keep-ours-jpath-merge-driver"
  if [[ ! -f "$ATTRIBUTES_FILE" ]]; then
    echo "#   File $ATTRIBUTES_FILE is not present, creating it."
    echo "#   Registering Maven Pom merge driver in $ATTRIBUTES_FILE: $MAVEN_POM_REGISTRATION"
    echo "$MAVEN_POM_REGISTRATION" >>"$ATTRIBUTES_FILE"
    echo "#   Registering NPM package.json merge driver in $ATTRIBUTES_FILE: $NPM_PACKAGE_JSON_REGISTRATION"
    echo "$NPM_PACKAGE_JSON_REGISTRATION" >>"$ATTRIBUTES_FILE"
  else
    echo "#   File $ATTRIBUTES_FILE already present."
    echo "#   Checking if Maven Pom merge driver already registered in $ATTRIBUTES_FILE or shall be registered."
    if ! grep -Fq "$MAVEN_POM_REGISTRATION" "$ATTRIBUTES_FILE"; then
      echo "#    Is not present. Registering Maven Pom merge driver in $ATTRIBUTES_FILE: $MAVEN_POM_REGISTRATION"
      echo "$MAVEN_POM_REGISTRATION" >>"$ATTRIBUTES_FILE"
    else
      echo "#     Is present."
    fi
    echo "#   Checking if NPM package.json merge driver already registered in $ATTRIBUTES_FILE or shall be registered."
    if ! grep -Fq "$NPM_PACKAGE_JSON_REGISTRATION" "$ATTRIBUTES_FILE"; then
      echo "#   Is not present. Registering NPM package.json merge driver in $ATTRIBUTES_FILE: $NPM_PACKAGE_JSON_REGISTRATION"
      echo "$NPM_PACKAGE_JSON_REGISTRATION" >>"$ATTRIBUTES_FILE"
    else
      echo "#     Is present."
    fi
  fi
fi

echo "# Pre-script $0 called for repo $MGR_REPO_DIR finished."
