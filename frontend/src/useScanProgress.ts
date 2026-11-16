import { useEffect, useRef, useState } from "react";
import { fetchScanProgress, RunningScan } from "./api/setups";

export const SCAN_PROGRESS_POLL_MS = 2000;

/**
 * The running watchlist scan, checked every 2 s; null when none is running.
 * Calls onFinished once each time a scan seen running has stopped.
 */
export function useScanProgress(onFinished: () => void): RunningScan | null {
  const [progress, setProgress] = useState<RunningScan | null>(null);
  const wasRunning = useRef(false);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  useEffect(() => {
    let isMounted = true;
    async function check() {
      try {
        const latest = await fetchScanProgress();
        if (!isMounted) return;
        const running = latest.running ? latest : null;
        setProgress(running);
        if (wasRunning.current && !running) onFinishedRef.current();
        wasRunning.current = running != null;
      } catch {
        // Best effort (e.g. the backend restarting): hide the bar until a check succeeds.
        if (isMounted) setProgress(null);
      }
    }
    check();
    const timer = setInterval(check, SCAN_PROGRESS_POLL_MS);
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  return progress;
}
