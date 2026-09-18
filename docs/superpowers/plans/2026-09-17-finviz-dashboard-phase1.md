# Finviz Dashboard Phase 1: Foundation + Stock Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational FastAPI backend + React frontend that lets the user
look up a single stock ticker and see its quote/fundamentals, sourced from the Finviz
Elite export API.

**Architecture:** React (Vite/TS) frontend calls a FastAPI backend, which is the only
thing that talks to Finviz. The backend wraps Finviz's CSV export endpoints behind a
typed `finviz_client` module, caches parsed responses in SQLite (15 min TTL), and
exposes them as JSON over `/api/stocks/{ticker}`. Everything runs locally via Docker
Compose.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pandas, requests, pytest, SQLite
(stdlib `sqlite3`); React 18, TypeScript, Vite, vitest; Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-17-finviz-dashboard-phase1-design.md`

## Global Constraints

- Backend owns all external API calls; the frontend never calls Finviz directly.
- Finviz Elite auth token lives only in backend environment variables (`.env`,
  gitignored) — never logged, never sent to the frontend, never committed. Add new env
  vars to `.env.example` with a placeholder value.
- No live Finviz HTTP calls in automated tests — mock the HTTP layer.
- Errors fail loudly with context (no silent empty-data returns); invalid ticker,
  no-data, and auth-failure are distinct, user-visible error cases.
- Dev environment runs via Docker Compose (backend, frontend, SQLite volume) — not
  plain local processes.
- No charts, no screener, no options, no auth/multi-user in this phase (see spec's
  "Explicitly out of scope").
- Cache TTL defaults to 15 minutes, configurable via env var.

---

## Task 1: Project scaffold + Docker Compose

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Modify: `.gitignore` (add `backend/.venv/`, `frontend/node_modules/`,
  `frontend/dist/`, `*.db`)

**Interfaces:**
- Produces: a running FastAPI app at `http://localhost:8000` with `GET /health` →
  `{"status": "ok"}`, and a running Vite dev server at `http://localhost:5173` showing
  a placeholder page. Later tasks build inside `backend/app/` and `frontend/src/`.

- [ ] **Step 1: Create backend Python project**

`backend/pyproject.toml`:
```toml
[project]
name = "finviz-dashboard-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pandas>=2.2",
    "requests>=2.32",
    "pydantic-settings>=2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-mock>=3.14",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`backend/app/__init__.py`: empty file.

`backend/app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="Finviz Dashboard API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 2: Create backend Dockerfile**

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app ./app
COPY scripts ./scripts

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

`backend/.dockerignore`:
```
.venv/
__pycache__/
*.pyc
tests/
.pytest_cache/
```

- [ ] **Step 3: Scaffold frontend with Vite**

`frontend/package.json`:
```json
{
  "name": "finviz-dashboard-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "vite": "^5.4.10",
    "vitest": "^2.1.4"
  }
}
```

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Finviz Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/main.tsx`:
```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`frontend/src/App.tsx`:
```typescript
export default function App() {
  return <div>Finviz Dashboard</div>;
}
```

- [ ] **Step 4: Create frontend Dockerfile**

`frontend/Dockerfile`:
```dockerfile
FROM node:22-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]
```

`frontend/.dockerignore`:
```
node_modules/
dist/
```

- [ ] **Step 5: Create Docker Compose config**

`docker-compose.yml`:
```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
      - ./backend/scripts:/app/scripts
      - db-data:/data
    env_file:
      - .env
    environment:
      - DB_PATH=/data/finviz_dashboard.db

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src
    depends_on:
      - backend

volumes:
  db-data:
```

- [ ] **Step 6: Create `.env.example`**

`.env.example`:
```
FINVIZ_API_TOKEN=your-finviz-elite-token-here
QUOTE_CACHE_TTL_MINUTES=15
```

- [ ] **Step 7: Extend `.gitignore` for backend/frontend build artifacts**

Add to `.gitignore`:
```
backend/.venv/
backend/__pycache__/
backend/.pytest_cache/
frontend/node_modules/
frontend/dist/
*.db
```

- [ ] **Step 8: Verify the stack builds and runs**

Run: `docker compose up --build`
Expected: both services start; `curl http://localhost:8000/health` returns
`{"status":"ok"}`; `http://localhost:5173` serves the placeholder page.

- [ ] **Step 9: Commit**

