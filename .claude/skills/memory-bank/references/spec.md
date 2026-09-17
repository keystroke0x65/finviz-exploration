# Memory Bank Specification

The contract every file, script, and operation follows. If this file and the scripts disagree, the scripts (`scripts/lib/budget.py`, `scripts/lib/store.py`) are authoritative — update this file.

## Contents
1. Folder layout
2. Entry line format
3. Entry kinds: root, delta, trap
4. IDs
5. Operations
6. Budgets
7. What goes where

---

## 1. Folder layout

```
<project>/memory-bank/
├── index.md              GENERATED map of the bank. Read at session start. Never edit.
├── active-context.md     Freeform current state. The only file edited directly. ≤80 lines.
├── progress.md           Entry file: Now / Next / Done / Known issues          prefix: prog
├── context/              Declarative project knowledge
│   ├── project-brief.md  Purpose, users, scope, non-goals, constraints          prefix: brief
│   ├── architecture.md   Components, data flow, integrations, invariants        prefix: arch
│   ├── tech-stack.md     Frameworks, services, dev environment, commands        prefix: stack
│   ├── conventions.md    Code style, patterns, testing, workflow                prefix: conv
│   └── decisions.md      ADR-style decisions with rationale                     prefix: dec
├── experience/           Procedural lessons, one file per topic
│   └── <topic>.md        Lessons + Traps; created on first ADD_ROOT             prefix: <topic>
├── history/archive.md    Superseded, deleted, and promoted entries with reasons. Not loaded by default.
├── ops-log.jsonl         Every applied batch (audit trail, replayable into a future backend).
├── .state.json           ID counters and hook state. Never edit.
└── .snapshots/           Pre-batch copies for rollback (last 20). Gitignored.
```

Topic names: lowercase, `a-z0-9-`, 2–31 chars, not one of the reserved prefixes (`brief arch stack conv dec prog`). Prefer a small number of broad topics (`auth`, `deploy`, `testing`, `data-model`, `ui`, `tooling`) over many narrow ones.

Commit `memory-bank/` to git if the memory should be shared or versioned; `.snapshots/` is excluded automatically.

## 2. Entry line format

```
- [auth-0001] root h=4 x=0 d=2026-09-16 labels=auth,clerk src="middleware.ts" :: Content sentence.
  - [auth-0001.1] delta h=1 x=0 d=2026-09-16 when="API route handlers" :: Only what differs under this condition.
- [auth-0002] trap h=0 x=0 d=2026-09-16 labels=auth :: FAILED: what was tried and what happened. INSTEAD: what works.
```

| Field | Meaning |
|---|---|
| `[id]` | Stable identifier. Never reused. |
| kind | `root`, `delta`, or `trap` |
| `h` / `x` | helpful / harmful counters, changed only via `feedback` |
| `d` | date created (UTC) |
| `labels` | up to 6 lowercase keywords that improve `find` |
| `when` | deltas only: the condition under which the delta applies |
| `src` | where the fact was verified (file path, command, `user`) |
| `supersedes` / `from` | lineage after SUPERSEDE / PROMOTE |
| content | after ` :: `, one line, 12–400 chars, self-contained |

Lines starting with `## ` are sections. HTML comments and other text are preserved and ignored.

## 3. Entry kinds

**root** — a general fact or lesson that stands on its own.

**delta** — a residual variation of its parent (DeltaMem). It stores *only* what differs, plus `when`. To use it, read the chain root → … → delta. Deltas nest up to depth 3. A delta must never repeat its parent.

**trap** — a failure record (DeltaMem failure nodes, ReasoningBank failure-derived insights). Format content as `FAILED: … INSTEAD: …`. If what to do instead is unknown, write `UNEXPLORED: <plausible approaches not yet tried>`.

## 4. IDs

- Roots and traps: `<prefix>-NNNN`, e.g. `dec-0007`. Counters only increase, even after deletes.
- Deltas: `<parent-id>.N`, e.g. `auth-0001.2`, `auth-0001.2.1`.
- Within a batch, give an op `"ref": "name"` and refer to its new ID as `"@name"` in later ops.

## 5. Operations

A batch is a JSON object (schema: `scripts/schemas/ops.schema.json`):

```json
{
  "note": "fixed preview deploy failures",
  "feedback": [{"id": "deploy-0001", "tag": "helpful"}, {"id": "deploy-0003", "tag": "harmful"}],
  "operations": [ ... ]
}
```

| op | Required | Effect |
|---|---|---|
| `ADD_ROOT` | file, section, content | New root (or `kind: "trap"`). Rejected if ≥0.82 similar to an entry in the file unless `force`. Creates topic file/section if missing. |
| `ADD_DELTA` | parent, when, content | New delta under parent, placed after the parent's subtree. Rejected if it repeats any node in the chain. |
| `UPDATE` | id, reason, and ≥1 of content/when/labels/section | Same fact, refined. Keeps counters and ID. `section` moves a root with its deltas. |
| `SUPERSEDE` | id, content, reason | The fact changed. Old entry (and its deltas) go to the archive; new entry gets a new ID with `supersedes=`. Counters reset. |
| `DELETE` | id, reason | Archives the entry and its deltas. |
| `PROMOTE` | id (leaf delta), content | Consolidation: writes a self-contained root compiled from the chain, archives the delta. Keeps helpful count. |

`feedback` tags: `helpful` → h+1, `harmful` → x+1, `neutral` → no change.

Batches are atomic: any error means nothing is written. Use `--dry-run` first. `rollback` restores the state before the most recent batch.

## 6. Budgets

| Scope | Limit |
|---|---|
| entry content | 12–400 chars, one line |
| `when` | ≤120 chars |
| delta depth | ≤3 |
| each `context/*.md` | 60 entries / 9,000 chars |
| each `experience/*.md` | 80 entries / 12,000 chars |
| `progress.md` | 50 entries / 7,000 chars; Done ≤15 |
| `active-context.md` | ≤80 lines |
| all entry files | warn above 60,000 chars (~15k tokens) |
| duplicate rejection | similarity ≥0.82 |
| promote candidate | delta with h ≥3, x = 0, no children |
| prune candidate | x ≥2 and x > h (also hidden from `find`) |
| stale candidate | experience/progress entry unused for 90 days |

Budgets are signals to consolidate, not reasons to drop valuable knowledge.

## 7. What goes where

| It is… | Goes to |
|---|---|
| What the project is for, who uses it, what's out of scope | `context/project-brief.md` |
| How components fit together; rules that must stay true | `context/architecture.md` |
| Versions, services, env var names, commands that work | `context/tech-stack.md` |
| How code is written here | `context/conventions.md` |
| A choice between alternatives, with the reason | `context/decisions.md` |
| Status of work items and open bugs | `progress.md` |
| A reusable way to get something done | `experience/<topic>.md` › Lessons (root) |
| The same, but different under a specific condition | ADD_DELTA under that root |
| Something that failed and why | `experience/<topic>.md` › Traps (trap) |
| What you're doing right now, blockers, next steps | `active-context.md` |
