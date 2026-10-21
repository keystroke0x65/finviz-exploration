# 0002: Store screens as raw Finviz codes, with a form for a known subset
Date: 2026-10-20
Status: accepted

## Context
Finviz has hundreds of screener filter codes (`geo_usa`, `sh_float_u10`, …). The user builds
screens on Finviz itself and changes them often. Decision dec-0002 (memory bank) keeps raw
codes out of the rest of the app where possible.

## Decision
A screen is stored as its Finviz codes (filters, signal, order). The editor offers a small
form for the filters the user uses daily (`app/screens/filter_form.py`), plus pasting a
Finviz screener URL; any other code round-trips untouched as an "extra" code. Because
Finviz silently ignores unknown codes, saving a screen checks each extra code and the
signal against Finviz and rejects ones it doesn't recognise. The form's own codes are
checked by `scripts/finviz_sanity_check.py --screens`.

## Alternatives considered
- **A full typed filter model** for every Finviz filter: large, would drift from Finviz,
  and the user would still have to translate screens they build on Finviz.
- **Only URL paste, no form**: simplest, but quick tweaks (price under $10 instead of $20)
  would mean a round trip to Finviz.

## Consequences
- Any Finviz screen can be pasted in, including filters the app knows nothing about.
- Saving a screen with pasted codes costs one Finviz request per code plus one.
- Codes appear in the API (`extra_filters`); only the screens module and `finviz_client`
  interpret them.
