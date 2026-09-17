# Experience — dev-environment

<!-- Entry file (procedural lessons). Created automatically on first ADD_ROOT to experience/dev-environment.md.
     roots = general lessons, deltas = condition-specific variations (when=), traps = failure records. -->

## Lessons
<!-- empty: reusable strategies that worked, with the reason they work -->

## Traps
<!-- empty: approaches that failed: what was tried, what happened, what to do instead -->
- [dev-environment-0001] trap h=0 x=0 d=2026-09-17 labels=git,wsl,gitignore src="git-skill init_repo.py output, 2026-09-17" :: FAILED: git-skill's default .gitignore doesn't exclude WSL *:Zone.Identifier files or __pycache__/*.pyc, so init_repo's first commit included them as noise. INSTEAD: add "__pycache__/", "*.pyc", "*:Zone.Identifier" to .gitignore and git rm --cached matches right after init.
