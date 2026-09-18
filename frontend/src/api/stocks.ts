export interface Quote {
  Ticker: string;
  Company?: string;
  Price?: string;
  [key: string]: string | undefined;
}

export async function fetchQuote(ticker: string): Promise<Quote> {
  const response = await fetch(`/api/stocks/${ticker}`);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.detail ?? "Failed to fetch quote");
  }

  return body as Quote;
}
