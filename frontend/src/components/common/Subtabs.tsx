export function Subtabs({
  tabs,
  active,
  onChange,
}: {
  tabs: readonly string[];
  active: string;
  onChange: (tab: string) => void;
}) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-it-border bg-it-surface px-4 pt-2">
      {tabs.map((tab) => {
        const selected = tab === active;
        return (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab)}
            className={`rounded-t-lg px-3 py-2 text-sm font-medium ${
              selected
                ? "border border-b-0 border-it-border bg-it-window-bg text-it-text"
                : "text-it-muted-text hover:bg-it-window-bg"
            }`}
          >
            {tab}
          </button>
        );
      })}
    </div>
  );
}
