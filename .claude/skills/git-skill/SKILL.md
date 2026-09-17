---
name: git-skill
description: Create, update, and maintain git repositories safely. Use this skill whenever the user wants to start, set up, or initialize a project or repo; commit, save, checkpoint, or "push" work; write commit messages; create or switch branches; tag a release; sync with or add a remote; clean up branches; fix a messy git state; or whenever Claude is about to modify files in a project folder and needs to know whether it is under version control. Always run the detection step first. If no repository exists, this skill initializes one automatically with a stack-aware .gitignore and a safe initial commit. Trigger even when the user doesn't say "git" (e.g. "save my progress", "set up this project", "version this folder").
---

# git-skill

Handles the full lifecycle of a git repository: **detect → create (if missing) → update → maintain**. Helper scripts live in `scripts/` (Python 3, standard library only) and print JSON so results are easy to reason about.

## Step 0: Always detect first

Before any git work, run:

```bash
python3 <skill-dir>/scripts/detect_repo.py [path]   # path defaults to cwd
```

Read the JSON and branch on `state`:

| state | meaning | what to do |
|---|---|---|
| `no_git` | git isn't installed | Tell the user; stop. |
| `no_repo` | folder isn't tracked by any repo | Go to **Create** (auto-init is the default). |
| `nested` | folder sits *inside* a parent repo (`repo_root` ≠ `path`) | Don't init silently. Ask whether they meant to work in the parent repo or want a separate repo here. |
| `repo` | folder is a repo root | Go to **Update** or **Maintain** as the task requires. |

Also note `unsafe_location` (true for `/`, the home directory, and system dirs). Never auto-init there; initializing your whole home folder as a repo is a classic, painful mistake. Ask the user which project folder they meant.

## Create: initialize a repo when none exists

When `state` is `no_repo` and the location is safe, initialize without waiting for permission, then report what happened. The user has asked for this behavior: a missing repo is a gap to fill, not a question to ask.

```bash
python3 <skill-dir>/scripts/init_repo.py [path] [--branch main] [--dry-run] [--no-commit]
```

The script:

1. Detects the stack from marker files (`package.json`, `next.config.*`, `astro.config.*`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `go.mod`, `Dockerfile`, etc.).
2. Runs `git init` with default branch `main`.
3. Writes a `.gitignore` combining a common base (OS files, editor files, `.env*`) with per-stack rules. If a `.gitignore` already exists, it only appends missing lines.
4. Checks for files that should never be committed (`.env`, private keys, credentials) and files over 50 MB, and makes sure they are ignored or flagged.
5. Stages everything and runs `scripts/check_staged.py` for secret patterns.
6. Makes the initial commit `chore: initial commit` **only if** the secret check passes and `user.name`/`user.email` are configured. Otherwise it leaves files staged and reports why.

Use `--dry-run` first if the folder has a lot of unfamiliar content or the user seems unsure. After it runs, summarize for the user: branch name, detected stack, what went into `.gitignore`, file count committed, and any warnings.

A README or license is not created automatically. Offer them if the project has neither.

**Remote setup is a separate step.** Don't create a GitHub repo or add a remote unless the user asks. When they do:
- If `gh` is available and authenticated (`gh auth status`): `gh repo create <name> --private --source . --remote origin --push`. Default to **private** unless told otherwise.
- Otherwise: `git remote add origin <url>` then `git push -u origin main`.

## Update: day-to-day commits and branches

### Before every commit
1. `git status --short` and `git diff --stat` to see what changed.
2. Stage deliberately. Prefer `git add <paths>` for the files related to one change; `git add -A` is fine when every change belongs together.
3. Run `python3 <skill-dir>/scripts/check_staged.py`. If it reports findings, unstage those files and tell the user. Don't commit secrets "just this once"; removing them from history later is much harder than not committing them.

### Commit messages: Conventional Commits
Format: `type(scope): summary` in imperative mood, lowercase, no trailing period, ≤72 chars. Add a body (blank line, then wrapped text) when the *why* isn't obvious.

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Append `!` for breaking changes (`feat(api)!: drop v1 endpoints`).

Examples:
- Added Clerk sign-in page → `feat(auth): add sign-in page with Clerk`
- Fixed extension crashing on empty share URL → `fix(extension): handle empty share url`
- Updated memory-bank files → `docs(memory-bank): update active context`

One logical change per commit. If the working tree mixes unrelated changes, split them into separate commits rather than writing a vague "update stuff" message.

### Branches
- Naming: `type/short-kebab-description` (e.g. `feat/artifact-marketplace`, `fix/clerk-dev-redirect`).
- Create from an up-to-date base: `git switch main && git pull --ff-only && git switch -c feat/x`.
- Solo projects may commit directly to `main` for small changes. Use a branch for anything experimental or multi-session.

### Pushing
- `git push` for tracked branches; `git push -u origin <branch>` the first time.
- If the push is rejected because the remote moved ahead, `git pull --rebase` on your own feature branch, or `git pull --ff-only` / merge on shared branches, then push again.

## Maintain: health and housekeeping

For anything beyond everyday commits, read `references/maintenance.md`. It covers:
- syncing and pruning (`fetch --prune`, deleting merged branches)
- releases (semantic version tags, changelog from Conventional Commits)
- undoing mistakes (amend, revert, reset, reflog recovery), from least to most destructive
- conflict resolution
- removing a committed secret
- a periodic health check checklist

## Safety rules

These protect work that can't be recovered. Follow them even if a shortcut seems faster.

- **Never** `git push --force` to `main`/`master` or any shared branch. On your own feature branch, use `--force-with-lease`, never bare `--force`.
- **Never** rewrite published history (rebase, amend, reset of pushed commits on shared branches) without explicit user approval.
- **Ask before destructive commands**: `reset --hard`, `clean -fd`, `branch -D`, `checkout -- <file>`/`restore` on uncommitted work, `stash drop`, `filter-repo`. Show what would be lost first (`git status`, `git clean -n`, `git log`).
- If something went wrong, check `git reflog` before concluding work is lost.
- Don't change global git config (`--global`) without asking. If `user.name`/`user.email` is missing, tell the user and suggest the command rather than inventing an identity.
- Don't run `git init` inside an existing repo, in the home directory, or at filesystem root.

## Reporting back

After git operations, give a short summary: what ran, the resulting branch and commit (short hash plus message), and anything the user needs to act on (missing identity, flagged secrets, no remote yet). Don't dump raw command output unless something failed.
