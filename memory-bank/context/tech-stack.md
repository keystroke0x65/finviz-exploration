# Tech Stack — finviz-exploration

<!-- Entry file. Versions, tooling, environments, and the commands that actually work. -->

## Runtime and frameworks
<!-- empty: languages, frameworks, key libraries with versions -->
- [stack-0001] root h=1 x=0 d=2026-09-17 labels=python,fastapi,react,typescript src="user decision 2026-09-17" :: Backend: Python + FastAPI. Frontend: React + TypeScript (Vite). Chosen so pandas can handle Finviz's CSV-shaped export data and screener manipulation naturally.

## Services and infrastructure
<!-- empty: hosting, databases, storage, CI/CD -->

## Dev environment
<!-- empty: setup steps, env var NAMES (never values), local services -->
- [stack-0003] root h=0 x=0 d=2026-09-17 labels=docker,dev-environment src="user decision 2026-09-17" :: Docker Compose used for local dev (backend, frontend, SQLite volume as services), not plain local processes, per explicit user preference.

## Commands
<!-- empty: build, test, lint, run, deploy commands verified to work -->

## Storage
- [stack-0002] root h=0 x=0 d=2026-09-17 labels=sqlite,database src="user decision 2026-09-17" :: SQLite for local persistence (response cache, later saved screens/watchlists/portfolio data). Chosen over Postgres since this is local-only single-user.

## External APIs
- [stack-0005] root h=0 x=0 d=2026-09-17 labels=schwab,options,api src="user" :: Schwab developer API (user has a Schwab/thinkorswim brokerage account) will supply options chains and greeks. Requires a developer app approval process that can take days, so should be started early/in parallel.
- [stack-0006] root h=0 x=0 d=2026-10-20 labels=finviz,api src="backend/app/finviz_client.py" supersedes=stack-0004 :: Finviz Elite export API: quotes via https://elite.finviz.com/export/screener?v=111&t=TICKER&auth=<FINVIZ_API_TOKEN> (CSV, Overview view). /export.ashx is a legacy 301 alias; /export/stock returns historical bars, not quotes. Finviz has NO options data on any tier.
