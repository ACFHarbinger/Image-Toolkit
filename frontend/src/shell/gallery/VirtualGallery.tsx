import { useEffect, useRef, useState } from "react";
import { renderCacheAssetUrl } from "./assetUrl";
import { visibleWindow } from "./window";

export interface GalleryStill {
  id: string;
  cachePath: string;
}

interface VirtualGalleryProps {
  items: GalleryStill[];
  scrollTop: number;
  viewportHeight: number;
  rowHeight: number;
  columns: number;
  onScroll?: (scrollTop: number) => void;
}

/**
 * Mounts only the visible window. `items` may be large; cells outside
 * the window are not created. Image sources must already be render-cache
 * paths. Anything else is left blank rather than pointed at an original.
 */
export function VirtualGallery({
  items,
  scrollTop,
  viewportHeight,
  rowHeight,
  columns,
  onScroll,
}: VirtualGalleryProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const [offset, setOffset] = useState(scrollTop);
  useEffect(() => {
    setOffset(scrollTop);
    const node = scroller.current;
    if (node && node.scrollTop !== scrollTop) {
      node.scrollTop = scrollTop;
    }
  }, [scrollTop]);
  const window = visibleWindow(items.length, {
    scrollTop: offset,
    viewportHeight,
    rowHeight,
    columns,
  });
  const visible = items.slice(window.start, window.end);
  const totalHeight = Math.ceil(items.length / Math.max(1, columns)) * rowHeight;
  return (
    <div
      ref={scroller}
      data-testid="virtual-gallery"
      data-count={items.length}
      data-mounted={window.mounted}
      style={{ height: viewportHeight, overflow: "auto" }}
      onScroll={(event) => {
        const next = event.currentTarget.scrollTop;
        setOffset(next);
        onScroll?.(next);
      }}
    >
      <div style={{ height: totalHeight, position: "relative" }}>
        {visible.map((item, offset) => {
          const src = renderCacheAssetUrl(item.cachePath);
          const index = window.start + offset;
          const row = Math.floor(index / columns);
          const column = index % columns;
          return (
            <div
              key={item.id}
              data-testid="gallery-cell"
              data-index={index}
              style={{
                position: "absolute",
                top: row * rowHeight,
                left: `${(100 / columns) * column}%`,
                width: `${100 / columns}%`,
                height: rowHeight,
              }}
            >
              {src ? <img alt="" src={src} /> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
