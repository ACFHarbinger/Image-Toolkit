import { SourceImage } from "./SourceImage";
import { useRef, type ReactElement } from "react";
import { deskButtonClass, deskControlClass } from "./DeskForm";
import { dragPosition, type CanvasTile } from "./canvasLayout";

function baseName(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

/** Draggable tiles on a scaled board. Positions stay in canvas pixels. */
export function MergeCanvasBoard({
  tiles,
  canvasWidth,
  canvasHeight,
  background,
  selectedPath,
  onSelect,
  onMove,
  onResize,
  onFit,
  onRemove,
  onClear,
}: {
  tiles: readonly CanvasTile[];
  canvasWidth: number;
  canvasHeight: number;
  background: string;
  selectedPath: string;
  onSelect: (path: string) => void;
  onMove: (path: string, x: number, y: number) => void;
  onResize: (path: string, w: number, h: number) => void;
  onFit: (path: string, naturalWidth: number, naturalHeight: number) => void;
  onRemove: (path: string) => void;
  onClear: () => void;
}): ReactElement {
  const boardRef = useRef<HTMLDivElement>(null);
  const selected = tiles.find((tile) => tile.path === selectedPath) ?? null;
  const fill = background === "white" ? "#ffffff" : background === "black" ? "#000000" : "transparent";

  function startDrag(event: React.PointerEvent, tile: CanvasTile): void {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    onSelect(tile.path);
    const board = boardRef.current?.getBoundingClientRect();
    const boardWidth = board?.width ?? 0;
    const boardHeight = board?.height ?? 0;
    const origin = { x: tile.x, y: tile.y };
    const startX = event.clientX;
    const startY = event.clientY;
    const move = (ev: PointerEvent) => {
      const next = dragPosition(
        origin,
        ev.clientX - startX,
        ev.clientY - startY,
        boardWidth,
        boardHeight,
        canvasWidth,
        canvasHeight,
      );
      onMove(tile.path, next.x, next.y);
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  }

  return (
    <div className="flex flex-col gap-2" data-testid="merge-canvas">
      <div
        ref={boardRef}
        className="relative w-full overflow-hidden rounded-lg border border-it-accent"
        style={{ aspectRatio: `${canvasWidth} / ${canvasHeight}`, background: fill }}
      >
        {tiles.length === 0 ? (
          <p className="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-it-muted-text">
            Scan a directory or select thumbnails to place them on the canvas.
          </p>
        ) : null}
        {tiles.map((tile) => (
          <button
            key={tile.path}
            type="button"
            aria-label={baseName(tile.path)}
            title={tile.path}
            onPointerDown={(event) => startDrag(event, tile)}
            className={`absolute overflow-hidden border ${
              tile.path === selectedPath ? "border-it-accent ring-2 ring-it-accent" : "border-white/70"
            }`}
            style={{
              left: `${(tile.x / canvasWidth) * 100}%`,
              top: `${(tile.y / canvasHeight) * 100}%`,
              width: `${(tile.w / canvasWidth) * 100}%`,
              height: `${(tile.h / canvasHeight) * 100}%`,
            }}
          >
            <SourceImage
              path={tile.path}
              alt=""
              draggable={false}
              className="h-full w-full object-fill"
              onDimensions={(width, height) => onFit(tile.path, width, height)}
            />
          </button>
        ))}
      </div>
      {selected ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <label className="text-xs text-it-muted-text">
            X
            <input
              aria-label="Tile x"
              className={deskControlClass}
              type="number"
              value={selected.x}
              onChange={(event) => onMove(selected.path, Number(event.target.value), selected.y)}
            />
          </label>
          <label className="text-xs text-it-muted-text">
            Y
            <input
              aria-label="Tile y"
              className={deskControlClass}
              type="number"
              value={selected.y}
              onChange={(event) => onMove(selected.path, selected.x, Number(event.target.value))}
            />
          </label>
          <label className="text-xs text-it-muted-text">
            W
            <input
              aria-label="Tile width"
              className={deskControlClass}
              type="number"
              min={1}
              value={selected.w}
              onChange={(event) => onResize(selected.path, Number(event.target.value), selected.h)}
            />
          </label>
          <label className="text-xs text-it-muted-text">
            H
            <input
              aria-label="Tile height"
              className={deskControlClass}
              type="number"
              min={1}
              value={selected.h}
              onChange={(event) => onResize(selected.path, selected.w, Number(event.target.value))}
            />
          </label>
        </div>
      ) : null}
      <div className="flex gap-2">
        <button type="button" className={deskButtonClass} disabled={!selected} onClick={() => selected && onRemove(selected.path)}>
          Remove from canvas
        </button>
        <button type="button" className={deskButtonClass} disabled={tiles.length === 0} onClick={onClear}>
          Clear canvas
        </button>
      </div>
    </div>
  );
}
