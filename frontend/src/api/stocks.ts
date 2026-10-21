import { requestJson } from "./http";

export interface Quote {
  Ticker: string;
  Company?: string;
  Price?: string;
  [key: string]: string | null | undefined;
}

export function fetchQuote(ticker: string): Promise<Quote> {
  return requestJson<Quote>(`/api/stocks/${ticker}`);
}
