import type { Verdict, VerdictCall } from "../api/setups";

const LABELS: Record<VerdictCall, string> = {
  leans_long: "Leans long",
  leans_short: "Leans short",
  no_clear_edge: "No clear edge",
};

export function VerdictBadge({ verdict }: { verdict: Verdict | null | undefined }) {
  if (!verdict) {
    return <span className="muted">—</span>;
  }
  return (
    <span className="badge verdict-badge" data-call={verdict.call} title={verdict.reasons.join("\n")}>
      {LABELS[verdict.call]}
    </span>
  );
}
