import type { ReasonItem } from "../api/journal";

interface ReasonChipsProps {
  items: ReasonItem[];
  selected: string[];
  onToggle: (key: string) => void;
}

export function ReasonChips({ items, selected, onToggle }: ReasonChipsProps) {
  return (
    <div className="reason-chips">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className="reason-chip"
          aria-pressed={selected.includes(item.key)}
          onClick={() => onToggle(item.key)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function toggled(keys: string[], key: string): string[] {
  return keys.includes(key) ? keys.filter((existing) => existing !== key) : [...keys, key];
}
