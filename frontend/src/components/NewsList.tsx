import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { NewsItem } from "../api/stocks";
import { formatNewsTime, isWebUrl } from "../format";
import { firstCutoff, showMore, SkippedStretch } from "../newsWindow";

interface NewsListProps {
  // null while loading.
  items: NewsItem[] | null;
  error: string | null;
  now?: Date;
}

const SHORT_DATE = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "numeric" });

// The box shows this many articles; the rest scroll inside it, so the page never grows.
const VISIBLE_ARTICLES = 5;

// Fit the box to the bottom of its 5th article. Measured, not a fixed height, because long
// titles wrap onto a second line. Fewer articles: no limit.
function fitToFirstArticles(box: HTMLElement): void {
  const articles = box.querySelectorAll<HTMLElement>(".news-row");
  const last = articles[VISIBLE_ARTICLES - 1];
  box.style.maxHeight = articles.length > VISIBLE_ARTICLES && last ? `${last.offsetTop + last.offsetHeight}px` : "";
}

type Row = { kind: "news"; item: NewsItem } | { kind: "gap"; stretch: SkippedStretch };

function rowTime(row: Row): number {
  return row.kind === "news" ? Date.parse(row.item.time) : row.stretch.to.getTime();
}

// Render with key={ticker} so another stock starts again from its last 2 weeks.
export function NewsList({ items, error, now = new Date() }: NewsListProps) {
  const [cutoff, setCutoff] = useState(() => firstCutoff(now));
  const [gaps, setGaps] = useState<SkippedStretch[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);
  const refit = useCallback(() => {
    if (boxRef.current) fitToFirstArticles(boxRef.current);
  }, []);

  useLayoutEffect(refit);

  useEffect(() => {
    window.addEventListener("resize", refit);
    return () => window.removeEventListener("resize", refit);
  }, [refit]);

  if (error) return <p role="alert" className="alert news-list">Couldn't load news: {error}</p>;
  if (items == null) return <p className="muted news-list">Loading news…</p>;

  const shown = items.filter((item) => Date.parse(item.time) >= cutoff.getTime());
  const rows: Row[] = [
    ...shown.map((item): Row => ({ kind: "news", item })),
    ...gaps.map((stretch): Row => ({ kind: "gap", stretch })),
  ].sort((left, right) => rowTime(right) - rowTime(left));
  const next = showMore(items, now, cutoff);

  function handleShowMore() {
    if (!next) return;
    setCutoff(next.cutoff);
    if (next.skipped) setGaps([...gaps, next.skipped]);
  }

  return (
    <section className="news-list" aria-label="News">
      <h3 className="editor-section-title">News</h3>
      {shown.length === 0 && gaps.length === 0 && <p className="muted">No news in the last 2 weeks.</p>}
      <div ref={boxRef} className="news-scroll" role="region" aria-label="News articles">
        <ul className="news-rows">
          {rows.map((row) =>
            row.kind === "news" ? (
              <li key={`${row.item.time}-${row.item.url}`} className="news-row">
                <span className="muted news-time">{formatNewsTime(row.item.time, now)}</span>
                <span className="news-source">{row.item.source}</span>
                {isWebUrl(row.item.url) ? (
                  <a href={row.item.url} target="_blank" rel="noreferrer" className="news-title">
                    {row.item.title}
                  </a>
                ) : (
                  <span className="news-title">{row.item.title}</span>
                )}
              </li>
            ) : (
              <li key={`gap-${row.stretch.to.toISOString()}`} className="muted news-gap">
                No news {SHORT_DATE.format(row.stretch.from)} – {SHORT_DATE.format(row.stretch.to)}
              </li>
            ),
          )}
        </ul>
        {next && (
          <button type="button" onClick={handleShowMore}>
            Show more
          </button>
        )}
      </div>
    </section>
  );
}
