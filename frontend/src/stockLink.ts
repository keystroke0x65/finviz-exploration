// The address of the Stock view for one ticker, e.g. /?stock=HOST, so a ticker can be
// opened in a new browser tab.
const STOCK_PARAM = "stock";
// Same rule as the backend's ticker check: letters, dots and dashes, up to 10 long.
const TICKER_PATTERN = /^[A-Za-z.-]{1,10}$/;

export function stockUrl(ticker: string): string {
  return `/?${new URLSearchParams({ [STOCK_PARAM]: ticker })}`;
}

export function readTickerFromSearch(search: string): string | null {
  const ticker = new URLSearchParams(search).get(STOCK_PARAM);
  if (!ticker || !TICKER_PATTERN.test(ticker)) return null;
  return ticker.toUpperCase();
}
