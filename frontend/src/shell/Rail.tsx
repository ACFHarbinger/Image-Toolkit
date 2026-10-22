import { CatalogEntry } from "./catalog";
import { CATEGORY_MARK, iconFor } from "./icons";

interface RailProps {
  categories: string[];
  activeCategory: string;
  rows: CatalogEntry[];
  activeId: string;
  drawerOpen: boolean;
  onSelectCategory: (category: string) => void;
  onSelectModule: (id: string) => void;
  onToggleDrawer: () => void;
}

export function Rail({
  categories,
  activeCategory,
  rows,
  activeId,
  drawerOpen,
  onSelectCategory,
  onSelectModule,
  onToggleDrawer,
}: RailProps) {
  return (
    <nav aria-label="Catalog rail" className="flex shrink-0 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40">
      <div className="flex w-14 flex-col items-center gap-1 py-2">
        {categories.map((category) => (
          <button
            key={category}
            type="button"
            title={category}
            aria-label={`category ${category}`}
            aria-pressed={category === activeCategory}
            onClick={() => onSelectCategory(category)}
            className={`flex h-11 w-11 items-center justify-center rounded-lg text-lg ${
              category === activeCategory
                ? "bg-violet-600 text-white"
                : "hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
          >
            {CATEGORY_MARK[category] ?? "📦"}
          </button>
        ))}
        <button
          type="button"
          className="mt-auto text-xs text-gray-500"
          aria-label="Toggle navigation drawer"
          onClick={onToggleDrawer}
        >
          {drawerOpen ? "◀" : "▶"}
        </button>
      </div>
      {drawerOpen && (
        <div className="flex w-52 flex-col gap-1 overflow-y-auto p-2">
          <div className="px-2 py-1 text-xs font-bold uppercase tracking-wide text-gray-500">
            {activeCategory}
          </div>
          {rows.map((entry) => {
            const Icon = iconFor(entry.icon_name);
            const selected = entry.id === activeId;
            return (
              <button
                key={entry.id}
                type="button"
                data-catalog-id={entry.id}
                aria-current={selected ? "page" : undefined}
                onClick={() => onSelectModule(entry.id)}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm ${
                  selected
                    ? "bg-violet-100 font-medium text-violet-800 dark:bg-violet-900/40 dark:text-violet-200"
                    : "text-gray-700 hover:bg-gray-200 dark:text-gray-200 dark:hover:bg-gray-700"
                }`}
              >
                <Icon size={14} />
                {entry.title}
              </button>
            );
          })}
        </div>
      )}
    </nav>
  );
}
