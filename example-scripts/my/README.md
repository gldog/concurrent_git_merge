Merge Use Cases
=

# General

* The terms `SOURCE_BRANCH` and `DEST_BRANCH` are from the merge-script point of view.
* The terms `A` (ancestor commit), `ours` and `theirs` are from a merge driver point of view.
* The terms `Parent` and `Child` means branches (not commits).
* The term `M` describes a merge commit.
* When the server merges a pull request, no merge driver is involved!
  If versions must be protected, this have to be done by modifying the source branch before creating a pull request.
  In the following examples this is done by a merge driver using a merge branch.

In the following chapter merge use cases are discussed.
The merge driver [keep_ours_paths_merge_driver](https://github.com/gldog/keep_ours_paths_merge_driver) is involved.

# Update child branch from parent branch

Direkt merge from parent branch to child branch.

     A   SOURCE_BRANCH
    -*------*------------*---------  Parent (theirs)
      \                  |
       \           merge ↓
        *-------*--------*---------  Child (ours)
         DEST_BRANCH     M

* Pre-script: Clone or update the repo, install merge driver with merge strategy `onconflict-ours`.
* Merge driver: The merge driver protects versions on the child branch using merge strategy `onconflict-ours`.
* Merge branch: No
* Pull request: No
* Post-script: Probably needs only push the child branch.
  Can be done with the universal command:
  `--post-script 'bash -c "git push --set-upstream origin HEAD"'`

# Merge back a child branch to parent branch using a pull requst

First the child branch is updated, then a pull request is created from child to parent.

     A   SOURCE_BRANCH
    -*------*------------*---------  Parent (theirs)
      \                  |   ↑
       \                 |   | PR
        \          merge ↓   |
         *----*----------*---------  Child (ours)
         DEST_BRANCH     M

* Pre-script: Clone or update the repo, install merge driver with merge strategy `onconflict-ours`
* Merge driver: The merge driver protects versions on the child branch using merge strategy `onconflict-ours`.
* Merge branch: No
* Pull request: Yes, child branch > parent branch.
  When the server merges the pull request, no merge driver is involved!
* Post-script: Push the child branch, create the pull request.

Notes:

* In the pull request, versions on child branch can result in merge conflicts or the merge can overwrite versions on
  parent branch!

# Update child branch from parent branch using a merge banch and pull request

A merge-branch is created as preparation for a pull request.
Merge conflicts are resolved on the merge-branch before creating the pull request.
The merge is decoupled by using a pull request.
You can have a look what will be integrated into the child branch.

     A   SOURCE_BRANCH
    -*------*------------*---------  Parent (theirs)
      \            merge ↓
       \         --------*---------  merge (ours)
        \      /         M   ↓ PR
         *----*--------------------  Child
         DEST_BRANCH

* Pre-script: Clone or update the repo, install merge driver with merge strategy `onconflict-ours`.
* Merge driver: The merge driver protects versions on the child branch using merge strategy `onconflict-ours`.
* Merge branch: Yes
* Pull request: Yes, merge branch > child branch.
  When the server merges the pull request, no merge driver is involved!
* Post-script: Push the merge- and child branch, create the pull request.

# Merge back a child branch to parent branch directly

Direkt merge from child branch to parent branch.

     A   DEST_BRANCH     M
    -*------*------------*---------  Parent (ours)
      \            merge ↑
       \                 |
        \                |
         *----*----------*---------  Child (theirs)
         SOURCE_BRANCH 

* Pre-script: Clone or update the repo, install merge driver with merge strategy `always-ours`.
* Merge driver: The merge driver protects versions on the parent branch using merge strategy `always-ours`.
* Merge branch: No
* Pull request: No
* Post-script: Probably needs only push the child branch.
  Can be done with the universal command:
  `--post-script 'bash -c "git push --set-upstream origin HEAD"'`

# Merge back a child branch to parent branch using a merge branch and pull request

A merge-branch is created as preparation for a pull request.
Merge conflicts are resolved on the merge-branch before creating the pull request.

     A   DEST_BRANCH   
    -*------*----------------------  Parent
      \      \               ↑ PR
       \       ----------*---------  merge (ours)
        \          merge ↑
         *----*----------*---------  Child (theirs)
         SOURCE_BRANCH

* Pre-script: Clone or update the repo, install merge driver with merge strategy `always-ours`.
* Merge driver: The merge driver protects versions on the parent branch using merge strategy `always-ours`.
* Merge branch: Yes
* Pull request: Yes, merge branch > parent branch.
  When the server merges the pull request, no merge driver is involved!
* Post-script: Push the merge- and parent branch, create the pull request.

# TODO under construction: Example how to setup a parallel merge and using a merge driver

This demo combines two topics:

1. Demonstrate how to configure the merge_git_repos.py.
2. Demonstrate how to use a merge driver.

Directory content:

* clone_repos_and_install_mergedrivers.sh: Pre-script
* keep_ours_paths_merge_driver.pyz: Merge driver, located here but not checked-in.
  It is the result of project [keep-ours-paths-merge-driver](https://github.com/gldog/keep-ours-paths-merge-driver).
* merge-demo.sh: Overall script
* post-script.sh: Post-script (under development, not checked-in yet)

The overall script merge-demo.sh configures and calls merge_git_repos.py.
merge_git_repos.py calls the pre-script and triggers the `git merge`.
The `git merge` calls the merge driver.

# Chars

◦●○◎◉⦿⧸⧹⧵∕∖⎮⋰⋱⋮⦦⦧↑↓⬇︎↧↥↘︎↗︎⎯⏐—¦|/\
