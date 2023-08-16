#!/bin/bash

REPOS_DIR="/Users/jo/prj-test/merge_git_repos/repos"

git -C "$REPOS_DIR/mb" config --local merge.maven-pomxml-keep-ours-xpath-merge-driver.driver 'keep_ours_paths_merge_driver.pyz -O %O -A %A -B %B -P ./%P -p ./version ./parent/version ./properties/revision ./properties/:.+[.]version'
git -C "$REPOS_DIR/mb" config --local merge.npm-packagejson-keep-ours-jpath-merge-driver.driver 'keep_ours_paths_merge_driver.pyz -t JSON -O %O -A %A -B %B -P ./%P -p version dependencies:@comdirect/.+'

git -C "$REPOS_DIR/td" config --local merge.maven-pomxml-keep-ours-xpath-merge-driver.driver 'keep_ours_paths_merge_driver.pyz -O %O -A %A -B %B -P ./%P -p ./version ./parent/version ./properties/revision ./properties/:.+[.]version'
git -C "$REPOS_DIR/td" config --local merge.npm-packagejson-keep-ours-jpath-merge-driver.driver 'keep_ours_paths_merge_driver.pyz -t JSON -O %O -A %A -B %B -P ./%P -p version dependencies:@comdirect/.+'
