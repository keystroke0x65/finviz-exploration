# 0003: Draw candle charts with TradingView lightweight-charts v4
Date: 2026-10-21
Status: accepted

## Context
The Stock view needs candlestick charts on 1m, 5m and daily bars with horizontal lines for
entry, stop, target, daily support/resistance and session levels, plus VWAP and a pattern
outline. The user checks setups visually, the same way they read Finviz charts.

## Decision
Use `lightweight-charts` 4.2 (Apache-2.0, ~45 KB gzipped), pinned to the v4 API
(`addCandlestickSeries`, `addLineSeries`, `createPriceLine`). Times are passed as Eastern
wall-clock values (`frontend/src/chartTime.ts`) so the axis reads in market time.

## Alternatives considered
- **Recharts / Chart.js**: general charting; candles and price lines need plugins or custom
  drawing, and large bar counts render slowly.
- **lightweight-charts v5**: newer API (`addSeries(CandlestickSeries)`); no gain for this
  use, and v4 is stable and well documented.
- **Embedding Finviz charts**: not available through the export API.

## Consequences
- Fast canvas rendering of thousands of bars, built-in price-line labels.
- Canvas can't read CSS variables, so chart colours are duplicated in `CandleChart.tsx`.
- jsdom has no canvas: component tests mock the library.
- The library's own "TV" attribution logo is shown on the chart.
