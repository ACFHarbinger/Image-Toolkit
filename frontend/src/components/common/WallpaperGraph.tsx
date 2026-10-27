import { SourceImage } from "./SourceImage";
import { type ReactElement } from "react";
import type { MonitorInfo } from "../../../../contracts/generated/ts";
import { graphPayload, moveQueuePath, readGraphPayload } from "./wallpaperGraph";

function baseName(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

/** Per-monitor nodes. Drop an image node on another monitor to move it. */
export function WallpaperGraph({
  monitors,
  queues,
  selectedMonitor,
  onSelectMonitor,
  onQueues,
}: {
  monitors: readonly MonitorInfo[];
  queues: Record<string, string[]>;
  selectedMonitor: string;
  onSelectMonitor: (monitorId: string) => void;
  onQueues: (queues: Record<string, string[]>) => void;
}): ReactElement {
  function onDrop(monitorId: string, event: React.DragEvent): void {
    event.preventDefault();
    const payload = readGraphPayload(event.dataTransfer.getData("text/plain"));
    if (!payload) {
      return;
    }
    onQueues(moveQueuePath(queues, payload.path, payload.monitorId, monitorId));
  }

  return (
    <div data-testid="wallpaper-graph" className="grid gap-4 md:grid-cols-2">
      {monitors.map((monitor) => {
        const images = queues[monitor.id] ?? [];
        const selected = monitor.id === selectedMonitor;
        return (
          <section
            key={monitor.id}
            aria-label={`${monitor.name} graph`}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => onDrop(monitor.id, event)}
            className={`rounded-xl border bg-gray-50 p-4 dark:bg-gray-900/50 ${
              selected ? "border-violet-500 ring-2 ring-violet-500" : "border-gray-200 dark:border-gray-700"
            }`}
          >
            <button
              type="button"
              aria-pressed={selected}
              onClick={() => onSelectMonitor(monitor.id)}
              className="mb-3 text-left"
            >
              <span className="block text-sm font-semibold">{monitor.name}</span>
              <span className="font-mono text-xs text-gray-500">
                {monitor.width}x{monitor.height} @ ({monitor.x}, {monitor.y})
              </span>
            </button>
            <div className="flex flex-wrap gap-2">
              {images.length === 0 ? (
                <p className="text-xs text-gray-400">Drop a thumbnail here to build this monitor's sequence.</p>
              ) : null}
              {images.map((path) => (
                <button
                  key={path}
                  type="button"
                  draggable
                  aria-label={baseName(path)}
                  title={path}
                  onDragStart={(event) => {
                    event.dataTransfer.setData("text/plain", graphPayload(monitor.id, path));
                    event.dataTransfer.effectAllowed = "move";
                  }}
                  className="w-24 overflow-hidden rounded-lg border border-gray-300 bg-white text-left dark:border-gray-600 dark:bg-gray-800"
                >
                  <SourceImage path={path} alt="" className="h-16 w-full object-cover" draggable={false} />
                  <span className="block truncate px-1 py-0.5 text-[10px]">{baseName(path)}</span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
      {monitors.length === 0 ? (
        <p className="text-sm text-gray-400">No monitors yet. Refresh the layout, then drop images onto a monitor.</p>
      ) : null}
    </div>
  );
}