```bash
git add backend/ frontend/ docker-compose.yml .env.example .gitignore
git commit -m "chore: scaffold FastAPI backend and React frontend with Docker Compose"
```

---

## Task 2: Finviz client — quote fetching with error handling

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/errors.py`
- Create: `backend/app/finviz_client.py`
- Create: `backend/tests/test_finviz_client.py`
- Create: `backend/tests/fixtures/quote_valid.csv`
- Create: `backend/tests/fixtures/quote_empty.csv`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `get_settings() -> Settings` (with `.finviz_api_token: str`,
  `.quote_cache_ttl_minutes: int`) from `app.config`; `TickerNotFoundError`,
  `FinvizAuthError` from `app.errors`; `get_quote(ticker: str) -> dict` from
  `app.finviz_client`, raising those errors on failure and returning a `dict` of
  column name → value on success. Task 3 (cache) and Task 4 (routes) call
  `get_quote`.

- [ ] **Step 1: Write the failing test for config loading**

`backend/tests/test_finviz_client.py` (start of file):
```python
import pytest
import responses

from app.config import get_settings
from app.errors import FinvizAuthError, TickerNotFoundError
from app.finviz_client import get_quote


def test_get_settings_reads_env(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token-123")
    monkeypatch.setenv("QUOTE_CACHE_TTL_MINUTES", "30")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.finviz_api_token == "test-token-123"
    assert settings.quote_cache_ttl_minutes == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_finviz_client.py::test_get_settings_reads_env -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Implement config module**

`backend/app/config.py`:
```python
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    finviz_api_token: str
    quote_cache_ttl_minutes: int = 15
    db_path: str = "finviz_dashboard.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_finviz_client.py::test_get_settings_reads_env -v`
Expected: PASS

- [ ] **Step 5: Write the failing tests for `get_quote` (happy path, not found, auth failure)**

Add to `backend/tests/test_finviz_client.py`:
```python
FINVIZ_EXPORT_URL = "https://elite.finviz.com/export.ashx"

VALID_QUOTE_CSV = (
    "Ticker,Company,Sector,Price,Change,Volume,Market Cap,P/E\n"
    "AAPL,Apple Inc.,Technology,227.52,1.35%,48291012,3.45T,34.2\n"
)

EMPTY_CSV = "Ticker,Company,Sector,Price,Change,Volume,Market Cap,P/E\n"


@responses.activate
def test_get_quote_returns_parsed_fields(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=VALID_QUOTE_CSV,
        status=200,
    )

    result = get_quote("AAPL")

    assert result["Ticker"] == "AAPL"
    assert result["Price"] == "227.52"
    assert result["Sector"] == "Technology"


@responses.activate
def test_get_quote_raises_not_found_for_empty_csv(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    get_settings.cache_clear()
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body=EMPTY_CSV,
        status=200,
    )

    with pytest.raises(TickerNotFoundError, match="ZZZZINVALID"):
        get_quote("ZZZZINVALID")


@responses.activate
def test_get_quote_raises_auth_error_on_401(monkeypatch):
    monkeypatch.setenv("FINVIZ_API_TOKEN", "bad-token")
    get_settings.cache_clear()
    responses.add(
        responses.GET,
        FINVIZ_EXPORT_URL,
        body="Invalid auth token",
        status=401,
    )

    with pytest.raises(FinvizAuthError):
        get_quote("AAPL")
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_finviz_client.py -v`
Expected: FAIL — `get_quote` doesn't exist yet (`ImportError`), and `responses` package
not yet installed.

Add `responses>=0.25` to the `dev` dependencies in `backend/pyproject.toml`, then run
`pip install -e ".[dev]"` inside the backend environment.

- [ ] **Step 7: Implement error types**

`backend/app/errors.py`:
```python
class TickerNotFoundError(Exception):
    """Raised when Finviz has no data for the requested ticker."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"No Finviz data found for ticker '{ticker}'")


class FinvizAuthError(Exception):
    """Raised when the Finviz Elite API rejects our auth token."""

    def __init__(self):
        super().__init__(
            "Finviz Elite API rejected the configured auth token. "
            "Check FINVIZ_API_TOKEN in .env."
        )
```

- [ ] **Step 8: Implement the Finviz client**

`backend/app/finviz_client.py`:
```python
import io

import pandas as pd
import requests

from app.config import get_settings
from app.errors import FinvizAuthError, TickerNotFoundError

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export.ashx"

# Finviz's quote export view code; "152" returns the overview column set
# (price, sector, market cap, P/E, etc.) used by the /api/stocks endpoint.
QUOTE_VIEW = "152"


def get_quote(ticker: str) -> dict:
    settings = get_settings()
    response = requests.get(
        FINVIZ_EXPORT_URL,
        params={
            "v": QUOTE_VIEW,
            "t": ticker,
            "auth": settings.finviz_api_token,
        },
        timeout=10,
    )

    if response.status_code == 401:
        raise FinvizAuthError()
    response.raise_for_status()

    df = pd.read_csv(io.StringIO(response.text))
    if df.empty:
        raise TickerNotFoundError(ticker)

    return df.iloc[0].to_dict()
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_finviz_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 10: Commit**

```bash
git add backend/app/config.py backend/app/errors.py backend/app/finviz_client.py \
  backend/tests/test_finviz_client.py backend/pyproject.toml
git commit -m "feat: add Finviz client with typed errors for quote lookup"
```

---

## Task 3: SQLite quote cache

**Files:**
- Create: `backend/app/cache.py`
- Create: `backend/tests/test_cache.py`

**Interfaces:**
- Consumes: `get_settings()` from `app.config` (for `db_path`,
  `quote_cache_ttl_minutes`).
- Produces: `get_cached_quote(ticker: str) -> dict | None` and
  `set_cached_quote(ticker: str, data: dict) -> None` from `app.cache`. Task 4 (routes)
  calls both.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_cache.py`:
```python
import json
import sqlite3
import time

import pytest

from app.cache import get_cached_quote, set_cached_quote
from app.config import get_settings


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FINVIZ_API_TOKEN", "test-token")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("QUOTE_CACHE_TTL_MINUTES", "15")
    get_settings.cache_clear()
    return db_path


def test_set_then_get_returns_same_data(temp_db):
    set_cached_quote("AAPL", {"Ticker": "AAPL", "Price": "227.52"})

    result = get_cached_quote("AAPL")

    assert result == {"Ticker": "AAPL", "Price": "227.52"}


def test_get_returns_none_for_uncached_ticker(temp_db):
    result = get_cached_quote("MSFT")

    assert result is None


def test_get_returns_none_for_expired_entry(temp_db):
    set_cached_quote("AAPL", {"Ticker": "AAPL", "Price": "227.52"})
    conn = sqlite3.connect(temp_db)
    stale_time = time.time() - (16 * 60)
    conn.execute(
        "UPDATE quote_cache SET fetched_at = ? WHERE ticker = ?",
        (stale_time, "AAPL"),
    )
    conn.commit()
    conn.close()

    result = get_cached_quote("AAPL")

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cache'`

- [ ] **Step 3: Implement the cache module**

`backend/app/cache.py`:
```python
import json
import sqlite3
import time

from app.config import get_settings


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_cache (
            ticker TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            fetched_at REAL NOT NULL
        )
        """
    )
    return conn


def get_cached_quote(ticker: str) -> dict | None:
    settings = get_settings()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT data, fetched_at FROM quote_cache WHERE ticker = ?",
            (ticker,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    data, fetched_at = row
    ttl_seconds = settings.quote_cache_ttl_minutes * 60
    if time.time() - fetched_at > ttl_seconds:
        return None

    return json.loads(data)


def set_cached_quote(ticker: str, data: dict) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO quote_cache (ticker, data, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET data = excluded.data, fetched_at = excluded.fetched_at
            """,
            (ticker, json.dumps(data), time.time()),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_cache.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/cache.py backend/tests/test_cache.py
git commit -m "feat: add SQLite-backed quote cache with TTL expiry"
```

---

## Task 4: `/api/stocks/{ticker}` route

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/routes/stocks.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_stocks_route.py`

**Interfaces:**
- Consumes: `get_quote(ticker)` from `app.finviz_client`; `get_cached_quote`,
  `set_cached_quote` from `app.cache`; `TickerNotFoundError`, `FinvizAuthError` from
  `app.errors`.
- Produces: `router` (a `fastapi.APIRouter`) from `app.routes.stocks`, mounted on
  `app` in `main.py`. `GET /api/stocks/{ticker}` returns `QuoteResponse` JSON;
  `GET /api/stocks/{ticker}/refresh` bypasses the cache.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_stocks_route.py`:
```python
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.errors import FinvizAuthError, TickerNotFoundError
from app.main import app

client = TestClient(app)

QUOTE_DATA = {"Ticker": "AAPL", "Company": "Apple Inc.", "Price": "227.52"}


@patch("app.routes.stocks.get_cached_quote", return_value=None)
@patch("app.routes.stocks.set_cached_quote")
@patch("app.routes.stocks.get_quote", return_value=QUOTE_DATA)
def test_get_stock_returns_quote_on_cache_miss(mock_get_quote, mock_set, mock_get_cached):
    response = client.get("/api/stocks/AAPL")

    assert response.status_code == 200
    assert response.json()["Ticker"] == "AAPL"
    mock_get_quote.assert_called_once_with("AAPL")
    mock_set.assert_called_once_with("AAPL", QUOTE_DATA)


@patch("app.routes.stocks.get_cached_quote", return_value=QUOTE_DATA)
@patch("app.routes.stocks.get_quote")
def test_get_stock_uses_cache_on_hit(mock_get_quote, mock_get_cached):
    response = client.get("/api/stocks/AAPL")

    assert response.status_code == 200
    assert response.json()["Ticker"] == "AAPL"
    mock_get_quote.assert_not_called()


@patch("app.routes.stocks.get_cached_quote", return_value=None)
@patch("app.routes.stocks.get_quote", side_effect=TickerNotFoundError("ZZZZ"))
def test_get_stock_returns_404_for_unknown_ticker(mock_get_quote, mock_get_cached):
    response = client.get("/api/stocks/ZZZZ")

    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]


@patch("app.routes.stocks.get_cached_quote", return_value=None)
@patch("app.routes.stocks.get_quote", side_effect=FinvizAuthError())
def test_get_stock_returns_502_on_auth_failure(mock_get_quote, mock_get_cached):
    response = client.get("/api/stocks/AAPL")

    assert response.status_code == 502
    assert "auth token" in response.json()["detail"]


@patch("app.routes.stocks.set_cached_quote")
@patch("app.routes.stocks.get_cached_quote", return_value=QUOTE_DATA)
@patch("app.routes.stocks.get_quote", return_value=QUOTE_DATA)
def test_refresh_bypasses_cache(mock_get_quote, mock_get_cached, mock_set):
    response = client.get("/api/stocks/AAPL/refresh")

    assert response.status_code == 200
    mock_get_quote.assert_called_once_with("AAPL")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_stocks_route.py -v`
Expected: FAIL — `app.routes.stocks` does not exist.

- [ ] **Step 3: Implement the response schema**

`backend/app/schemas.py`:
```python
from pydantic import BaseModel, ConfigDict


class QuoteResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    Ticker: str
    Company: str | None = None
    Price: str | None = None
```

- [ ] **Step 4: Implement the route**

`backend/app/routes/__init__.py`: empty file.

`backend/app/routes/stocks.py`:
```python
from fastapi import APIRouter, HTTPException

from app.cache import get_cached_quote, set_cached_quote
from app.errors import FinvizAuthError, TickerNotFoundError
from app.finviz_client import get_quote
from app.schemas import QuoteResponse

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


def _fetch_quote(ticker: str, *, use_cache: bool) -> QuoteResponse:
    ticker = ticker.upper()

    if use_cache:
        cached = get_cached_quote(ticker)
        if cached is not None:
            return QuoteResponse(**cached)

    try:
        data = get_quote(ticker)
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FinvizAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    set_cached_quote(ticker, data)
    return QuoteResponse(**data)


@router.get("/{ticker}", response_model=QuoteResponse)
def get_stock(ticker: str) -> QuoteResponse:
    return _fetch_quote(ticker, use_cache=True)


@router.get("/{ticker}/refresh", response_model=QuoteResponse)
def refresh_stock(ticker: str) -> QuoteResponse:
    return _fetch_quote(ticker, use_cache=False)
```

- [ ] **Step 5: Mount the router**

Modify `backend/app/main.py`:
```python
from fastapi import FastAPI

from app.routes.stocks import router as stocks_router

app = FastAPI(title="Finviz Dashboard API")
app.include_router(stocks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_stocks_route.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Run the full backend test suite**

Run: `cd backend && pytest -v`
Expected: PASS (all tests from Tasks 2-4)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/routes/ backend/app/main.py \
  backend/tests/test_stocks_route.py
git commit -m "feat: add /api/stocks/{ticker} route with cache and error mapping"
```

---

## Task 5: Manual Finviz sanity-check script

**Files:**
- Create: `backend/scripts/finviz_sanity_check.py`
- Create: `backend/scripts/README.md`

**Interfaces:**
- Consumes: `get_quote(ticker)` from `app.finviz_client`.
- Produces: a standalone script, not imported by application code.

- [ ] **Step 1: Write the script**

`backend/scripts/finviz_sanity_check.py`:
```python
"""Manual check that the Finviz Elite export API integration still works.

Not run in CI (hits the real Finviz API and requires a valid FINVIZ_API_TOKEN).
Run manually after Finviz changes something on their end, or when debugging
an unexpected TickerNotFoundError/FinvizAuthError in production use.

Usage:
    cd backend && python -m scripts.finviz_sanity_check AAPL
"""

import sys

from app.errors import FinvizAuthError, TickerNotFoundError
from app.finviz_client import get_quote


def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Fetching live Finviz quote for {ticker}...")

    try:
        data = get_quote(ticker)
    except TickerNotFoundError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
    except FinvizAuthError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    print("OK. Sample fields:")
    for key in ("Ticker", "Company", "Price", "Sector"):
        print(f"  {key}: {data.get(key)}")


if __name__ == "__main__":
    main()
```

`backend/scripts/README.md`:
```markdown
# Scripts

## finviz_sanity_check.py

Manual, live check that the Finviz Elite export API integration still works.
Not run in CI. Run this after Finviz changes something on their end, or when
debugging an unexpected error from the /api/stocks endpoint.

Requires `FINVIZ_API_TOKEN` set in the environment (e.g. via `.env` loaded by
Docker Compose, or exported manually).

    cd backend && python -m scripts.finviz_sanity_check AAPL
```

- [ ] **Step 2: Verify the script runs against the real API**

Run: `cd backend && FINVIZ_API_TOKEN=<your real token> python -m scripts.finviz_sanity_check AAPL`
Expected: prints `OK. Sample fields:` followed by Ticker/Company/Price/Sector values.

(This step needs your real Finviz Elite token from `.env` — run it manually, it's not
part of the automated test suite.)

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/finviz_sanity_check.py backend/scripts/README.md
git commit -m "chore: add manual Finviz API sanity-check script"
```

---

## Task 6: Frontend stock search + quote table

**Files:**
- Create: `frontend/src/api/stocks.ts`
- Create: `frontend/src/components/StockSearch.tsx`
- Create: `frontend/src/components/QuoteTable.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/api/stocks.test.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test-setup.ts`

**Interfaces:**
- Consumes: backend `GET /api/stocks/{ticker}` (proxied through Vite dev server at
  `/api/stocks/{ticker}`, see Task 1's `vite.config.ts`).
- Produces: `fetchQuote(ticker: string): Promise<Quote>` and the `Quote` type from
  `src/api/stocks.ts`; `<StockSearch onSearch={(ticker: string) => void} />` and
  `<QuoteTable quote={Quote | null} error={string | null} isLoading={boolean} />`
  components, composed in `App.tsx`.

- [ ] **Step 1: Add test tooling config**

`frontend/vitest.config.ts`:
```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
```

`frontend/src/test-setup.ts`:
```typescript
import "@testing-library/jest-dom/vitest";
```

Add to `frontend/package.json` devDependencies:
```json
"@testing-library/jest-dom": "^6.6.3",
"@testing-library/react": "^16.0.1",
"jsdom": "^25.0.1"
```

Run: `cd frontend && npm install`

- [ ] **Step 2: Write the failing test for the API client**

`frontend/src/api/stocks.test.ts`:
```typescript
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchQuote } from "./stocks";

