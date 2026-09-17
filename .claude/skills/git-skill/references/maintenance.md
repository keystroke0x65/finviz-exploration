# Repository maintenance

Contents: 1. Sync & prune · 2. Releases & tags · 3. Undoing mistakes · 4. Conflicts · 5. Removing a committed secret · 6. Health check

Run `scripts/detect_repo.py` before any of these. If `operation_in_progress` is set, finish or abort that operation first.

## 1. Sync & prune

```bash
git fetch --all --prune                 # update remote refs, drop deleted remote branches
git switch main && git pull --ff-only   # fast-forward main; if it fails, main has diverged — stop and ask
git branch --merged main | grep -vE '^\*|\bmain\b|\bmaster\b'   # candidates for deletion
git branch -d <branch>                  # -d refuses unmerged branches, which is the point
git branch -vv | grep ': gone]'         # local branches whose remote was deleted
```

Show the user the list before deleting branches. Use `git branch -D` only with approval, since it discards unmerged commits.

## 2. Releases & tags

Semantic versioning, derived from Conventional Commits since the last tag:
- any `!` or `BREAKING CHANGE:` → major (pre-1.0: minor)
- any `feat` → minor
- otherwise → patch

```bash
git describe --tags --abbrev=0                      # last tag
git log <last-tag>..HEAD --pretty=format:'%s (%h)'  # commits since
git tag -a v1.4.0 -m "v1.4.0"                       # annotated tags only
git push origin v1.4.0
```

Changelog: group commits under `### Features` (feat), `### Fixes` (fix), `### Other` (everything else worth mentioning), newest version at top of `CHANGELOG.md`. Commit it as `chore(release): v1.4.0` before tagging. If `gh` is available: `gh release create v1.4.0 --notes-file <notes>`.

Never move or delete a tag that has been pushed without asking.

## 3. Undoing mistakes (least → most destructive)

| Situation | Command | Destroys work? |
|---|---|---|
| Unstage a file | `git restore --staged <file>` | No |
| Fix last commit message/contents (not pushed) | `git commit --amend` | No |
| Undo a pushed commit | `git revert <sha>` | No (adds a new commit) |
| Undo last local commit, keep changes | `git reset --soft HEAD~1` | No |
| Set changes aside | `git stash push -m "msg"` | No |
| Discard uncommitted edits to a file | `git restore <file>` | **Yes**, ask first |
| Throw away local commits and changes | `git reset --hard <ref>` | **Yes**, ask first |
| Delete untracked files | `git clean -n` then `git clean -fd` | **Yes**, ask first |

Recovery: `git reflog` lists every position HEAD has been in the last ~90 days. `git switch -c rescue <sha>` restores a "lost" commit. Uncommitted, unstashed edits that were discarded are not recoverable, which is why the destructive rows require confirmation.

## 4. Conflicts

1. `git status` to list conflicted files.
2. For each file, read both sides and resolve based on what the code should do; don't just pick "ours" or "theirs" wholesale.
3. Remove all `<<<<<<<`, `=======`, `>>>>>>>` markers, then run tests/build if they exist.
4. `git add <file>`, then `git merge --continue` / `git rebase --continue`.
5. If it gets confusing: `git merge --abort` or `git rebase --abort` returns to the pre-operation state.

For lockfiles (`package-lock.json`, `pnpm-lock.yaml`), take one side and regenerate with the package manager rather than hand-merging.

## 5. Removing a committed secret

The secret is compromised the moment it's pushed. **Rotate it first**, and tell the user this is the most important step.

- Not yet pushed, last commit: `git rm --cached <file>`, add it to `.gitignore`, `git commit --amend`.
- Not yet pushed, older commit: interactive rebase to edit that commit (ask first).
- Already pushed: history rewrite with `git filter-repo --invert-paths --path <file>` (or `--replace-text`), then force-push with lease. This affects every clone and requires explicit user approval. On GitHub, cached views may persist; contact support for full removal if needed.

## 6. Health check

Run periodically or when the user asks "is my repo in good shape?":

- [ ] `detect_repo.py`: on the expected branch, no stuck operation, ahead/behind reasonable
- [ ] Uncommitted work older than a session? Suggest committing or stashing.
- [ ] `.gitignore` covers the stack (compare with `init_repo.py --dry-run` output on a copy, or check common entries manually)
- [ ] No tracked files that should be ignored: `git ls-files -i --exclude-standard -c`
- [ ] No large blobs: `git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | awk '$1=="blob" && $3>5000000'`
- [ ] Stale merged branches (section 1)
- [ ] Remote configured and pushed recently
- [ ] `git fsck --no-dangling` reports no errors
