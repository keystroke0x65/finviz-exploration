# Record mode, step 2 — Curate

Turn the reflection into the *smallest* set of operations that makes memory correct and more useful. Adapted from ACE's Curator ("identify ONLY the new insights missing from the playbook; do not regenerate it") and DeltaMem's delta extractor ("extract only the minimal patch not covered by existing memory; skip only when you can quote the entry that already covers it").

## Decision procedure — for each insight and each changed fact

**Step A. Look before writing.**
```
python3 scripts/memory.py find <keywords from this insight>
```
Read the chains that come back. Most write mistakes (duplicates, contradictions, orphaned variations) come from skipping this.

**Step B. Choose exactly one action.**

1. **SKIP** — an existing entry already says this. You must be able to point at it: *which ID, and which words cover every part of the insight?* If any part isn't covered (a condition, a step, a failure mode), don't skip — go to 2.
2. **ADD_DELTA** — an existing root/delta is right in general, but under a specific condition something differs or extra steps are needed. Write only the difference, plus a `when` that is specific and different from sibling `when`s. Attach to the *deepest* node whose meaning still holds.
3. **SUPERSEDE** — an existing entry is now false (version changed, decision reversed, file moved, approach no longer works). Write the new fact; give the reason. History is kept in the archive.
4. **UPDATE** — same fact, but the entry is vague, incomplete, or has wrong labels/section. Keeps ID and counters. Don't use UPDATE to change meaning — that's SUPERSEDE.
5. **DELETE** — an entry is wrong and there's no replacement, or it describes something removed from the project.
6. **ADD_ROOT (lesson)** — a genuinely new, general strategy. File under `experience/<topic>.md` › Lessons.
7. **ADD_ROOT kind=trap** — a failure worth never repeating. Content: `FAILED: <what was tried> → <what happened>. INSTEAD: <what works>` or `UNEXPLORED: <approaches not yet tried>`.
8. **ADD_ROOT (context)** — a new project fact: route it with the "what goes where" table in `spec.md`.

Tiebreakers: prefer DELTA over ROOT when a related root exists (it keeps related knowledge in one chain); prefer SUPERSEDE over UPDATE when in doubt about whether meaning changed; prefer SKIP over a weak insight.

**Step C. Progress and feedback.**
- Work items: ADD_ROOT to `progress.md` (Now/Next/Known issues); move with `UPDATE` + `section` ("Now" → "Done"); DELETE fixed Known issues with reason "fixed in …".
- Put every tag from the reflection into `feedback`.

## Writing good entries

- **Self-contained.** A future session reads the entry cold, maybe months later. Name the thing: "Drizzle migrations for preview deploys must target the Neon branch in DATABASE_URL_PREVIEW", not "use the other URL".
- **Specific over generic.** ACE shows that concise-but-generic memories (*brevity bias*) lose the details that made them useful. Keep the concrete command, file, flag, or error message.
- **One idea per entry.** Two ideas → two operations.
- **Labels** — 1–4 lowercase keywords someone would search for: the area, the library, the kind of work.
- **source** — the file or command that proves it, or `user`.
- **No secrets, no transient details** (branch names for one PR, today's error IDs, temporary workarounds already removed).

## Batch example

```json
{
  "note": "fixed preview deploy migrations; upgraded drizzle-kit",
  "feedback": [
    {"id": "deploy-0001", "tag": "helpful"},
    {"id": "stack-0004", "tag": "harmful"}
  ],
  "operations": [
    {"op": "SUPERSEDE", "id": "stack-0004", "reason": "upgraded in package.json",
     "content": "drizzle-kit 0.24 generates SQL migrations into drizzle/; apply with pnpm db:migrate", "source": "package.json"},
    {"op": "ADD_DELTA", "parent": "deploy-0001", "when": "Vercel preview deployments",
     "content": "run pnpm db:migrate with DATABASE_URL set to the preview Neon branch before the build step", "labels": ["deploy", "neon"]},
    {"op": "ADD_ROOT", "file": "experience/deploy.md", "section": "Traps", "kind": "trap", "labels": ["deploy", "drizzle"],
     "content": "FAILED: running drizzle-kit push inside next build → build hangs waiting for a TTY prompt. INSTEAD: run migrations as a separate CI step before build"},
    {"op": "UPDATE", "id": "prog-0003", "section": "Done", "reason": "pipeline shipped"}
  ]
}
```

## Apply

```
python3 scripts/memory.py apply /tmp/mb-batch.json --dry-run
python3 scripts/memory.py apply /tmp/mb-batch.json
```

If rejected, the message names the fix:
- *near-duplicate of X* → SKIP, UPDATE X, or ADD_DELTA under X.
- *requires 'when'* → you're writing a variation; state its condition.
- *possible secret* → replace the value with the env var name / location.
- *content length* → split into two entries or tighten.
- *entry not found* → re-run `find`; the ID may have been superseded (check `history/archive.md`).

Use `force: true` only when two entries are textually similar but meaningfully different; say why in `reason`.

## Then
1. Rewrite `active-context.md` directly: current focus, open questions/blockers, recent changes (newest first), next steps. Keep it under 80 lines.
2. Tell the user briefly what was recorded, e.g. "Memory: superseded stack-0004 (drizzle-kit 0.24), added deploy-0001.2 (preview migrations) and trap deploy-0005."
3. If `apply` printed budget warnings, suggest maintain mode.
