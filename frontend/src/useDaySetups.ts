import { useEffect, useState } from "react";
import { DaySetups, fetchDaySetups } from "./api/journal";
import type { Direction } from "./api/setups";
import { easternParts } from "./easternTime";

// Fills are typed a character at a time; ask once the typing settles.
const SETTLE_MS = 400;

export interface TradeMoment {
  time: string; // ISO
  // null for a pass made while the price was unknown.
  price: number | null;
}

/**
 * The stock's setups for the picker, matched to the trade's first fill (its day, time,
 * direction and price), or the setups live right now when there's no fill yet.
 */
export interface DaySetupsState {
  // null while loading.
  setups: DaySetups | null;
  error: string | null;
}

export function useDaySetups(ticker: string, moment: TradeMoment | null, direction: Direction | null): DaySetupsState {
  const [state, setState] = useState<DaySetupsState>({ setups: null, error: null });
  const time = moment?.time ?? null;
  const price = moment?.price ?? null;

  useEffect(() => {
    let isCurrent = true;
    const timer = setTimeout(() => {
      const at = time ?? new Date().toISOString();
      fetchDaySetups(ticker, easternParts(at).date, at, direction ?? undefined, price ?? undefined)
        .then((loaded) => {
          if (isCurrent) setState({ setups: loaded, error: null });
        })
        // The picker says so; the entry can still be saved with "No setup".
        .catch((loadError: unknown) => {
          if (!isCurrent) return;
          const message = loadError instanceof Error ? loadError.message : String(loadError);
          setState({ setups: { matches: [], others: [] }, error: message });
        });
    }, SETTLE_MS);
    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [ticker, time, price, direction]);

  return state;
}
