import { FormEvent, useState } from "react";

interface StockSearchProps {
  onSearch: (ticker: string) => void;
}

export function StockSearch({ onSearch }: StockSearchProps) {
  const [ticker, setTicker] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = ticker.trim();
    if (trimmed.length > 0) {
      onSearch(trimmed.toUpperCase());
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={ticker}
        onChange={(event) => setTicker(event.target.value)}
        placeholder="Enter ticker (e.g. AAPL)"
        aria-label="Stock ticker"
      />
      <button type="submit" className="button-primary">
        Look up
      </button>
    </form>
  );
}
