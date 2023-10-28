#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|
#
# Pre-script for concurrent_git_merge.py
#
# This script clones a Git repo if absent and installs custom merge driver.
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
# In this script the keep_ours_paths_merge_driver https://github.com/gldog/keep_ours_paths_merge_driver
# is used.
#

set -eu
#set -x

trap on_error ERR

function on_error() {
  echo "Pre-script for repo $CGM_REPO_DIR exited with FAILURE."
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
# parent choose "always-ours" ("ours" then is the parent). Despite "onconflict-ours" is the default
# it is given here explicitly for demonstration.
: "${MERGE_DRIVER_MERGE_STRATEGY:='onconflict-ours'}"

# The merge driver executable, set by the overall calling script. This line is also the check if it
# is set. The merge diver is only used in this pre-script. But it is defined in the calling script
# to fail-fast in case it is not callable.
echo ""
echo "# MERGE_DRIVER_EXECUTABLE: ${MERGE_DRIVER_EXECUTABLE}."
echo "# Environment-vars exposed by concurrent_git_merge.py:"
cmd="printenv | sort | grep CGM_"
echo "\$ $cmd"
eval "$cmd"

# If concurrent_git_merge.py is called in Gitbash, Python in fact runs it in a Windows environment
# and creates Windows-style paths. Make the paths Unix-style-paths (I'm in Linux, macOS, Gitbash,
# but not in CMD).
export CGM_REPO_DIR="${CGM_REPO_DIR//\\//}"
export CGM_REPOS_DIR="${CGM_REPOS_DIR//\\//}"
export CGM_LOGS_DIR="${CGM_LOGS_DIR//\\//}"

echo ""
echo "# Cloning the repo $CGM_REPO_DIR if absent."
if [[ ! -d "$CGM_REPO_DIR" ]]; then
  echo "#   Repo $CGM_REPO_DIR is absent."

  # The ref-repo is named as the remote-repo.
  # CGM_PRJ_AND_REPO_REMOTE_NAME is the value given to concurrent_git_merge.py in parameter
  # -r/--repos-data in part 'prj/repo-remote-name'. Get the repo-name.
  REPO_REMOTE_NAME=${CGM_PRJ_AND_REPO_REMOTE_NAME##*/}
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
  cmd="git -C $CGM_REPOS_DIR clone --branch $CGM_DEST_BRANCH"
  cmd+=" ${BASE_URL}/${CGM_PRJ_AND_REPO_REMOTE_NAME}.git $CGM_REPO_LOCAL_NAME"
  echo "#   Use reference-repo if present."
  if [[ -d "$REF_REPO" ]]; then
    echo "#   Found reference-repo $REF_REPO, using option --reference."
    cmd+=" --reference $REF_REPO"
  else
    echo "#   Haven't found reference-repo $REF_REPO, making a full clone."
  fi
  echo "\$ $cmd"
  eval "$cmd"
else
  echo ""
  echo "#   Repo $CGM_REPO_DIR is present."
  echo "#   Fetching all tags."
  # REMOTE might have a trailing slash. Remove it.
  cmd="git -C $CGM_REPO_DIR fetch --tags ${REMOTE///}"
  echo "\$ $cmd"
  eval "$cmd"
  echo ""
  echo "# Checkout dest-branch"
  cmd="git -C $CGM_REPO_DIR checkout $CGM_DEST_BRANCH"
  echo "\$ $cmd"
  eval "$cmd"
  echo "# Pull dest-branch"
  cmd="git -C $CGM_REPO_DIR pull"
  echo "\$ $cmd"
  eval "$cmd"
fi

# The same merge-driver can be defined repeatedly without error. Don't care if it is already
# installed.
echo ""
echo "# Defining the merge drivers."
echo "#   Defining the XML Maven pom.xml merge driver:"
cmd="git -C $CGM_REPO_DIR config --local merge.maven-pomxml-keep-ours-xpath-merge-driver.driver"
cmd+=" '"
cmd+="$MERGE_DRIVER_EXECUTABLE -t XML -O %O -A %A -B %B -P ./%P -p"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./version"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./parent/version"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./properties/revision"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./properties/:.+[.]version"
cmd+="'"
echo "\$ $cmd"
eval "$cmd"

echo "#   Defining the JSON NPM package.json merge driver:"
cmd="git -C $CGM_REPO_DIR config --local merge.npm-packagejson-keep-ours-jpath-merge-driver.driver"
cmd+=" '"
cmd+="$MERGE_DRIVER_EXECUTABLE -t JSON -O %O -A %A -B %B -P ./%P -p"
cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:version"
cmd+="'"
echo "\$ $cmd"
eval "$cmd"

# Set the "merge" attribute in .git/info/attributes if IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES
# is true and the setting is absent in .git/info/attributes.
echo ""
ATTRIBUTES_FILE="$CGM_REPO_DIR/.git/info/attributes"
if [[ $IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES == true ]]; then
  echo "# IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES is true." \
    "Registering merge drivers in $ATTRIBUTES_FILE."
  # Create the file if absent.
  touch "$ATTRIBUTES_FILE"
  echo "# Remove all our merge-drivers from $ATTRIBUTES_FILE."
  # Our merge driver are:
  #   - maven-pomxml-keep-ours-xpath-merge-driver
  #   - npm-packagejson-keep-ours-jpath-merge-driver
  # Their name substrings keep-ours-xpath-merge-driver and keep-ours-jpath-merge-driver are almost equal, the only
  # difference is the x/j.
  grep -v "keep-ours-.path-merge-driver" "$ATTRIBUTES_FILE" >"${ATTRIBUTES_FILE}.tmp" || true
  MAVEN_POM_REGISTRATION="pom.xml merge=maven-pomxml-keep-ours-xpath-merge-driver"
  NPM_PACKAGE_JSON_REGISTRATION="package.json merge=npm-packagejson-keep-ours-jpath-merge-driver"
  NPM_PACKAGELOCK_JSON_REGISTRATION="package-lock.json merge=npm-packagejson-keep-ours-jpath-merge-driver"
  mv "${ATTRIBUTES_FILE}.tmp" "$ATTRIBUTES_FILE"
  echo "# Registering Maven Pom merge driver in $ATTRIBUTES_FILE: $MAVEN_POM_REGISTRATION"
  echo "$MAVEN_POM_REGISTRATION" >>"$ATTRIBUTES_FILE"
  echo "# Registering NPM package.json merge driver in $ATTRIBUTES_FILE: $NPM_PACKAGE_JSON_REGISTRATION"
  echo "$NPM_PACKAGE_JSON_REGISTRATION" >>"$ATTRIBUTES_FILE"
  # The registration for package-lock.json is done with merge driver for package.json.
  echo "# Registering NPM package-lock.json merge driver in $ATTRIBUTES_FILE: $NPM_PACKAGE_JSON_REGISTRATION"
  echo "$NPM_PACKAGELOCK_JSON_REGISTRATION" >>"$ATTRIBUTES_FILE"
fi

echo ""
echo "# Summarize .git/config and .git/info/attributes."
echo ""
GIT_CONFIG="$CGM_REPO_DIR/.git/config"
echo "#   $GIT_CONFIG:"
if [[ -f "$GIT_CONFIG" ]]; then
  echo "#   >>>>>"
  cat "$GIT_CONFIG"
  echo "#   <<<<<"
else
  echo "#   No .git/config file."
fi

echo ""
echo "#   $ATTRIBUTES_FILE:"
if [[ -f "$ATTRIBUTES_FILE" ]]; then
  echo "#   >>>>>"
  cat "$ATTRIBUTES_FILE"
  echo "#   <<<<<"
else
  echo "#   No attributes file."
fi
