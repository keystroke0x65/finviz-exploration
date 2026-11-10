# Experience — frontend

<!-- Entry file (procedural lessons). Created automatically on first ADD_ROOT to experience/frontend.md.
     roots = general lessons, deltas = condition-specific variations (when=), traps = failure records. -->

## Lessons
<!-- empty: reusable strategies that worked, with the reason they work -->

## Traps
<!-- empty: approaches that failed: what was tried, what happened, what to do instead -->
- [frontend-0001] trap h=0 x=0 d=2026-11-10 labels=lightweight-charts,chart,click src="browser check 2026-11-09, fix 98a26ed" :: FAILED: chart.subscribeClick/subscribeDblClick for journal fills -> lightweight-charts 4.2 drops a 2nd click inside its double-click window if >=5px from the 1st (no click, no dblclick), losing quick exit clicks; mocked-chart tests can't show it. INSTEAD: native onClick on the chart div + bar at the crosshair time, ignoring clicks that end a drag (CandleChart.tsx).
