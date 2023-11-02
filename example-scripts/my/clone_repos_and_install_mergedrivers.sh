#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|
#
# Pre-script for concurrent_git_merge.py
#
# This script clones a Git repo if absent and installs custom merge drivers.
#
# This script is called by concurrent_git_merge.py using parameter --pre-script. It is an example.
# concurrent_git_merge.py calls this pre-script for each repo to be merged concurrently.
#
# While concurrent_git_merge.py is a general purpose script for local merging, this pre-script is
# specific for someone's workflow.
#
# In detail this script does the following:
#   - Clone the repo if absent.
#   - If the repo exists, do a "fetch --tags" and a "git pull". The merge drivers are deactivated
#     during pull.
#   - define and register mergedrivers.
#   - Ff MERGE_DRIVER_MERGE_STRATEGY is "always-ours":
#     Modify files registered for merge drivers if they were modified on source-ref but not on
#     dest-branch.
#     If a user configures "always-ours" it is expected the paths configured for the merge driver
#     are kept at merge. But Git calls merge drivers only in case of a 3-way-merge. If a file has
#     been modified on source-ref but not on dest-branch, the merge driver won't be called and
#     can not keep anything. The changes on source-ref will win, and potentially change paths.
#     To let the merge driver keep the paths, a 3-way-merge is needed. This is achieved by "touching"
#     and commit the files registered for the merge driver on dest-branch.
#     Those files have a text-marker line. This pre-script notices this line and append the file's
#     content-hash to this line (or replace an existing hash), and commits the file on dest-branch.
#     This is done only in case the file hasn't changed between merge-base and dest-branch, to
#     modify the file only if needed.
#     Using the file's content-hash for modifying is one possibility to make any change to the file.
#     There might be other ways.
#
# Using a custom merge driver means in general:
#   - The custom merge driver is registered in the "merge" attribute in .gitattributes or
#     .git/info/attributes.
#   - The custom merge driver is defined in .git/config.
#   - The custom merge driver's executable file can be executed (is present, is in PATH, is executable).
#
# About merge drivers, from "gitattributes - Defining attributes per path"
#   https://git-scm.com/docs/gitattributes: ($GIT_DIR is ".git")
#
#         When deciding what attributes are assigned to a path, Git consults $GIT_DIR/info/attributes
#         file (which has the highest precedence), .gitattributes file in the same directory as the
#         path in question, and its parent directories up to the toplevel of the work tree (the
#         further the directory that contains .gitattributes is from the path in question, the lower
#         its precedence). Finally global and system-wide files are considered (they have the lowest
#         precedence).
#
# This means there are multiple ways to register merge drivers. Two of them are:
#
#   - In .gitattributes. It is expected someone has checked-in the "merge" setting before merging.
#   - In .git/info/attributes. This works without checking-in anything and is done in this pre-script.
#
# The "merge" setting in .gitattributes and .git/info/attributes are the same, e.g.:
#
#     pom.xml merge=maven-pomxml-keep-ours-path-merge-driver
#     package.json merge=npm-packagejson-keep-ours-path-merge-driver
#     package-lock.json merge=npm-packagejson-keep-ours-path-merge-driver
#
# In this script the keep_ours_paths_merge_driver https://github.com/gldog/keep_ours_paths_merge_driver
# is used, and registered in .git/info/attributes.
#

set -eu
#set -x

trap on_error ERR

on_error() {
  echo "Pre-script for repo $CGM_REPO_DIR exited with FAILURE."
}

# Used for testing single functions.
: "${IS_SCRIPT_USED_AS_LIB:=false}"
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

# If concurrent_git_merge.py is called in Gitbash, Python in fact runs it in a Windows environment
# and creates Windows-style paths. Make the paths Unix-style-paths (I'm in Linux, macOS, Gitbash,
# but not in CMD).
export CGM_REPO_DIR="${CGM_REPO_DIR//\\//}"
export CGM_REPOS_DIR="${CGM_REPOS_DIR//\\//}"
export CGM_LOGS_DIR="${CGM_LOGS_DIR//\\//}"

exec_cmd() {
  local cmd="$1"

  echo "\$ $cmd"
  eval "$cmd"
}

print_env_vars() {
  # The merge driver executable, set by the overall calling script. This line is also the check if it
  # is set. The merge diver is only used in this pre-script. But it is defined in the calling script
  # to fail-fast in case it is not callable.
  echo ""
  echo "# MERGE_DRIVER_EXECUTABLE: $(which "$MERGE_DRIVER_EXECUTABLE")."
  echo "# Environment-vars exposed by concurrent_git_merge.py:"
  exec_cmd "printenv | sort | grep CGM_"
}

