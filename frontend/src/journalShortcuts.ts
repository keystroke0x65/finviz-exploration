import { useEffect } from "react";

interface ShortcutHandlers {
  onLogTrade: () => void;
  onPass: () => void;
  onClose: () => void;
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

// L = log trade, P = pass, Escape = close the panel. Ignored while typing or with modifier keys
// so browser shortcuts (Ctrl+L) keep working.
export function useJournalShortcuts({ onLogTrade, onPass, onClose }: ShortcutHandlers, isEnabled: boolean): void {
  useEffect(() => {
    if (!isEnabled) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "l") onLogTrade();
      if (key === "p") onPass();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onLogTrade, onPass, onClose, isEnabled]);
}