describe("fetchQuote", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed quote data on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ Ticker: "AAPL", Price: "227.52" }),
      }),
    );

    const result = await fetchQuote("AAPL");

    expect(result).toEqual({ Ticker: "AAPL", Price: "227.52" });
    expect(fetch).toHaveBeenCalledWith("/api/stocks/AAPL");
  });

  it("throws with the backend's error detail on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "No Finviz data found for ticker 'ZZZZ'" }),
      }),
    );

    await expect(fetchQuote("ZZZZ")).rejects.toThrow(
      "No Finviz data found for ticker 'ZZZZ'",
    );
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — `src/api/stocks.ts` doesn't exist.

- [ ] **Step 4: Implement the API client**

`frontend/src/api/stocks.ts`:
```typescript
export interface Quote {
  Ticker: string;
  Company?: string;
  Price?: string;
  [key: string]: string | undefined;
}

export async function fetchQuote(ticker: string): Promise<Quote> {
  const response = await fetch(`/api/stocks/${ticker}`);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.detail ?? "Failed to fetch quote");
  }

  return body as Quote;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS (2 tests)

- [ ] **Step 6: Implement StockSearch component**

`frontend/src/components/StockSearch.tsx`:
```typescript
import { FormEvent, useState } from "react";

interface StockSearchProps {
  onSearch: (ticker: string) => void;
}