clone_or_fetch_and_pull() {
  if [[ ! -d "$CGM_REPO_DIR" ]]; then
    echo "# Repo $CGM_REPO_DIR is absent, cloning it."

    # The ref-repo is named as the remote-repo.
    # CGM_PRJ_AND_REPO_REMOTE_NAME is the value given to concurrent_git_merge.py in parameter
    # -r/--repos-data in part 'prj/repo-remote-name'. Get the repo-name.
    local repo_remote_name=${CGM_PRJ_AND_REPO_REMOTE_NAME##*/}
    local ref_repo="./referencerepos/${repo_remote_name}.git"

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
    local cmd="git -C $CGM_REPOS_DIR clone --branch $CGM_DEST_BRANCH"
    cmd+=" ${BASE_URL}/${CGM_PRJ_AND_REPO_REMOTE_NAME}.git $CGM_REPO_LOCAL_NAME"
    echo "#   Use reference-repo if present."
    if [[ -d "$ref_repo" ]]; then
      echo "#   Found reference-repo $ref_repo, using option --reference."
      cmd+=" --reference $ref_repo"
    else
      echo "#   Haven't found reference-repo $ref_repo, making a full clone."
    fi
    echo "\$ $cmd"
    eval "$cmd"

    cd "$CGM_REPO_DIR"
  else
    cd "$CGM_REPO_DIR"
    echo "# Repo $CGM_REPO_DIR is present."
    echo "#   Fetching all tags."
    # REMOTE might have a trailing slash. Remove it.
    exec_cmd "git fetch --tags ${REMOTE///}"
    echo ""
    echo "#   Checking out and pulling dest-branch."
    echo "#   Deactivating merge drivers first."
    # Disable merge drivers.
    # At pull, a fast-forward merge is expected. But if it isn't a fast-forward, the merge drivers
    # shall not "keep ours" local path. A user expects merging the/all remote changes into the
    # local workspace.
    # The paths for the merge driver can be configured by command line parameter "-p/--pathspatterns
    # or by environment varianle KOP_MERGE_DRVIER_PATHSPATTERNS. The latter takes precedence. Setting
    # it to an empty string effectively disables the merge driver.
    exec_cmd "export KOP_MERGE_DRVIER_PATHSPATTERNS=''"
    exec_cmd "git checkout $CGM_DEST_BRANCH"
    echo "#   Pulling dest-branch"
    exec_cmd "git pull"
    echo "#   Reactivating merge drivers."
    exec_cmd "unset KOP_MERGE_DRVIER_PATHSPATTERNS"
  fi
}

define_and_register_mergedrivers() {
  # The same merge-driver can be defined repeatedly without error. Don't care if it is already
  # installed.
  #
  # Note:
  # The files have to be listed in section "files_registered_for_merge_drivers".
  #
  echo ""
  echo "# Defining the merge drivers."
  echo "#   Defining the XML Maven pom.xml merge driver:"
  local cmd="git config --local merge.maven-pomxml-keep-ours-path-merge-driver.driver"
  cmd+=" '"
  # Merge driver params:
  # -t: The file type to merge, one of 'XML', 'JSON'.
  # -O: Base version (ancestor's version)
  # -A: Ours version (current version).
  # -B: Theirs version (other branches' version).
  # -P: The pathname in which the merged result will be stored.
  # -p: List of paths with merge-strategy and and path-pattern.
  cmd+="$MERGE_DRIVER_EXECUTABLE -t XML -O %O -A %A -B %B -P ./%P -p"
  cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./version"
  cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./parent/version"
  cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./properties/revision"
  cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:./properties/:.+[.]version"
  # This line is about triggering a 3-way-merge:
  # With merge-strategy "always-ours" it is expected the configured path always wins. But Git calls
  # a merge driver only in case of a 3-way-merge. Without a 3-way-merge but with a change on "theirs"
  # Git will fast-forward merge a file. By this, that "theirs" changes win on dest-branch "ours".
  # This is not expected using "always-ours". The following line will be changed by the pre-script
  # in case
  #   - the merge-strategy is "always-ours", and
  #   - ours file hasn't changed.
  # This provokes a 3-way-merge, Git will trigger the merge driver, and the merge driver can keep
  # the configured paths.
  # The "trigger text line" is:
  #   <project>
  #     <properties>
  #       <ci-merge-driver-trigger>
  #         This line is to trigger the Git merge driver. Do not touch! (12345)
  #       </ci-merge-driver-trigger>
  #     ...
  # The "(12345)" is the file's hash (before changing it). This hash will be changed to make a
  # modification to the file. See modify_files_if_unchanged_on_dest_branch.sh.
  # The trigger-text is embedded in the XML as tag, not as comment or simply an empty line. This
  # is to make that tag part of the merge driver's path configuration. This line is only a trigger
  # and must not provoke merge conflicts, not be changed by IDEs or formatters.
  # "always-ours" is used here because that should result in less merges than "onconflict-ours"
  # (the merge result of this line is not of interest).
  cmd+=" always-ours:./properties/ci-merge-driver-trigger"
  cmd+="'"
  exec_cmd "$cmd"

  echo "#   Defining the JSON NPM package.json merge driver:"
  cmd="git config --local merge.npm-packagejson-keep-ours-path-merge-driver.driver"
  cmd+=" '"
  cmd+="$MERGE_DRIVER_EXECUTABLE -t JSON -O %O -A %A -B %B -P ./%P -p"
  cmd+=" ${MERGE_DRIVER_MERGE_STRATEGY}:version"
  # This line is about triggering a 3-way-merge.
  # NPM allows arbitrary (but valid) custom JSON-objects, as long as they do not conflict with
  # reserved attributes. Here, "com_example.ci-merge-driver-trigger" is used.
  cmd+=" always-ours:com_example.ci-merge-driver-trigger"
  cmd+="'"
  exec_cmd "$cmd"

  # Set the "merge" attribute in .git/info/attributes if IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES
  # is true.
  echo ""
  local attributes_file=".git/info/attributes"
  if [[ $IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES == true ]]; then
    echo "#   IS_REGISTER_MERGEDRIVER_IN_GITDIR_INFO_ATTRIBUTES is true." \
      "Registering merge drivers in $attributes_file."
    # Create the file if absent.
    touch "$attributes_file"
    # Removing and re-inserting the merge drivers makes them robust against reconfiguration.
    echo "#   Removing all our merge-drivers from $attributes_file."
    echo ""
    # sed with in-place-edit behaves different depending on the OS. One (or the only) portable way is
    # to give -i _with_ extension. But this creates a backup-file. Delete it.
    sed -i.bak '/keep-ours-path-merge-driver/d' "$attributes_file"
    rm "${attributes_file}.bak"
    MERGE_DRIVER_REGISTRATION="/pom.xml merge=maven-pomxml-keep-ours-path-merge-driver\n"
    MERGE_DRIVER_REGISTRATION+="/package.json merge=npm-packagejson-keep-ours-path-merge-driver\n"
    MERGE_DRIVER_REGISTRATION+="/package-lock.json merge=npm-packagejson-keep-ours-path-merge-driver"
    echo -e "#   Registering Maven Pom and NPM package/lock.json merge drivers" \
      "in $attributes_file:\n$MERGE_DRIVER_REGISTRATION"
    echo -e "$MERGE_DRIVER_REGISTRATION" >>"$attributes_file"
  fi

  echo ""
  echo "# Summary of .git/config and .git/info/attributes."
  echo ""
  local git_config_file=".git/config"
  echo "#   $git_config_file:"
  if [[ -f "$git_config_file" ]]; then
    echo "#   >>>>>"
    cat "$git_config_file"
    echo "#   <<<<<"
  else
    echo "#   No .git/config file."
  fi

  echo ""
  echo "#   $attributes_file:"
  if [[ -f "$attributes_file" ]]; then
    echo "#   >>>>>"
    cat "$attributes_file"
    echo "#   <<<<<"
  else
    echo "#   No attributes file."
  fi
}

#
# MAIN
#

[[ "$IS_SCRIPT_USED_AS_LIB" == true ]] && exit

print_env_vars
clone_or_fetch_and_pull
define_and_register_mergedrivers

echo ""
if [[ "$MERGE_DRIVER_MERGE_STRATEGY" == "always-ours" ]]; then
  files_registered_for_merge_drivers="pom.xml package-lock.json package.json"
  echo "# MERGE_DRIVER_MERGE_STRATEGY is $MERGE_DRIVER_MERGE_STRATEGY."
  echo "# Modfy files registered for the merge drivers on dest-branch (if unchanged) to trigger the" \
    "merge drivers."
  echo "# The files are: $files_registered_for_merge_drivers"
  . modify_files_if_unchanged_on_dest_branch.sh
  # Note, the "files_registered_for_merge_drivers" are the ones from section "define_and_register_mergedrivers".
  modify_files_if_unchanged_on_dest_branch "$CGM_SOURCE_REF" "$CGM_DEST_BRANCH" "$files_registered_for_merge_drivers"
fi
