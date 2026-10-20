export interface Quote {
  Ticker: string;
  Company?: string;
  Price?: string;
  [key: string]: string | null | undefined;
}

export async function fetchQuote(ticker: string): Promise<Quote> {
  const response = await fetch(`/api/stocks/${ticker}`);

  if (!response.ok) {
    // The backend normally sends { detail: string } (FastAPI's HTTPException
    // shape), but an unhandled 500 can return an HTML error page instead, so
    // the body isn't guaranteed to be valid JSON.
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }

  return (await response.json()) as Quote;
}
