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

// L = log trade, P = pass, Escape = close the panel. All ignored while typing; L and P also with
// modifier keys so browser shortcuts (Ctrl+L) keep working.
export function useJournalShortcuts({ onLogTrade, onPass, onClose }: ShortcutHandlers, isEnabled: boolean): void {
  useEffect(() => {
    if (!isEnabled) return;
    function handleKeyDown(event: KeyboardEvent) {
      // Escape while typing belongs to the field (closing a date picker), not the panel:
      // closing would throw away a half-entered trade.
      if (isTyping(event.target)) return;
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "l") onLogTrade();
      if (key === "p") onPass();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onLogTrade, onPass, onClose, isEnabled]);
}
