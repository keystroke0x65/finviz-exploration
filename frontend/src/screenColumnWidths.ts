import { useEffect, useState } from "react";
import { ColumnWidths, fetchScreenColumnWidths, saveScreenColumnWidths } from "./api/settings";

// Same bounds as the backend: thin enough to tuck a column away, still wide enough to
// grab its edge again; never wider than a screen.
export const MIN_COLUMN_WIDTH = 40;
export const MAX_COLUMN_WIDTH = 2000;

export function clampColumnWidth(width: number): number {
  return Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, Math.round(width)));
}

export interface ScreenColumnWidths {
  // null while the table sizes its own columns (nothing saved).
  widths: ColumnWidths | null;
  error: string | null;
  // While dragging: shown straight away, saved once the drag ends.
  showWidths: (widths: ColumnWidths) => void;
  saveWidths: (widths: ColumnWidths) => void;
  resetWidths: () => void;
}

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

export function useScreenColumnWidths(): ScreenColumnWidths {
  const [widths, setWidths] = useState<ColumnWidths | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    fetchScreenColumnWidths()
      .then((saved) => {
        if (!isMounted || Object.keys(saved).length === 0) return;
        // A resize started before the load finished wins over the older saved layout.
        setWidths((current) => current ?? saved);
      })
      .catch((loadError: unknown) => {
        if (isMounted) setError(`Couldn't load saved column widths: ${describeError(loadError)}`);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  function persist(next: ColumnWidths) {
    setError(null);
    saveScreenColumnWidths(next).catch((saveError: unknown) => {
      setError(`Couldn't save column widths: ${describeError(saveError)}`);
    });
  }

  return {
    widths,
    error,
    showWidths: setWidths,
    saveWidths: (next) => {
      setWidths(next);
      persist(next);
    },
    resetWidths: () => {
      setWidths(null);
      persist({});
    },
  };
}
