# Trading research system — working notes

Status: **brainstorm in progress, not an approved design.** Captures what the user has said
so far (2026-10-26/27) so it isn't lost between sessions. Items marked *(Claude's guess)* are
not yet confirmed by the user.

## Why

- The Finviz dashboard (phases 1–2) scans the user's kind of stocks and applies textbook
  chart patterns. The user has made money trading from it, and it showed the idea works.
- It also showed the limit: applying every pattern to every stock a screen catches is not
  how successful small-cap traders work, and the live track record agrees (most generic
  setups lose; time of day matters; the generic score and verdict don't separate winners).
- An earlier attempt at a full trading system failed because it was "not precise enough, too
  vague, and without clear boundaries". This time: start small, grow day by day.

## The idea, in the user's words

The user wants part of the system to discover and build its own trading strategies, the way
traders like Steven Dux, Tim Sykes, Tim Grattani and Jack Kellogg do:

- Watch the stocks that move (including repeat movers) and put them into the appropriate
  tables to track them.
- Look at the charts and find patterns visually.
- Use the kind of applied statistics used in finance on those tables to find patterns that
  are actually worthwhile.
- This means the system takes and uses meaningful chart screenshots, and creates, reads,
  updates and analyses tables (like Excel sheets).

Example of the kind of finding meant (made up, after a Steven Dux video): a stock spikes
pre-market, fades into the open; if it then does only 75% of its pre-market volume in the
first 30 minutes, it tanks.

The user's own process today: wake early, read the charts, write down planned trades, try to
make them; read news and occasionally SEC filings. No trade journal or statistics so far.

## Corrections the user made to Claude's playback

1. **Many tables, of different widths.** Not one big table. Some narrow, some wide, created
   as needed.
2. **No fixed "everything".** What is measured must be able to change: e.g. first-30-minute
   volume vs pre-market volume may stop working and first-45-minute volume plus pre-market
   price action may start working. Winning patterns change, especially once they work "too
   perfectly". Don't try to judge "too perfect"; instead start small, build tables day by
   day, test what works and what doesn't, form hypotheses from visual chart analysis, and
   check them with the tables and applied statistics.
   - *(Claude's reading)* So raw minute bars (including pre-market) for every mover-day are
     the source of truth, and measurements are computed from them and can be added or
     changed later and recomputed over all past days.
3. **Patterns start from one stock, not from a time window.** Research is not "look back
   weeks or months". A trader sees one stock do something interesting, notices a pattern,
   then looks for other stocks that show the same pattern. One example comes first, then
   the search for lookalikes.
4. **Patterns get retired and come back.** Over time traders know when a pattern has stopped
   working, so they retire it until it "catches steam" again. They also decide which patterns
   to apply to which stocks. The user suspects this comes from knowing which tables the
   stocks belong in, and testing patterns within those tables.
5. **Applied statistics is how quality is judged.** The traders likely use applied statistics
   to decide what is statistically significant: about a pattern, a stock, the information in
   a table, the setup grade, or anything else needed to judge a pattern's quality and whether
   it is improving.
   - *(Claude's reading of 3–5)* A pattern belongs to a table (a group of similar stocks),
     not to every stock. Each pattern has a lifecycle: candidate (from one example) →
     testing (lookalikes found, measured) → active → retired (still tracked) → active again
     if its numbers recover. Statistics decide each move between stages, and also what the
     A–F grade means.

## The target experience (user's scenario, "a couple of months" out)

Monday morning, 5:00 AM: the user turns the computer and the software on.

- 5:00–9:30 AM: it looks at what is moving pre-market, finds exactly which pattern/setup is
  happening (if any), grades each stock's setup A–F, and gives entry, exit, stop and target.
  It finds and ranks opportunities. It may trade pre-market if the pattern and setup are
  right; if not trading itself, at the very least it tells the user the stock, pattern,
  setup and levels so the user can trade manually.
- During the session it keeps looking for the best setups. If nothing is good enough, so be
  it.
- At end of day it may research new patterns (see corrections 3–5 below for what that
  means). If a new pattern means nothing, it drops it, as long as it tried.

(Note: the example date, 18 Jan 2027, is MLK Day and US markets are closed; the system needs
the trading calendar, which the dashboard doesn't model today.)

## Decisions so far

- **Which stocks go into the journal:** the ones the user's current screens catch.
  *(Claude's suggestion, not yet confirmed)* also recent runners from the watchlist on days
  they aren't moving, since day-2, first-red-day and panic-dip plays happen then.
- **Tables are created by the system, seeded from the named traders' tables** (user, 2026-10-27).
  It starts with tables reconstructed from what Dux, Sykes, Grittani and Kellogg track, and
  creates new ones (for example splitting a table by float bucket) when the statistics justify
  it. Their actual tables aren't published, so the seeds come from their setup criteria in the
  Research section. *(Claude's proposed seed list)*:
  - Day-1 big gap-up: up >100%, market cap under $100M, by float bucket 1–2M / 2–5M / 5–10M (Dux).
  - Multi-day runner, first red day: ≥3 green days, market cap under ~$200M (Dux, Grittani).
  - Overextended promoted runner: several green days, large % run (Grittani).
  - Morning panic: ran ≈50%+, then drops 30–35%+ at or near the open, no bad news (Sykes).
  - First green day: closes near highs after a down stretch (Sykes).
  - Bounce into old resistance: price returns to a prior high-volume area within ~1 year (Dux).
  - Pullback below VWAP on a liquid low-float runner (Kellogg).
  - *(Claude's suggestion)* A new table must hold up on days it wasn't created from before
    the system trusts it, and needs a minimum number of examples.
- **Long-biased tables too** (user, 2026-10-27). Dux and Grittani are mostly short-biased; the
  user trades long, so the system must create and seed long-biased tables as well.
  *(Claude's reading)* Each stock-day records what happened in both directions, so the same
  table can test long and short patterns (Dux's post-open push of ~30–35% on 1–2M floats is
  the long side of his gap-up short). Long-biased seeds: day-1 opening push / first
  pullback, morning panic dip buy (Sykes), first green day (Sykes), VWAP pullback and reclaim
  (Kellogg), multi-day runner breakout continuation.
- **The user approves before anything goes live** (user, 2026-10-27). Research (creating
  tables, finding candidates, testing, retiring) runs on its own. A new table or a pattern
  promoted to active is proposed with its evidence and waits for the user's approval before it
  appears in live alerts. Revisit after a couple of months of trust.
- **Worthwhile = makes money on average after costs** (user, 2026-10-27). No preference between
  high-win-rate and big-winner patterns; patterns are ranked by average profit per trade (in R)
  after slippage, and the win rate is always shown so the user knows how it will feel to trade.
  *(Claude's proposal, not yet confirmed)* The A–F grade follows from this: it is the expected
  profit per trade for this setup on this stock, from its table's and pattern's statistics,
  marked down when the evidence is thin (A = clearly positive, F = expected to lose).
- **Start small:** first slice proposed by Claude, not yet approved: a *movers journal* —
  each day, store each mover's full 4 AM–8 PM minute bars, a handful of measurements, and a
  chart image; backfill past days from Massive; recompute when a measurement is added.
- **Auto-trading** *(Claude's suggestion)*: a late, opt-in step behind a broker API with hard
  risk limits, after alerts have earned trust.

## Research: what the named traders say (2026-10-27)

Sources are mostly secondary (course pages, blog summaries, interviews from 2019–2023), so
every number below is a starting hypothesis to check against our own tables, not a rule.

**Steven Dux** (small-cap short framework, as summarised by Tradezella):
- Universe: initial market cap under $100M for gap-up shorts (up to ~$200M for bounce shorts
  and first red days); float under 50M, bucketed 1–2M / 2–5M / 5–10M; price above $3; avoid
  biotech and energy (his tracking showed a win-rate drop on biotech); avoid thin Chinese
  tickers with halt risk.
- Volume pace: full-day volume estimated from pre-market at roughly 1:5 to 1:10; pre-market
  volume above 50M makes a same-day gap-up short risky; float rotation above ~15x means
  smaller or no trade; gap-up shorts want ~30–35% of expected volume traded by late morning.
- Setups: gap-up short (stock up >100%, short after the opening push, 9:30–11:30, breakdown
  usually 10:00–11:00, after ~1 hour of consolidation); bounce short into a prior
  high-volume resistance area (uses ~1 year of history; "trapped volume" ≥ 2:1 against
  today's buying); first red day short (≥3 consecutive green days; skip if the red day
  already erased >50% of the run).
- Statistics cited: post-open push averages ~30–35% on 1–2M floats, ~20–25% on 5–10M floats;
  gap-up short average fade ~24–26% from the high of day with ~7% average risk (≈1:3.5–1:4).
  Setups occur a "known number of times per year" with known win rates and fades.
- Benzinga (2019): he ran aggregated data sets through scenarios and only tracked stocks with
  market caps up to $200M.

**Tim Sykes** (his own blog, older posts): morning panic dip buy: a 30–35%+ sell-off at or
near the open, on a stock that first ran a lot (≈50%+), not on bad news; buy when support
holds and buyers step in; cut fast. Supernova / multi-day runners almost always "fall off a
cliff"; first green day: buy a stock closing near its highs for the next-morning gap. A
7-step framework (one step is the "cliff dive" panic after a run).

**Tim Grittani:** shorts heavily promoted stocks that are overextended after several
consecutive green days; warns that a first red day doesn't necessarily mean the move is over.
No published checklist found. Others' first-red-day criteria: 2–3+ green days, run of
~80–100%+ (or 200–500%), market cap under $500M.

**Jack Kellogg:** trades OTCs too; low float for spikes but real size only in liquid names
with clean stops; starts small and adds to winners, moving the stop to break even; waits for
pullbacks below VWAP before longs. No published scanner criteria or reward:risk figures
found. (An earlier draft said he aims for ~10:1; that came from an unsourced search summary
and couldn't be verified, so it was removed. His Chat With Traders episode 249 is the best
primary source to check.)

**What this suggests for the system** *(Claude's reading)*:
- Every setup is tied to a *stage* of a run (day 1 gap-up, day 2, first red day after N green
  days, panic after a big run, bounce into old resistance). The stage needs its own columns
  (consecutive green days, % run from start, prior high-volume price areas).
- Their measurements are simple and specific: float/market-cap buckets, pre-market volume,
  volume pace vs expected, float rotation, time windows, % push after open, % fade from high.
- Their statistics are simple too: per setup and segment, how often it happens, win rate,
  average fade/push, average risk.
- Dux and Grittani are mostly short-side; for a long-only trader their setups still matter:
  a stock matching a strong short setup is a poor long.

Sources: [Tradezella: Steven Dux small-cap short strategy](https://www.tradezella.com/strategies/small-cap-short-strategy),
[Benzinga 2019 interview](https://www.benzinga.com/markets/penny-stocks/19/08/14300909/verified-millionaire-trader-steven-dux-shares-his-high-odds-strategy),
[Trading Reviewers: Steven Dux](https://www.tradingreviewers.com/steven-dux/),
[Sykes: morning panic dip buys](https://www.timothysykes.com/blog/dip-buy-morning-panics/),
[Sykes: which stocks are morning panic dip buys](https://www.timothysykes.com/blog/morning-panic-dip-buys/),
[Sykes: first green day](https://www.timothysykes.com/blog/first-green-day-otc/),
[Trading Reviewers: Grittani Trading Tickers](https://www.tradingreviewers.com/tim-grittani-trading-tickers-dvd-review/),
[Tradezella: first red day](https://www.tradezella.com/strategies/first-red-day-2),
[Bullish Bears: first red day](https://bullishbears.com/first-red-day-pattern/),
[SteadyTrade: Jack Kellogg](https://www.steadytrade.com/jack-kellogg/),
[Forex Club: Jack Kellogg](https://en.forexclub.pl/jack-kellogg-advice-from-a-trader-who-went-from-75k-usd-to-126m-usd-in-5-years/).

## Open

- Research what the named traders publicly say they scan for and trade (done above; primary
  material such as their courses and videos wasn't available).
- What "a worthwhile pattern" means in numbers (sample size, out-of-sample checks, costs).
- What the A–F grade means.
- Order of the sub-projects (Claude's proposal: journal → measurements/outcomes → pattern
  search → charts/visual similarity → live strategies).
