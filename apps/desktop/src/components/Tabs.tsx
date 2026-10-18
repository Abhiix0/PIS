import { useId, useRef, type KeyboardEvent } from "react";

export type TabsProps = {
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
};

// Roving tabindex; arrow keys / Home / End move selection. Panels are the caller's job: use aria-labelledby={`${tabId}-<id>`}.
export function Tabs({ tabs, value, onChange }: TabsProps) {
  const base = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    const n = tabs.length;
    const next = { ArrowRight: (i + 1) % n, ArrowLeft: (i + n - 1) % n, Home: 0, End: n - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    onChange(tabs[next]!.id);
    refs.current[next]?.focus();
  };
  return (
    <div role="tablist" className="tabs">
      {tabs.map((t, i) => (
        <button
          key={t.id}
          ref={(el) => {
            refs.current[i] = el;
          }}
          id={`${base}-${t.id}`}
          type="button"
          role="tab"
          aria-selected={t.id === value}
          tabIndex={t.id === value ? 0 : -1}
          onClick={() => onChange(t.id)}
          onKeyDown={(e) => onKey(e, i)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
