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

## The target experience (user's scenario, "a couple of months" out)

Monday morning, 5:00 AM: the user turns the computer and the software on.

- 5:00–9:30 AM: it looks at what is moving pre-market, finds exactly which pattern/setup is
  happening (if any), grades each stock's setup A–F, and gives entry, exit, stop and target.
  It finds and ranks opportunities. It may trade pre-market if the pattern and setup are
  right; if not trading itself, at the very least it tells the user the stock, pattern,
  setup and levels so the user can trade manually.
- During the session it keeps looking for the best setups. If nothing is good enough, so be
  it.
- At end of day it may research new patterns, looking back weeks or months. If a new pattern
  means nothing, it drops it, as long as it tried. It searches harder when it senses its
  currently working patterns are fading.

(Note: the example date, 18 Jan 2027, is MLK Day and US markets are closed; the system needs
the trading calendar, which the dashboard doesn't model today.)

## Decisions so far

- **Which stocks go into the journal:** the ones the user's current screens catch.
  *(Claude's suggestion, not yet confirmed)* also recent runners from the watchlist on days
  they aren't moving, since day-2, first-red-day and panic-dip plays happen then.
- **Start small:** first slice proposed by Claude, not yet approved: a *movers journal* —
  each day, store each mover's full 4 AM–8 PM minute bars, a handful of measurements, and a
  chart image; backfill past days from Massive; recompute when a measurement is added.
- **Auto-trading** *(Claude's suggestion)*: a late, opt-in step behind a broker API with hard
  risk limits, after alerts have earned trust.

## Open

- Research what the named traders publicly say they scan for and trade (in progress).
- What "a worthwhile pattern" means in numbers (sample size, out-of-sample checks, costs).
- What the A–F grade means.
- Order of the sub-projects (Claude's proposal: journal → measurements/outcomes → pattern
  search → charts/visual similarity → live strategies).
