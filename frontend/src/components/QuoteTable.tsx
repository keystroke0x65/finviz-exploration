import { Quote } from "../api/stocks";

interface QuoteTableProps {
  quote: Quote | null;
  error: string | null;
  isLoading: boolean;
}

export function QuoteTable({ quote, error, isLoading }: QuoteTableProps) {
  if (isLoading) {
    return <p className="muted">Looking up quote…</p>;
  }

  if (error) {
    return (
      <p role="alert" className="alert">
        {error}
      </p>
    );
  }

  if (!quote) {
    return null;
  }

  // FastAPI serializes missing Pydantic fields as JSON `null`, not
  // `undefined`, so both must be excluded to omit empty rows (e.g. P/E).
  const rows = Object.entries(quote).filter(([, value]) => value != null);

  return (
    <table className="quote-table">
      <tbody>
        {rows.map(([key, value]) => (
          <tr key={key}>
            <th>{key}</th>
            <td>{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