export function StockSearch({ onSearch }: StockSearchProps) {
  const [ticker, setTicker] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = ticker.trim();
    if (trimmed.length > 0) {
      onSearch(trimmed.toUpperCase());
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={ticker}
        onChange={(event) => setTicker(event.target.value)}
        placeholder="Enter ticker (e.g. AAPL)"
        aria-label="Stock ticker"
      />
      <button type="submit">Look up</button>
    </form>
  );
}
```

- [ ] **Step 7: Implement QuoteTable component**

`frontend/src/components/QuoteTable.tsx`:
```typescript
import { Quote } from "../api/stocks";

interface QuoteTableProps {
  quote: Quote | null;
  error: string | null;
  isLoading: boolean;
}

export function QuoteTable({ quote, error, isLoading }: QuoteTableProps) {
  if (isLoading) {
    return <p>Loading...</p>;
  }

  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (!quote) {
    return null;
  }

  const rows = Object.entries(quote).filter(([, value]) => value !== undefined);

  return (
    <table>
      <tbody>
        {rows.map(([key, value]) => (
          <tr key={key}>
            <th>{key}</th>
            <td>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 8: Wire components together in App**

Modify `frontend/src/App.tsx`:
```typescript
import { useState } from "react";
import { fetchQuote, Quote } from "./api/stocks";
import { QuoteTable } from "./components/QuoteTable";
import { StockSearch } from "./components/StockSearch";

export default function App() {
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSearch(ticker: string) {
    setIsLoading(true);
    setError(null);
    setQuote(null);

    try {
      const result = await fetchQuote(ticker);
      setQuote(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h1>Finviz Dashboard</h1>
      <StockSearch onSearch={handleSearch} />
      <QuoteTable quote={quote} error={error} isLoading={isLoading} />
    </div>
  );
}
```

- [ ] **Step 9: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: PASS (all tests)

- [ ] **Step 10: Manual end-to-end check**

Run: `docker compose up --build`, then open `http://localhost:5173`, enter `AAPL` in
the search box, and confirm a quote table renders. Enter an invalid ticker like
`ZZZZINVALID` and confirm the "ticker not found" error message renders instead of a
blank page.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/ frontend/vitest.config.ts frontend/package.json
git commit -m "feat: add stock search UI with quote table and error display"
```

---

## Self-Review Notes

- **Spec coverage:** architecture (Task 1 compose setup, Task 2 client isolation) ✓;
  Finviz CSV/auth quirks (Task 2) ✓; SQLite cache with TTL (Task 3) ✓; API surface,
  both endpoints (Task 4) ✓; frontend search + table, no charts (Task 6) ✓; error
  handling for invalid ticker / auth failure (Tasks 2 & 4) ✓; testing — mocked unit
  tests plus manual sanity script (Tasks 2-4, Task 5) ✓; secrets via `.env`,
  `.env.example` (Task 1) ✓; Docker Compose dev environment (Task 1) ✓.
- **Out of scope confirmed absent:** no screener, options, auth, charts, watchlist
  code anywhere in this plan.
- **Type consistency checked:** `get_quote(ticker: str) -> dict` (Task 2) is what
  Task 3's cache stores/returns and Task 4's route calls; `QuoteResponse` (Task 4)
  matches the `Quote` TS interface shape (Task 6) via the JSON boundary;
  `get_cached_quote`/`set_cached_quote` signatures match between Task 3's
  implementation and Task 4's route usage.
