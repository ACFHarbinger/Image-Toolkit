import { CatalogEntry } from "./catalog";

interface RibbonProps {
  workspaceTitle: string;
  routes: CatalogEntry[];
  activeId: string;
  onSelectModule: (id: string) => void;
}

/** Child routes of the active workspace. Hidden when the selection is a page. */
export function Ribbon({ workspaceTitle, routes, activeId, onSelectModule }: RibbonProps) {
  if (routes.length === 0) {
    return null;
  }
  return (
    <div
      aria-label="Workspace ribbon"
      className="flex items-center gap-2 border-b border-gray-200 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-800"
    >
      <span className="text-xs font-semibold text-gray-500">{workspaceTitle}</span>
      {routes.map((route) => {
        const selected = route.id === activeId;
        return (
          <button
            key={route.id}
            type="button"
            data-catalog-id={route.id}
            aria-pressed={selected}
            onClick={() => onSelectModule(route.id)}
            className={`rounded-full px-3 py-1 text-xs ${
              selected
                ? "bg-violet-600 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-100"
            }`}
          >
            {route.title}
          </button>
        );
      })}
    </div>
  );
}
