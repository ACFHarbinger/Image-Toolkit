import { ReactNode } from "react";
import { CatalogEntry } from "../catalog";
import {
  categoriesInOrder,
  classicPages,
  classicSubtabs,
  entryById,
  railCategory,
} from "../navigation";

interface ClassicShellProps {
  entries: readonly CatalogEntry[];
  activeId: string;
  onSelect: (id: string) => void;
  children: ReactNode;
}

function selectTarget(entries: readonly CatalogEntry[], page: CatalogEntry): string {
  const children = classicSubtabs(entries, page);
  return children[0]?.id ?? page.id;
}

export function ClassicShell({ entries, activeId, onSelect, children }: ClassicShellProps) {
  const categories = categoriesInOrder(entries);
  const active = entryById(entries, activeId);
  const category = active ? railCategory(active.category) : categories[0] ?? "";
  const pages = classicPages(entries, category);
  const page =
    active?.kind === "route"
      ? pages.find((item) => item.id === active.workspace_id) ?? pages[0]
      : pages.find((item) => item.id === active?.id) ?? pages[0];
  const subtabs = classicSubtabs(entries, page);

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-900/40">
        <label htmlFor="classic-category" className="text-xs font-semibold text-gray-500">
          Category
        </label>
        <select
          id="classic-category"
          aria-label="Category"
          value={category}
          onChange={(event) => {
            const nextPages = classicPages(entries, event.target.value);
            const first = nextPages[0];
            if (first) {
              onSelect(selectTarget(entries, first));
            }
          }}
          className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-600 dark:bg-gray-800"
        >
          {categories.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      <div role="tablist" aria-label={category} className="flex gap-1 overflow-x-auto border-b border-gray-200 px-2 py-1 dark:border-gray-700">
        {pages.map((tab) => {
          const selected = tab.id === page?.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              data-catalog-id={tab.id}
              aria-selected={selected}
              onClick={() => onSelect(selectTarget(entries, tab))}
              className={`rounded-md px-3 py-1.5 text-sm ${
                selected ? "bg-violet-600 text-white" : "text-gray-700 hover:bg-gray-100 dark:text-gray-200"
              }`}
            >
              {tab.title}
            </button>
          );
        })}
      </div>
      {subtabs.length > 0 ? (
        <div
          role="tablist"
          aria-label={`${page?.title ?? "Page"} subtabs`}
          className="flex gap-1 overflow-x-auto border-b border-gray-200 bg-white px-2 py-1 dark:border-gray-700 dark:bg-gray-800"
        >
          {subtabs.map((tab) => {
            const selected = tab.id === activeId;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                data-catalog-id={tab.id}
                aria-selected={selected}
                onClick={() => onSelect(tab.id)}
                className={`rounded-full px-3 py-1 text-xs ${
                  selected ? "bg-violet-600 text-white" : "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-100"
                }`}
              >
                {tab.title}
              </button>
            );
          })}
        </div>
      ) : null}
      {children}
    </div>
  );
}
