import { useId, useState } from "react";
import type { SlidingScale, SlidingScaleFactorGrade } from "../api/setups";

const MAX_POINTS = 14;
const GRADE_SYMBOLS: Record<SlidingScaleFactorGrade, string> = { good: "✓", ok: "~", poor: "✗", no_data: "?" };
// The card is about this tall; it opens upward when there isn't room below.
const CARD_HEIGHT_ESTIMATE = 260;
const CARD_GAP = 6;

interface CardPosition {
  right: number;
  top?: number;
  bottom?: number;
}

// The table scrolls inside its own box, which would clip an absolutely positioned
// card, so the card is fixed to the window next to the grade instead.
function positionNextTo(anchor: DOMRect): CardPosition {
  const right = window.innerWidth - anchor.right;
  if (anchor.bottom + CARD_GAP + CARD_HEIGHT_ESTIMATE <= window.innerHeight) {
    return { right, top: anchor.bottom + CARD_GAP };
  }
  return { right, bottom: window.innerHeight - anchor.top + CARD_GAP };
}

export function SlidingScaleBadge({ scale, ticker }: { scale: SlidingScale; ticker: string }) {
  const [position, setPosition] = useState<CardPosition | null>(null);
  const cardId = useId();

  function open(target: HTMLElement) {
    setPosition(positionNextTo(target.getBoundingClientRect()));
  }

  return (
    <>
      <button
        type="button"
        className="sykes-grade"
        data-letter={scale.letter}
        aria-label={`Sykes sliding scale ${scale.letter} for ${ticker}`}
        aria-describedby={position ? cardId : undefined}
        onMouseEnter={(event) => open(event.currentTarget)}
        onMouseLeave={() => setPosition(null)}
        onFocus={(event) => open(event.currentTarget)}
        onBlur={() => setPosition(null)}
      >
        {scale.letter}
      </button>
      {position && (
        <div id={cardId} role="tooltip" className="sykes-card" style={position}>
          <p className="sykes-card-title">
            Sykes sliding scale: {scale.letter} ({scale.points}/{MAX_POINTS})
          </p>
          <ul>
            {scale.factors.map((factor) => (
              <li key={factor.name} data-grade={factor.grade}>
                <span className="sykes-symbol" aria-hidden="true">
                  {GRADE_SYMBOLS[factor.grade]}
                </span>
                <span className="sykes-factor">{factor.name}</span>
                <span className="muted">{factor.detail}</span>
              </li>
            ))}
          </ul>
          <p className="muted sykes-card-note">Our scoring of Sykes's seven P.R.E.P.A.R.E. factors.</p>
        </div>
      )}
    </>
  );
}
