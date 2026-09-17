# Maintain mode — consolidate, promote, prune

Memory that only grows stops being read. Maintenance keeps it compact and trustworthy without losing knowledge: everything removed goes to `history/archive.md` with a reason.

Run it when `apply` or `validate` prints budget warnings, roughly every 10 batches (`memory.py stats` shows the count), or when the user asks.

## 1. Get the report
```
python3 scripts/memory.py validate
python3 scripts/memory.py consolidate
```
Fix `validate` errors first (usually a hand edit: restore with `rollback`, or re-express the change as operations).

## 2. Decide each candidate

### PROMOTE — a delta that keeps proving itself (h ≥3, x = 0)
DeltaMem's consolidation: when a root → delta path is used successfully again and again, compile the chain into one self-contained root so future sessions get it in one read.

Compile the content like this:
- Read the whole chain printed in the report (root → … → delta).
- Write a single entry that states the combined guidance *for the delta's condition* with no reference to "the above" or "the base rule". Include the condition in the sentence: "For Vercel preview deployments, run migrations against the preview Neon branch before building, because …".
- Keep concrete details from every level of the chain.

```json
{"op": "PROMOTE", "id": "deploy-0001.1",
 "content": "For Vercel preview deployments, run pnpm db:migrate against the preview Neon branch (DATABASE_URL_PREVIEW) as a CI step before next build",
 "reason": "delta used successfully 4 times"}
```
The parent root stays. Only leaf deltas can be promoted; promote the deepest one first.

Don't promote if the delta only makes sense next to its root, or if its condition is so narrow a root would mislead.

### PRUNE — harmful ≥2 and harmful > helpful
These are already hidden from `find`. For each: is it wrong (DELETE), outdated (SUPERSEDE with the current fact), or right but badly worded so it got misapplied (UPDATE with a clearer condition)?

### Near-duplicates
Similar content in the same file. If they say the same thing, UPDATE the better one to include any detail unique to the other, then DELETE the other with reason "merged into X". If one is a special case of the other, the real fix is structural: SUPERSEDE the special case as an ADD_DELTA under the general one. If they differ meaningfully, leave them.

### Stale — never used in 90+ days (experience and progress only)
Check quickly whether it still holds (the file, command, or library still exists). DELETE if obsolete; otherwise leave it — unused isn't wrong.

### Done overflow
DELETE the oldest Done items in `progress.md` with reason "archived: completed". The archive keeps them.

### Over budget
After the above, if a file is still over budget:
- Experience topic too big → split it into narrower topics. Moving across files takes two operations: ADD_ROOT the content into `experience/<new-topic>.md` (with a `ref`), re-add its deltas under `@ref`, then DELETE the original with reason "moved to <new-topic>". Put all of it in one batch so it lands atomically. Counters reset on the moved entries; mention the old ID in the reason so the history is traceable.
- Context file too big → look for entries that restate the code (DELETE) and clusters of related facts that can become one root with deltas.
Never delete correct, useful knowledge just to meet a number — raise it with the user instead.

## 3. Apply as one batch
```
python3 scripts/memory.py apply /tmp/mb-maintain.json --dry-run
python3 scripts/memory.py apply /tmp/mb-maintain.json
python3 scripts/memory.py validate
```
Then tell the user what changed (counts and notable IDs). If something went wrong, `memory.py rollback` undoes the batch.
