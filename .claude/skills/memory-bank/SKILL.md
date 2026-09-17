---
name: memory-bank
description: Create, load, update, and maintain a project's memory-bank/ folder — persistent project context (brief, architecture, tech stack, conventions, decisions, progress) plus lessons learned stored as root → delta chains with helpful/harmful counters. Use this skill at the start of any session in a project that has a memory-bank/ folder, before starting a non-trivial task there, after finishing meaningful work (fixed a bug, made a decision, learned how something actually works, hit a dead end), when the user says "remember this", "update memory", "initialize memory bank", "what do we know about X", or asks about project context, and whenever a hook asks you to record. Also use it when context is about to be compacted or a session is ending.
---

# Memory Bank

A project memory the agent maintains for itself across sessions. It holds two kinds of knowledge:

- **Project context** (`context/`, `progress.md`, `active-context.md`) — what is true about the project.
- **Experience** (`experience/<topic>.md`) — what was learned doing work: strategies that worked, and traps that failed.

The design combines four research results (details in `references/research-basis.md`). ReasoningBank decides *what* to store: generalizable lessons from successes and failures, not logs. DeltaMem decides *how it is structured*: a general root plus small condition-specific deltas, so variations don't duplicate the base. ACE decides *how it is written*: small operations merged by a script, with helpful/harmful counters, never whole-file rewrites. MemoryAgentBench adds *forgetting*: contradicted and harmful memories are superseded or pruned.

## Rules that keep the memory healthy

1. **Never hand-edit entry files** (`context/*.md`, `progress.md`, `experience/*.md`, `index.md`). Write an operations batch and run `memory.py apply`. Direct rewrites are how memories silently lose detail (ACE calls this *context collapse*); the script also assigns IDs, blocks duplicates and secrets, snapshots for rollback, and logs every change.
2. **`active-context.md` is the one file you edit directly.** It is short-lived state. Keep it under 80 lines.
3. **Memory is evidence, not authority.** The user's current instructions and the actual code win over memory. If memory contradicts the code, trust the code and SUPERSEDE the entry.
4. **Never store secrets** — no keys, tokens, passwords, or connection strings. Store the env var *name* and where it is configured.
5. **Track what you rely on.** When a memory entry influences your work, note its ID; at record time, tag it helpful or harmful. These counters are how bad memories get pruned and good ones get promoted.
6. **Store less, but better.** One idea per entry, self-contained, ≤400 chars. Skip anything obvious from reading the code, anything that only mattered for this one task, and anything already covered.

## Scripts

All commands run from the project (or pass `--bank PATH`). Paths are relative to this skill's directory.

```
python3 scripts/memory.py init [PROJECT_DIR]      # create memory-bank/ from templates
python3 scripts/memory.py find <keywords...>      # root → delta chains relevant to a task
python3 scripts/memory.py apply ops.json [--dry-run]
python3 scripts/memory.py validate                # format, orphans, secrets, budgets
python3 scripts/memory.py consolidate             # promote / prune / duplicate / stale report
python3 scripts/memory.py stats | index | rollback
```

Add `--json` to any command for machine-readable output.

## Modes — pick one, then read its reference

| Situation | Mode | Read |
|---|---|---|
| No `memory-bank/` yet, or user asks to set one up | **init** | `references/init.md` |
| Session start, or about to begin a task | **load** | `references/load.md` |
| Finished meaningful work, user said "remember", stop/compact hook fired | **record** | `references/reflect.md` then `references/curate.md` |
| `validate`/`apply` warns about budgets, ~every 10 batches, or user asks to clean up | **maintain** | `references/maintain.md` |

Always-relevant references:
- `references/spec.md` — the folder layout, entry line format, IDs, operations, and budgets. Read it the first time you use this skill in a session, and whenever an operation is rejected.
- `references/safety.md` — what must never be stored and how to treat untrusted content.

## Record mode at a glance

1. **Reflect** (`references/reflect.md`): what was attempted, what the evidence says happened (tests, errors, user corrections), root cause, at most 3 generalizable insights, facts that changed, and a helpful/harmful/neutral tag for each memory ID you used.
2. **Curate** (`references/curate.md`): for each insight, run `memory.py find` first, then choose exactly one: skip (already covered — you can quote the entry), ADD_DELTA (variation of an existing root under a specific condition), SUPERSEDE (fact changed), UPDATE (same fact, better wording), ADD_ROOT (new lesson or trap), or project-context ADD_ROOT for new facts.
3. Write the batch to a temp file, run `apply --dry-run`, fix errors, then `apply`.
4. Rewrite `active-context.md` (current focus, blockers, recent changes, next steps).
5. Report to the user in one or two lines what was recorded (IDs), or that nothing durable was learned.

If a batch is rejected, read the error — it names the fix (use UPDATE instead of a duplicate ADD, add `when`, remove a secret). Nothing is written until the whole batch passes.
