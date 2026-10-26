# Experience — dev-environment

<!-- Entry file (procedural lessons). Created automatically on first ADD_ROOT to experience/dev-environment.md.
     roots = general lessons, deltas = condition-specific variations (when=), traps = failure records. -->

## Lessons
<!-- empty: reusable strategies that worked, with the reason they work -->
- [dev-environment-0002] root h=1 x=0 d=2026-10-20 labels=git,worktree,env src="worktree cleanup 2026-10-20" :: Feature worktrees under .worktrees/ can hold the only copy of gitignored local files (.env with FINVIZ_API_TOKEN, backend/finviz_dashboard.db). Before git worktree remove, check git status --ignored and copy .env to the main checkout.
- [dev-environment-0003] root h=1 x=0 d=2026-10-21 labels=docker,wsl,ports,smoke-test src="phase 2 M1 smoke test 2026-10-20" :: Docker may be unavailable from WSL (Docker Desktop integration off) and port 5173 is often taken by another project's vite. Smoke-test instead with backend/.venv uvicorn --port 8000 (DB_PATH in scratchpad, env from .env) plus 'npx vite --port 5174 --strictPort'.
- [dev-environment-0005] root h=1 x=0 d=2026-10-21 labels=screenshots,playwright,ui src="session 2026-10-20" :: Visual UI checks: install playwright-core in a scratchpad dir and launch /usr/bin/google-chrome headless (browsers also cached in ~/.cache/ms-playwright); click through tabs and screenshot desktop 1440x900 and mobile 390x844. Caught table overflow (grid child needs min-width:0) that tests missed.

## Traps
<!-- empty: approaches that failed: what was tried, what happened, what to do instead -->
- [dev-environment-0001] trap h=0 x=0 d=2026-09-17 labels=git,wsl,gitignore src="git-skill init_repo.py output, 2026-09-17" :: FAILED: git-skill's default .gitignore doesn't exclude WSL *:Zone.Identifier files or __pycache__/*.pyc, so init_repo's first commit included them as noise. INSTEAD: add "__pycache__/", "*.pyc", "*:Zone.Identifier" to .gitignore and git rm --cached matches right after init.
- [dev-environment-0004] trap h=0 x=0 d=2026-10-21 labels=shell,pkill src="session 2026-10-20" :: FAILED: kill $(pgrep -f '<pattern>') to stop a background server -> also matched and killed the invoking bash shell. INSTEAD: get the PID from 'ss -ltnp' on the port, or pgrep -f with a pattern anchored to the binary path, and check the list before killing.
- [dev-environment-0006] trap h=0 x=0 d=2026-10-21 labels=docker,uvicorn,reload src="session 2026-10-21" :: FAILED: editing backend files while the Docker stack runs -> uvicorn --reload restarts the lifespan, which runs a feeder tick + full scan immediately (extra Finviz load, can collide with manual scripts). INSTEAD: stop the backend container (docker compose stop backend) before live Finviz scripts.
- [dev-environment-0007] trap h=0 x=0 d=2026-10-21 labels=git,testing,shell src="cleanup batch 2026-10-21" :: FAILED: 'pytest -q | tail -1 && git commit' -> the pipe's exit code is tail's, so a failing suite still committed (commit 37e03a2). INSTEAD: gate commits on the test command itself (run pytest/npm test without a pipe, or set -o pipefail) and only then commit.
- [dev-environment-0008] root h=0 x=0 d=2026-10-26 labels=scanner,snapshots,regression src="2026-10-26 incident" :: ticker_snapshots stores ScreenRow as json.dumps(asdict(row)); changing a ScreenRow field to a non-JSON type (datetime) crashed every full scan silently (feeder kept running, Setups went stale ~45 min). Grep for asdict(ScreenRow)/snapshots when changing ScreenRow; after merging, trigger a full scan and check ticker_scans.scanned_at moves.
