import { Quote } from "../api/stocks";

interface QuoteTableProps {
  quote: Quote | null;
  error: string | null;
  isLoading: boolean;
}

export function QuoteTable({ quote, error, isLoading }: QuoteTableProps) {
  if (isLoading) {
    return <p>Loading...</p>;
  }

  if (error) {
    return <p role="alert">{error}</p>;
  }

  if (!quote) {
    return null;
  }

  const rows = Object.entries(quote).filter(([, value]) => value !== undefined);

  return (
    <table>
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
