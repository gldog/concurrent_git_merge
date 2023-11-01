#!/bin/bash

#------------------------------------------------------------------------------------------- 100 --|
# Description see clone_repos_and_install_mergedrivers.sh
#

set -eu
#set -x

trap on_error ERR

on_error() {
  echo "$0 exited with FAILURE."
}

exec_cmd() {
  local cmd="$1"

  echo "\$ $cmd"
  eval "$cmd"
}

modify_file() {
  local file="$1"
  # Because of the marker-string there is no need to parse and modify the file as XML or JSON.
  # The whole marker-text is e.g.:
  #   This line is to trigger the Git merge driver. Do not touch! (e95b18d)
  local marker_text="This line is to trigger the Git merge driver."

  echo "#   modify_file; file: $file"

  echo "#     Search in $file for marker-text '$marker_text' and append file-hash."
  echo "#     Marker-text before modification:"
  # Because of "set -e" this command will abort in case the marker-text is not yet added.
  exec_cmd "grep -F '$marker_text' $file"
  # --short prints 7 chars instead of 40. 7 is sufficient.
  local cmd="git rev-parse --short HEAD:$file"
  echo "\$ $cmd"
  local file_hash
  file_hash=$(eval "$cmd")
  echo "$file_hash"
  # sed with in-place-edit behaves different depending on the OS. One (or the only) portable way is
  # to give -i _with_ extension. But this creates a backup-file. Delete it.
  exec_cmd "sed -i.bak -E \"s/(.*$marker_text.*)(\(.*\))/\1($file_hash)/g\" $file"
  rm "${file}.bak"
  echo "#     Marker-text after modification:"
  exec_cmd "grep -F '$marker_text' $file"
}

modify_files_if_unchanged_on_dest_branch() {
  local source_ref="$1"
  shift
  local dest_branch="$1"
  shift
  local files_registered_for_merge_drivers="$*"

  echo "# modify_files_if_unchanged_on_dest_branch; source_ref: $source_ref; dest_branch: $dest_branch;" \
    "files_registered_for_merge_drivers: $files_registered_for_merge_drivers"

  echo ""
  echo "#   Showing all merge-bases, just for logging."
  local cmd="git merge-base --all $source_ref $dest_branch"
  echo "\$ $cmd"
  local mergebase_commits
  mergebase_commits=$(eval "$cmd")
  echo "$mergebase_commits"

  # TODO abort if more than 1 merge-base? Or rely on Git?

  echo ""
  echo "#   Calculating files common to files_changed_on_source_ref and" \
    "files_registered_for_merge_drivers. Only that files can affect the" \
    "files_registered_for_merge_drivers on dest_branch."
  # By default, comm outputs 3 columns: left-only, right-only, both. The -1, -2 and -3 switches
  # suppress these columns. The inputs must be sorted.
  #
  # The following command gets the files changed on source-ref.
  #   git diff --name-only --merge-base "$dest_branch\ "$source_ref"
  cmd="comm -12"
  cmd+=" <(git diff --name-only --merge-base \"$dest_branch\" \"$source_ref\" | sort)"
  cmd+=" <(echo -e $files_registered_for_merge_drivers | tr ' ' '\n' | sort)"
  echo "\$ $cmd"
  local files_potentially_affecting
  files_potentially_affecting=$(eval "$cmd")
  echo "$files_potentially_affecting"

  echo ""
  echo "#   Calculating files affecting the merge. These are the files modified on source-ref," \
    "and in the list of files_registered_for_merge_drivers, and NOT modified on dest_branch." \
    "Without any further action, Git won't trigger the merge drivers registered for these files." \
    "There is the risk modifications on source-ref are being merged into dest_branch undesirably." \
    "To assure the merge drivers are triggered, modifying these files on dest_branch (HEAD)" \
    "to let Git detect a 3-way-merge."
  # The following command gets the files changed on dest_branch.
  #     git diff --name-only --merge-base "$source_ref" "$dest_branch"
  #
  cmd="comm -23"
  cmd+=" <(echo -e \"$files_potentially_affecting\" | sort)"
  cmd+=" <(git diff --name-only --merge-base \"$source_ref\" \"$dest_branch\" | sort)"
  echo "\$ $cmd"
  local files_affected
  files_affected=$(eval "$cmd")
  echo "$files_affected"

  for file in $files_affected; do
    echo ""
    modify_file "$file"
  done

  echo ""
  echo "#   Make a commit if any file has been modified."
  cmd="git status --porcelain"
  echo "\$ $cmd"
  local git_status
  git_status=$(eval "$cmd")
  echo "$git_status"
  if [[ -n "$git_status" ]]; then
    exec_cmd "git commit -am 'CI-RELEASE Dummy-change to let Git trigger the merge driver'"
    echo ""
    echo "#   The script concurrent_git_merge.py will output: \"Your branch is ahead of ... by 1 commit."
  else
    echo "#   Nothing to commit."
  fi
}
