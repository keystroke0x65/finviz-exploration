import type { Verdict, VerdictCall } from "../api/setups";
import { formatEasternDate } from "../format";

const LABELS: Record<VerdictCall, string> = {
  leans_long: "Leans long",
  leans_short: "Leans short",
  no_clear_edge: "No clear edge",
};

export function describeVerdictAge(verdict: Verdict): string {
  return `Scored ${new Date(verdict.computed_at).toLocaleString()}`;
}

// A verdict from an earlier trading day says little about how the stock trades now.
export function isVerdictStale(verdict: Verdict): boolean {
  return formatEasternDate(verdict.computed_at) !== formatEasternDate(new Date().toISOString());
}

export function VerdictBadge({ verdict }: { verdict: Verdict | null | undefined }) {
  if (!verdict) {
    return <span className="muted">—</span>;
  }
  return (
    <span
      className="badge verdict-badge"
      data-call={verdict.call}
      data-stale={isVerdictStale(verdict)}
      title={[describeVerdictAge(verdict), ...verdict.reasons].join("\n")}
    >
      {LABELS[verdict.call]}
    </span>
  );
}
