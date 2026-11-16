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
export function useDaySetups(ticker: string, moment: TradeMoment | null, direction: Direction | null): DaySetups | null {
  const [setups, setSetups] = useState<DaySetups | null>(null);
  const time = moment?.time ?? null;
  const price = moment?.price ?? null;

  useEffect(() => {
    let isCurrent = true;
    const timer = setTimeout(() => {
      const at = time ?? new Date().toISOString();
      fetchDaySetups(ticker, easternParts(at).date, at, direction ?? undefined, price ?? undefined)
        .then((loaded) => {
          if (isCurrent) setSetups(loaded);
        })
        // Best effort: the picker then offers only "No setup", and the entry still saves.
        .catch(() => {
          if (isCurrent) setSetups({ matches: [], others: [] });
        });
    }, SETTLE_MS);
    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [ticker, time, price, direction]);

  return setups;
}
