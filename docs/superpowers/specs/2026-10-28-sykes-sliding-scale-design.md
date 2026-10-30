# Sykes sliding scale grade

Date: 2026-10-28
Status: approved by the user ("build it"), thresholds left to us

## Intent

Tim Sykes grades a trade before taking it with the "Sykes Sliding Scale": seven
factors, P.R.E.P.A.R.E., whose overall read sets position size. The user wants that
grade next to Score on the Setups tab, with a hover card showing each factor.

Sykes publishes the seven factors but not a scoring formula; he says the exact
grading is in his paid Trader Checklist videos. This is **our scoring of his seven
factors**, built from what he and reporters have published. Every threshold below
says whether it comes from a source or is our call.

Non-goals: changing Score, the verdict or the research-system plan
(`2026-10-27-trading-research-system-notes.md`).

## The seven factors

Each factor is graded good (2 points), ok (1) or poor (0). A factor without data is
shown as "no data" and counts 1 (neutral), so missing data neither helps nor sinks a
setup.

| # | Factor | Good | OK | Poor | Basis |
|---|---|---|---|---|---|
| 1 | Pattern and price | pattern quality >= 0.7 and price not extended past entry | one of the two | neither | Sykes: "what's the pattern and where is the price relative to it" [1]. 0.7 is our call (detector quality is 0-1). |
| 2 | Risk/reward | 3R or more | above 2R, under 3R | 2R or less | Sykes: 1:2 is "not enough", he looks for 1:3 or 1:4 [1]. |
| 3 | Ease of entry and exit | 1M+ shares (larger of today's and average volume) | 500K-1M | under 500K | Sykes weighs size against average and current volume [1]; he trades stocks averaging 1-5M shares a day [3]. The 500K band is our call. |
| 4 | Past performance (history of spiking) | 3+ spike days in the past year | 1-2 | none | Sykes looks for a history of spiking, gapping up or multiday runs [1]. A spike day = high at least 30% above the previous close, matching the 30%+ gainers he watches [3]. Today is excluded. Day counts are our call. |
| 5 | Time | 9:30-10:30 AM or 3-4 PM ET | 10:30 AM-3 PM | pre-market or after-hours | Sykes's power hours are the first and last hour [2]; he rarely trades pre-market, after-hours or midday [1]. Midday as "ok" is our call (regular-hours liquidity). Uses the trigger time, or the scan time while forming. |
| 6 | Reason (catalyst) | Finviz news in the last 24 hours | in the last 3 days | none | Sykes avoids "random spikers"; no clear catalyst means smaller size [1]. Windows are our call. We can't judge whether the news is good. |
| 7 | Environment of the market | 10+ US stocks up 30%+ | 5-9 | under 5 | Sykes sizes up in a hot market [1]; his daily watchlist is 10-15 stocks up 30-200% [3]. Before 9:30 Finviz's change is the previous session's, and the hover card says so. |

Grade from the total (0-14): A 12-14, B 10-11, C 8-9, D 6-7, F 0-5 (our call: even
steps of two points, so an A needs at most one factor short of good).

Short setups are graded the same way.

## Data and storage

- Graded during each scan with data the scan already has (bars, snapshot, plan),
  plus one Finviz screen per full scan (`geo_usa,ta_change_u20`, counted at 30%+
  locally because Finviz ignores an "up 30%" code). The count is stored in
  `app_meta`; one-stock scans reuse it if it is from today.
- Stored per setup in `setup_records.sliding_scale` (JSON: letter, points, factors
  with grade and detail), refreshed on every scan like Score. Records from before
  this change show "—".
- `GET /api/setups` and `/api/stocks/{ticker}/setups` return `sliding_scale` on each
  setup (null when not graded).

## Sources

1. Tim Sykes, "Sykes Sliding Scale": https://timothysykes.com/blog/sykes-sliding-scale/
2. Tim Sykes, "Power Hours: The Top Times to Trade": https://www.timothysykes.com/blog/top-times-to-trade/
3. Business Insider on Sykes's watchlist, volume and patterns:
   https://www.businessinsider.nl/stock-trader-high-returns-millionaire-students-shares-top-trading-patterns-2023-6/
   and https://businessinsider.nl/stock-trader-high-gains-shares-key-signals-make-a-trade-2023-7/
