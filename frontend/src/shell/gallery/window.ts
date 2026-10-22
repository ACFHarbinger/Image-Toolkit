export interface GridWindow {
  start: number;
  end: number;
  mounted: number;
}

export interface WindowOptions {
  scrollTop: number;
  viewportHeight: number;
  rowHeight: number;
  columns: number;
  overscanRows?: number;
}

/** Index range a virtualised gallery mounts. The rest stay unmounted. */
export function visibleWindow(itemCount: number, options: WindowOptions): GridWindow {
  const columns = Math.max(1, Math.floor(options.columns));
  const rowHeight = Math.max(1, options.rowHeight);
  const overscan = options.overscanRows ?? 1;
  const totalRows = Math.ceil(itemCount / columns);
  const firstVisible = Math.floor(Math.max(0, options.scrollTop) / rowHeight);
  const visibleRows = Math.max(1, Math.ceil(options.viewportHeight / rowHeight));
  const firstRow = Math.max(0, firstVisible - overscan);
  const lastRow = Math.min(totalRows, firstVisible + visibleRows + overscan);
  const start = Math.min(itemCount, firstRow * columns);
  const end = Math.min(itemCount, lastRow * columns);
  return { start, end, mounted: Math.max(0, end - start) };
}
