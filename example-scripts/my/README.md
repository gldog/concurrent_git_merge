Example how to setup a parallel merge and using a merge driver
=

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
