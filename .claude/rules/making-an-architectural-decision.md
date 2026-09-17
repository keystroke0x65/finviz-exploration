# Making an architectural decision

## Rule
Significant choices get a short written record so they aren't relitigated later.

## Counts as significant
Choosing a library or framework, a data model or schema design, an auth approach, a caching strategy, a folder structure convention, or deliberately deviating from an existing pattern.

## Guidelines
- Before deciding, check existing decision records (e.g. `docs/decisions/`) for prior choices.
- If a decision contradicts a past one, flag it rather than silently overriding it.
- For big choices, propose options to the human before implementing.

## Record format
`docs/decisions/NNNN-short-title.md`:

```markdown
# NNNN: Short title
Date: YYYY-MM-DD
Status: accepted

## Context
What problem or constraint prompted this.

## Decision
What we chose.

## Alternatives considered
What else was on the table and why it lost.

## Consequences
What this makes easier, and what it makes harder.
```
