import { SourceImage } from "./SourceImage";
import { useState, type ReactElement } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { deskButtonClass, deskControlClass } from "./DeskForm";

const IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "bmp", "gif"];

function baseName(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

/** Directory scan plus a click-to-select thumbnail grid. Shared by the file tabs. */
export function ThumbnailGallery({
  selected,
  onSelectedChange,
  onScanned,
  multiple = true,
  extensions = IMAGE_EXTENSIONS,
  directoryLabel = "Image directory",
}: {
  selected: readonly string[];
  onSelectedChange: (paths: string[]) => void;
  onScanned?: (paths: string[]) => void;
  multiple?: boolean;
  extensions?: readonly string[];
  /** Distinct label when a page mounts more than one gallery. */
  directoryLabel?: string;
}): ReactElement {
  const [directory, setDirectory] = useState("");
  const [files, setFiles] = useState<string[]>([]);
  const [status, setStatus] = useState("");

  async function scan(dir: string): Promise<void> {
    const trimmed = dir.trim();
    if (!trimmed) {
      setStatus("Choose a directory.");
      return;
    }
    setStatus("Scanning…");
    try {
      const found = await invoke<string[]>("scan_files", {
        directory: trimmed,
        extensions: [...extensions],
        recursive: false,
      });
      const paths = Array.isArray(found) ? found : [];
      setFiles(paths);
      setStatus(paths.length === 0 ? "No matching files." : `${paths.length} files`);
      onScanned?.(paths);
    } catch (exc) {
      setFiles([]);
      setStatus(exc instanceof Error ? exc.message : "Scan failed.");
    }
  }

  async function browse(): Promise<void> {
    const picked = await open({ directory: true, multiple: false, title: "Select a directory" });
    if (typeof picked === "string" && picked) {
      setDirectory(picked);
      await scan(picked);
    }
  }

  function toggle(path: string): void {
    if (!multiple) {
      onSelectedChange(selected[0] === path ? [] : [path]);
      return;
    }
    if (selected.includes(path)) {
      onSelectedChange(selected.filter((item) => item !== path));
      return;
    }
    onSelectedChange([...selected, path]);
  }

  return (
    <div className="flex flex-col gap-2" data-testid="thumbnail-gallery">
      <div className="flex gap-2">
        <input
          aria-label={directoryLabel}
          className={deskControlClass}
          value={directory}
          placeholder="Directory of images"
          onChange={(event) => setDirectory(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void scan(directory);
            }
          }}
        />
        <button type="button" className={deskButtonClass} onClick={() => void browse()}>Browse</button>
        <button type="button" className={deskButtonClass} onClick={() => void scan(directory)}>Scan</button>
      </div>
      <div
        role="listbox"
        aria-label="Thumbnails"
        aria-multiselectable={multiple}
        className="grid max-h-64 grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-4 md:grid-cols-6"
      >
        {files.map((path) => {
          const name = baseName(path);
          const active = selected.includes(path);
          return (
            <button
              key={path}
              type="button"
              role="option"
              aria-selected={active}
              aria-label={name}
              title={path}
              onClick={() => toggle(path)}
              className={`flex flex-col gap-1 overflow-hidden rounded-lg border p-1 text-left ${
                active ? "border-it-accent ring-2 ring-it-accent" : "border-it-border"
              }`}
            >
              <SourceImage path={path} alt="" className="h-16 w-full rounded object-cover" draggable={false} />
              <span className="truncate text-[10px] text-it-muted-text">{name}</span>
            </button>
          );
        })}
      </div>
      {status ? <p className="text-xs text-it-muted-text">{status}</p> : null}
    </div>
  );
}
