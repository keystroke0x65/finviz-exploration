# Experience — finviz

<!-- Entry file (procedural lessons). Created automatically on first ADD_ROOT to experience/finviz.md.
     roots = general lessons, deltas = condition-specific variations (when=), traps = failure records. -->

## Lessons
<!-- empty: reusable strategies that worked, with the reason they work -->
- [finviz-0002] root h=0 x=0 d=2026-10-21 labels=finviz,bars,intraday src="probe 2026-10-20" :: Finviz Elite bars: quote_export.ashx?t=X&p=d gives ~10y daily; p=i1 ~2 weeks of 1m and p=i5 ~3 weeks of 5m, 04:00-20:00 ET incl. extended hours. Intraday timestamps look like '10/20/2026 19:59 PM' (24h clock + redundant AM/PM). Massive (Polygon) is the fallback for deeper intraday history.
- [finviz-0003] root h=1 x=0 d=2026-10-21 labels=finviz,columns,export src="probe 2026-10-20" :: Finviz wide export v=152&c=<ids> returns columns in ascending id order (map by header name), accepts many comma-separated tickers in t=, Market Cap/Shares Float in millions, Average Volume in thousands. Useful ids: float 25, rel vol 64, change 66, AH change 72, news title 137.
- [finviz-0005] root h=0 x=0 d=2026-10-21 labels=finviz,errors,csv src="backend/app/finviz_client.py" :: Finviz export can answer HTTP 200 with an HTML page or empty body; requests exception messages embed the URL incl. auth token. finviz_client therefore checks for a Ticker column, wraps parse errors as FinvizUnavailableError, and raises its errors 'from None' so the token never reaches logs.

## Traps
<!-- empty: approaches that failed: what was tried, what happened, what to do instead -->
- [finviz-0004] trap h=0 x=0 d=2026-10-21 labels=finviz,screener,filters src="scripts/finviz_sanity_check.py --screens run 2026-10-20" supersedes=finviz-0001 :: FAILED: assuming a bad Finviz filter code returns the whole market, so big results = typo -> Finviz drops each unknown f=/s= code individually and applies the rest (no error); valid broad screens exceed 5,000 rows (US only 10,435; market 11,758). INSTEAD: test each code alone vs the no-filter count (app: find_unrecognised_codes at screen save).
