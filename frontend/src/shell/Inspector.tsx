import { CatalogEntry } from "./catalog";

interface InspectorProps {
  entry: CatalogEntry | undefined;
  open: boolean;
  onToggle: () => void;
}

export function Inspector({ entry, open, onToggle }: InspectorProps) {
  return (
    <aside
      aria-label="Context inspector"
      className={`shrink-0 border-l border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800 ${
        open ? "w-72" : "w-8"
      }`}
    >
      <button
        type="button"
        aria-label="Toggle inspector"
        aria-pressed={open}
        onClick={onToggle}
        className="w-full px-2 py-2 text-xs text-gray-500"
      >
        {open ? "Inspector" : "▸"}
      </button>
      {open && entry && (
        <dl data-testid="inspector-body" className="space-y-2 px-3 pb-3 text-xs text-gray-700 dark:text-gray-200">
          <div>
            <dt className="text-gray-500">Catalog id</dt>
            <dd>{entry.id}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Category</dt>
            <dd>{entry.category}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Kind</dt>
            <dd>{entry.kind}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Window</dt>
            <dd>{entry.window_id}</dd>
          </div>
          {entry.companion_window_id && (
            <div>
              <dt className="text-gray-500">Companion window</dt>
              <dd>{entry.companion_window_id}</dd>
            </div>
          )}
          <div>
            <dt className="text-gray-500">Capabilities</dt>
            <dd>{entry.capability_flags.length ? entry.capability_flags.join(", ") : "none"}</dd>
          </div>
        </dl>
      )}
    </aside>
  );
}
