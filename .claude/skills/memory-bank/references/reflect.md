# Record mode, step 1 — Reflect

Adapted from ACE's Reflector (diagnose from feedback, tag the bullets used), ReasoningBank's extractor (≤3 generalizable items from successes *and* failures), and DeltaMem's failure recorder (what failed, what was never tried).

Reflection is kept separate from curation on purpose: ACE found that deciding *what was learned* and deciding *how to store it* in one step lowers quality. Do this step in your head or a scratch file — it is not saved. Step 2 (`curate.md`) turns it into operations.

## When to skip
Skip record mode (say "no memory update") when the session was trivial: a question answered from existing knowledge, a one-line change with no surprises, or work fully covered by memory that behaved as expected. If you relied on memory IDs, still send feedback-only batch (see below).

## Gather evidence first
Lessons without evidence become confident fiction in future sessions. Use, in priority order:
1. **Execution feedback** — test results, build/type errors, runtime errors, command output, before/after behavior.
2. **User corrections** — anything the user said was wrong, preferred, or decided.
3. **Code you read** — facts verified in files (note the path).
4. **Your reasoning** — lowest weight. Mark insights that rest only on this as tentative, and prefer not to store them.

## Answer these

**1. Attempt.** What was the task, and what approach did you take? (1–3 lines)

**2. Outcome.** `success`, `partial`, or `failure` — and the evidence. A task that needed several tries is a *partial success*: the failed tries are data.

**3. Diagnosis.** For failures and retries: where exactly did it go wrong, and what was the root cause (a wrong assumption, missing project knowledge, a misleading memory entry, a tool quirk)? Name the root cause, not the symptom.

**4. Insights — at most 3.** Each must be:
- **Generalizable** — useful on a *future, different* task in this project. "The flaky test was fixed" is not an insight; "tests touching the Neon branch DB fail in parallel because they share one branch; run them with --no-threads" is.
- **Actionable** — says what to do or avoid.
- **Scoped** — if it only holds under a condition, state the condition (it will become a delta's `when`).
- **Honest about failure** — for dead ends, capture what was tried, what happened, and either what works instead or what remains unexplored.

**5. Changed facts.** Anything in project context that is now different: a dependency version, a new service, a moved file, a new convention, a decision made or reversed, a work item started/finished, a newly found bug.

**6. Memory feedback.** For every memory ID you relied on this session:
- `helpful` — it was correct and saved time or prevented a mistake.
- `harmful` — it was wrong, outdated, or led you astray. (Also plan a SUPERSEDE/UPDATE/DELETE for it.)
- `neutral` — you read it but it didn't matter.

Don't tag entries you didn't use. Don't tag helpful just to be generous — inflated counters get wrong entries promoted.

## Output shape (scratch)
```
attempt: …
outcome: partial — first two migration attempts failed with "relation does not exist"; passed after …
root_cause: preview deploys use a Neon branch DB, but migrations ran against main
insights:
  1. [scoped: preview deployments] run migrations against the preview branch DB …
  2. [failure] FAILED: running drizzle-kit push in the build step … INSTEAD: …
changed_facts:
  - drizzle-kit upgraded 0.20 → 0.24 (package.json)
  - progress: "preview deploy pipeline" moved Now → Done
feedback: deploy-0001 helpful; stack-0004 harmful (says drizzle-kit 0.20)
```

Then continue to `references/curate.md`.
