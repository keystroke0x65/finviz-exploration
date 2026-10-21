# Experience — finviz

<!-- Entry file (procedural lessons). Created automatically on first ADD_ROOT to experience/finviz.md.
     roots = general lessons, deltas = condition-specific variations (when=), traps = failure records. -->

## Lessons
<!-- empty: reusable strategies that worked, with the reason they work -->
- [finviz-0002] root h=0 x=0 d=2026-10-21 labels=finviz,bars,intraday src="probe 2026-10-20" :: Finviz Elite bars: quote_export.ashx?t=X&p=d gives ~10y daily; p=i1 ~2 weeks of 1m and p=i5 ~3 weeks of 5m, 04:00-20:00 ET incl. extended hours. Intraday timestamps look like '10/20/2026 19:59 PM' (24h clock + redundant AM/PM). Massive (Polygon) is the fallback for deeper intraday history.
- [finviz-0003] root h=0 x=0 d=2026-10-21 labels=finviz,columns,export src="probe 2026-10-20" :: Finviz wide export v=152&c=<ids> returns columns in ascending id order (map by header name), accepts many comma-separated tickers in t=, Market Cap/Shares Float in millions, Average Volume in thousands. Useful ids: float 25, rel vol 64, change 66, AH change 72, news title 137.

## Traps
<!-- empty: approaches that failed: what was tried, what happened, what to do instead -->
- [finviz-0001] trap h=0 x=0 d=2026-10-21 labels=finviz,screener,filters src="probe of elite.finviz.com/export 2026-10-20" :: FAILED: assuming Finviz rejects bad filter codes -> unknown f=/s= codes are silently ignored and the export returns the whole market (~10,400 rows). INSTEAD: treat >5,000 rows as 'filters may have been ignored' and verify every code via the sanity script.
