import { useEffect, useState } from "react";
import { DailyLoss, fetchDailyLoss } from "../api/journal";
import { formatDollars } from "../format";

interface DailyLossBannerProps {
  // Bump to re-check, e.g. after a trade is saved.
  refreshKey: number;
}

// Warns only; never blocks logging or trading.
export function DailyLossBanner({ refreshKey }: DailyLossBannerProps) {
  const [dailyLoss, setDailyLoss] = useState<DailyLoss | null>(null);

  useEffect(() => {
    let isCurrent = true;
    fetchDailyLoss()
      .then((loaded) => {
        if (isCurrent) setDailyLoss(loaded);
      })
      // Best effort: without the figure there is simply no banner.
      .catch(() => undefined);
    return () => {
      isCurrent = false;
    };
  }, [refreshKey]);

  if (!dailyLoss || dailyLoss.level === "ok" || dailyLoss.max_daily_loss == null) return null;
  const amounts = `(${formatDollars(dailyLoss.realised_pnl_today, 0)} of ${formatDollars(-dailyLoss.max_daily_loss, 0)})`;
  if (dailyLoss.level === "reached") {
    return (
      <p role="alert" className="alert daily-loss-banner">
        Max daily loss reached {amounts}
      </p>
    );
  }
  return (
    <p role="status" className="daily-loss-banner daily-loss-warning">
      Close to max daily loss {amounts}
    </p>
  );
}
