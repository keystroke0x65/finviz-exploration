# Init mode — create a memory bank for a project

Goal: a small, accurate starting context. Every entry must be verifiable in the repo or stated by the user. A thin, correct bank beats a thick, guessed one — wrong memory is worse than no memory because future sessions will trust it.

## Steps

### 1. Create the folder
```
python3 scripts/memory.py init <project-dir>
```
Existing files are never overwritten. If a bank already exists, switch to load mode instead.

### 2. Survey the project (read, don't guess)
Read in this order and stop when you have enough; don't read the whole codebase.

1. `README*`, `CONTRIBUTING*`, `docs/` index, any existing `CLAUDE.md` / `AGENTS.md` / `.cursorrules`
2. Manifests: `package.json`, `pyproject.toml`, `requirements*.txt`, `Cargo.toml`, `go.mod`, lockfile for exact versions
3. Config: framework config (`next.config.*`, `vite.config.*`), `tsconfig.json`, `.env.example` (names only), `docker-compose*`, CI workflows, `vercel.json` / infra files
4. Structure: top two directory levels; entry points (`app/`, `src/main.*`, `pages/`, `api/`)
5. Recent history: `git log --oneline -30` for current direction and conventions in commit messages
6. Tests: where they live and the command that runs them

Note the source file for each fact — it goes in `source`.

### 3. Draft the initial batch
Write roots only (no deltas or traps yet — those come from experience). Aim for roughly:

| File | Target |
|---|---|
| `context/project-brief.md` | 3–8 entries |
| `context/tech-stack.md` | 5–15 entries (include verified commands) |
| `context/architecture.md` | 3–10 entries |
| `context/conventions.md` | 0–8 entries — only conventions actually visible in code/config |
| `context/decisions.md` | 0–5 entries — only when the reason is documented or stated |
| `progress.md` | Now / Next / Known issues from TODOs, open issues, or user input |

Rules:
- One fact per entry, self-contained: "Auth is Clerk; protected routes are matched in middleware.ts via createRouteMatcher", not "Uses Clerk".
- Put version numbers in tech-stack entries — they are what goes stale, so they need to be findable.
- Env vars: names and purpose only. Never values.
- If the purpose or scope isn't documented, **ask the user** rather than inferring it. Record their answer with `"source": "user"`.
- Don't write experience entries during init unless the user shares lessons; experience comes from doing work.

Example:
```json
{
  "note": "init from repo survey",
  "operations": [
    {"op": "ADD_ROOT", "file": "context/project-brief.md", "section": "Purpose", "source": "README.md",
     "content": "Logit lets users publish AI chat conversations as shareable, formatted pages", "labels": ["product"]},
    {"op": "ADD_ROOT", "file": "context/tech-stack.md", "section": "Runtime and frameworks", "source": "package.json",
     "content": "Next.js 14.2 App Router, React 18, TypeScript 5, Tailwind 3", "labels": ["nextjs", "react", "typescript"]},
    {"op": "ADD_ROOT", "file": "context/tech-stack.md", "section": "Commands", "source": "package.json",
     "content": "pnpm dev runs the app on :3000; pnpm test runs vitest; pnpm lint runs eslint", "labels": ["commands", "testing"]},
    {"op": "ADD_ROOT", "file": "context/tech-stack.md", "section": "Dev environment", "source": ".env.example",
     "content": "Requires CLERK_SECRET_KEY, NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and DATABASE_URL in .env.local", "labels": ["env", "clerk", "database"]}
  ]
}
```

### 4. Apply and verify
```
python3 scripts/memory.py apply /tmp/mb-init.json --dry-run
python3 scripts/memory.py apply /tmp/mb-init.json
python3 scripts/memory.py validate
```

### 5. Write `active-context.md`
Fill Current focus / Open questions / Recent changes / Next steps from the user's stated goal and recent git history.

### 6. Offer automation
Tell the user the bank is ready and that `hooks/settings.example.json` can load it at session start and prompt recording at session end. Don't modify their agent settings without asking.
