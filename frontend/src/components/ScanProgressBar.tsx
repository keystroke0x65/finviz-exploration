import type { RunningScan } from "../api/setups";

const START_TIME = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  hour: "numeric",
  minute: "2-digit",
});

function describeProgress(progress: RunningScan): string {
  const started = `started ${START_TIME.format(new Date(progress.started_at))}`;
  if (progress.phase === "preparing") return `Preparing… · ${started}`;
  if (progress.phase === "finishing") return `Finishing… · ${started}`;
  const current = progress.ticker ? ` · ${progress.ticker}` : "";
  return `${progress.done} of ${progress.total} stocks${current} · ${started}`;
}

export function ScanProgressBar({ progress }: { progress: RunningScan }) {
  const label = progress.kind === "manual" ? "Scanning watchlist" : "Automatic scan";
  const percent = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
  return (
    <div className="scan-progress">
      <span className="scan-progress-label">{label}</span>
      <div
        className="scan-progress-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={progress.total}
        aria-valuenow={progress.done}
      >
        <div className="scan-progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <span className="muted scan-progress-detail">{describeProgress(progress)}</span>
    </div>
  );
}
