# Experience — dev-environment

<!-- Entry file (procedural lessons). Created automatically on first ADD_ROOT to experience/dev-environment.md.
     roots = general lessons, deltas = condition-specific variations (when=), traps = failure records. -->

## Lessons
<!-- empty: reusable strategies that worked, with the reason they work -->
- [dev-environment-0002] root h=1 x=0 d=2026-10-20 labels=git,worktree,env src="worktree cleanup 2026-10-20" :: Feature worktrees under .worktrees/ can hold the only copy of gitignored local files (.env with FINVIZ_API_TOKEN, backend/finviz_dashboard.db). Before git worktree remove, check git status --ignored and copy .env to the main checkout.
- [dev-environment-0003] root h=0 x=0 d=2026-10-21 labels=docker,wsl,ports,smoke-test src="phase 2 M1 smoke test 2026-10-20" :: Docker may be unavailable from WSL (Docker Desktop integration off) and port 5173 is often taken by another project's vite. Smoke-test instead with backend/.venv uvicorn --port 8000 (DB_PATH in scratchpad, env from .env) plus 'npx vite --port 5174 --strictPort'.

## Traps
<!-- empty: approaches that failed: what was tried, what happened, what to do instead -->
- [dev-environment-0001] trap h=0 x=0 d=2026-09-17 labels=git,wsl,gitignore src="git-skill init_repo.py output, 2026-09-17" :: FAILED: git-skill's default .gitignore doesn't exclude WSL *:Zone.Identifier files or __pycache__/*.pyc, so init_repo's first commit included them as noise. INSTEAD: add "__pycache__/", "*.pyc", "*:Zone.Identifier" to .gitignore and git rm --cached matches right after init.
- [dev-environment-0004] trap h=0 x=0 d=2026-10-21 labels=shell,pkill src="session 2026-10-20" :: FAILED: kill $(pgrep -f '<pattern>') to stop a background server -> also matched and killed the invoking bash shell. INSTEAD: get the PID from 'ss -ltnp' on the port, or pgrep -f with a pattern anchored to the binary path, and check the list before killing.
