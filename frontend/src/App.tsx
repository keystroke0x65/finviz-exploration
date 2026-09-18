import { useState } from "react";
import { fetchQuote, Quote } from "./api/stocks";
import { QuoteTable } from "./components/QuoteTable";
import { StockSearch } from "./components/StockSearch";

export default function App() {
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSearch(ticker: string) {
    setIsLoading(true);
    setError(null);
    setQuote(null);

    try {
      const result = await fetchQuote(ticker);
      setQuote(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <h1>Finviz Dashboard</h1>
      <StockSearch onSearch={handleSearch} />
      <QuoteTable quote={quote} error={error} isLoading={isLoading} />
    </div>
  );
}
