import type { MouseEvent } from "react";
import { stockUrl } from "../stockLink";

interface StockLinkProps {
  ticker: string;
  onOpen: (ticker: string) => void;
}

const PRIMARY_BUTTON = 0;

function wantsNewTabOrWindow(event: MouseEvent<HTMLAnchorElement>): boolean {
  return event.button !== PRIMARY_BUTTON || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
}

// A real link, so Ctrl/Cmd-click, middle-click and "Open link in new tab" work; a plain
// click switches to the Stock view in this tab without reloading the page.
export function StockLink({ ticker, onOpen }: StockLinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (wantsNewTabOrWindow(event)) return;
    event.preventDefault();
    onOpen(ticker);
  }

  return (
    <a className="ticker-button" href={stockUrl(ticker)} onClick={handleClick}>
      {ticker}
    </a>
  );
}
