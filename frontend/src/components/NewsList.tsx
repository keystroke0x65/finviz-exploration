import { useState } from "react";
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

type Row = { kind: "news"; item: NewsItem } | { kind: "gap"; stretch: SkippedStretch };

function rowTime(row: Row): number {
  return row.kind === "news" ? Date.parse(row.item.time) : row.stretch.to.getTime();
}

// Render with key={ticker} so another stock starts again from its last 2 weeks.
export function NewsList({ items, error, now = new Date() }: NewsListProps) {
  const [cutoff, setCutoff] = useState(() => firstCutoff(now));
  const [gaps, setGaps] = useState<SkippedStretch[]>([]);

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
    </section>
  );
}
