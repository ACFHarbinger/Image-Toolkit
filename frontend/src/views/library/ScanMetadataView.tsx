import React, { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  FolderOpen,
  RefreshCcw,
  Tag,
  CheckCircle2,
  Clock,
  Sparkles,
  Save,
  CheckSquare,
  Square,
  Image as ImageIcon,
} from "lucide-react";
import type { HostClient } from "../../hostclient";
import type { GroupRecord, ScannedImage } from "../../../../contracts/generated/ts";
import { LibraryThumb } from "./LibraryThumb";

function uniqueNames(values: readonly string[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (let i = 0; i < values.length; i += 1) {
    const value = values[i];
    if (seen.has(value)) continue;
    seen.add(value);
    names.push(value);
  }
  return names;
}

type ScanFileSort = "scanned" | "name" | "size";

function sortDisplayedImages(rows: readonly ScannedImage[], sort: ScanFileSort): ScannedImage[] {
  if (sort === "scanned") {
    return rows.slice();
  }
  const ordered = rows.slice();
  if (sort === "name") {
    ordered.sort((a, b) => a.filename.localeCompare(b.filename));
    return ordered;
  }
  ordered.sort((a, b) => {
    if (a.size_bytes !== b.size_bytes) {
      return a.size_bytes - b.size_bytes;
    }
    return a.filename.localeCompare(b.filename);
  });
  return ordered;
}

function subgroupOptions(groups: readonly GroupRecord[], groupName: string): string[] {
  const trimmed = groupName.trim();
  for (let i = 0; i < groups.length; i += 1) {
    if (groups[i].name === trimmed) {
      return uniqueNames(groups[i].subgroups);
    }
  }
  const all: string[] = [];
  for (let i = 0; i < groups.length; i += 1) {
    const subgroups = groups[i].subgroups;
    for (let j = 0; j < subgroups.length; j += 1) {
      all.push(subgroups[j]);
    }
  }
  return uniqueNames(all);
}

export interface ScanMetadataViewProps {
  hostClient: HostClient;
  showModal?: (message: string, type?: "info" | "error" | "success") => void;
  onAddImagesToDb?: (files: File[]) => void;
}

export function ScanMetadataView({ hostClient, showModal }: ScanMetadataViewProps) {
  const [directory, setDirectory] = useState("");
  const [recursive, setRecursive] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [images, setImages] = useState<ScannedImage[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [dbAvailable, setDbAvailable] = useState<boolean | null>(null);
  const [groupName, setGroupName] = useState("");
  const [subgroupName, setSubgroupName] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [filterNewOnly, setFilterNewOnly] = useState(false);
  const [filterInDb, setFilterInDb] = useState(false);
  const [fileSort, setFileSort] = useState<ScanFileSort>("scanned");
  const [previewText, setPreviewText] = useState("");
  const [previewPng, setPreviewPng] = useState("");
  const [catalogGroups, setCatalogGroups] = useState<GroupRecord[]>([]);
  const [knownTags, setKnownTags] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    const loadCatalog = async () => {
      if (
        typeof hostClient.listLibraryGroups !== "function" ||
        typeof hostClient.listLibraryTags !== "function"
      ) {
        return;
      }
      try {
        const [groupsResult, tagsResult] = await Promise.all([
          hostClient.listLibraryGroups(),
          hostClient.listLibraryTags(),
        ]);
        if (cancelled) return;
        setCatalogGroups(groupsResult.available ? groupsResult.groups : []);
        setKnownTags(tagsResult.available ? tagsResult.tags : []);
      } catch {
        if (cancelled) return;
        setCatalogGroups([]);
        setKnownTags([]);
      }
    };
    void loadCatalog();
    return () => {
      cancelled = true;
    };
  }, [hostClient]);

  const groupOptions = uniqueNames(catalogGroups.map((group) => group.name));
  const subgroupOptionNames = subgroupOptions(catalogGroups, groupName);
  const tagOptions = uniqueNames(knownTags);

  const notify = (msg: string, type: "info" | "error" | "success" = "info") => {
    if (showModal) {
      showModal(msg, type);
    }
  };

  const handleBrowse = async () => {
    try {
      const picked = await open({ directory: true, multiple: false, defaultPath: directory || undefined });
      if (typeof picked === "string" && picked) {
        setDirectory(picked);
      }
    } catch {
      // The text field still edits the path when the dialog plugin is absent.
    }
  };

  const handleScan = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!directory.trim()) {
      notify("Please enter a directory path to scan.", "error");
      return;
    }
    setScanning(true);
    try {
      const res = await hostClient.scanDirectory({
        directory: directory.trim(),
        recursive,
        formats: ["webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff"],
        max_results: 50000,
      });
      setImages(res.images);
      setDbAvailable(res.database_available);
      setSelectedPaths(new Set());
      notify(`Discovered ${res.total_found} image(s).`, "success");
    } catch (err) {
      notify(`Scan failed: ${String(err)}`, "error");
    } finally {
      setScanning(false);
    }
  };

  const handleAddTag = () => {
    const trimmed = tagInput.trim().toLowerCase();
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  const toggleKnownTag = (name: string, checked: boolean) => {
    if (checked) {
      if (!tags.includes(name)) {
        setTags([...tags, name]);
      }
      return;
    }
    setTags(tags.filter((t) => t !== name));
  };

  const handleSuggestTags = async () => {
    if (selectedPaths.size === 0) {
      notify("Select at least one image to suggest tags.", "error");
      return;
    }
    try {
      const res = await hostClient.scanSuggestTags({
        paths: Array.from(selectedPaths),
      });
      const suggestedSet = new Set<string>(tags);
      for (const p of selectedPaths) {
        const pTags = res.suggestions[p] || [];
        pTags.forEach((t) => suggestedSet.add(t));
      }
      setTags(Array.from(suggestedSet));
      notify("Heuristic tags suggested from file paths.", "success");
    } catch (err) {
      notify(`Tag suggestion failed: ${String(err)}`, "error");
    }
  };

  const handleSaveMetadata = async () => {
    if (selectedPaths.size === 0) {
      notify("Select at least one image to update metadata.", "error");
      return;
    }
    setSaving(true);
    try {
      const items = Array.from(selectedPaths).map((p) => ({
        path: p,
        tags,
        group_name: groupName.trim() || null,
        subgroup_name: subgroupName.trim() || null,
      }));
      const res = await hostClient.scanSaveMetadata({ items });
      if (res.success) {
        notify(`Successfully saved metadata for ${res.saved_count} image(s).`, "success");
      } else {
        const errDetail = res.errors?.join("; ") || "Unknown failure";
        notify(`Metadata save partially failed or offline: ${errDetail}`, "error");
      }
    } catch (err) {
      notify(`Save metadata failed: ${String(err)}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    const path = Array.from(selectedPaths)[0];
    if (!path) {
      notify("Select an image to preview.", "error");
      return;
    }
    try {
      const described = await hostClient.libraryPreviewDescribe({ paths: [path] });
      const frame = await hostClient.libraryPreviewFrame({ path });
      const item = described.items[0];
      const detail = item ? `${item.path} ${item.width}x${item.height} ${item.error}` : path;
      setPreviewText(detail);
      setPreviewPng(frame.error ? "" : frame.png_base64);
      if ((item && item.error) || frame.error) {
        notify((item && item.error) || frame.error, "error");
      }
    } catch (err) {
      notify(`Preview failed: ${String(err)}`, "error");
    }
  };

  const toggleSelect = (p: string) => {
    const next = new Set(selectedPaths);
    if (next.has(p)) {
      next.delete(p);
    } else {
      next.add(p);
    }
    setSelectedPaths(next);
  };

  const displayedImages = filterNewOnly
    ? images.filter((img) => !img.in_database)
    : filterInDb
      ? images.filter((img) => img.in_database)
      : images;
  const listedImages = sortDisplayedImages(displayedImages, fileSort);

  const toggleSelectAll = () => {
    if (selectedPaths.size === displayedImages.length && displayedImages.length > 0) {
      setSelectedPaths(new Set());
    } else {
      setSelectedPaths(new Set(displayedImages.map((img) => img.path)));
    }
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4" data-testid="scan-metadata-view">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-200 pb-4 dark:border-gray-700">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">Scan and Tag</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Scan filesystem directories for image assets, inspect metadata, and batch tag into the library.
          </p>
        </div>
        {dbAvailable === false && (
          <div
            data-testid="scan-db-unavailable"
            className="rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
          >
            No database session is attached. Metadata saves fail until a vault session is open.
          </div>
        )}
      </div>

      <form onSubmit={handleScan} className="flex flex-wrap items-center gap-3">
        <div className="flex flex-1 min-w-[300px] items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-1.5 shadow-sm dark:border-gray-600 dark:bg-gray-800">
          <FolderOpen size={18} className="text-gray-400" />
          <input
            type="text"
            value={directory}
            onChange={(e) => setDirectory(e.target.value)}
            placeholder="/path/to/image/folder"
            className="w-full bg-transparent text-sm focus:outline-none dark:text-white"
          />
        </div>
        <label className="flex items-center gap-1.5 text-xs font-medium text-gray-700 dark:text-gray-300">
          <input
            type="checkbox"
            checked={recursive}
            onChange={(e) => setRecursive(e.target.checked)}
            className="rounded text-violet-600 focus:ring-violet-500"
          />
          Recursive
        </label>
        <button type="button" onClick={() => void handleBrowse()}>
          Browse
        </button>
        <button
          type="submit"
          disabled={scanning}
          className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-violet-700 disabled:opacity-50"
        >
          <RefreshCcw size={16} className={scanning ? "animate-spin" : ""} />
          {scanning ? "Scanning…" : "Scan Directory"}
        </button>
      </form>

      {images.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4 flex-1 min-h-0">
          <div className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800 lg:col-span-3">
            <div className="flex items-center justify-between border-b border-gray-100 pb-2 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={toggleSelectAll}
                  className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
                >
                  {selectedPaths.size === displayedImages.length && displayedImages.length > 0 ? (
                    <CheckSquare size={16} className="text-violet-600" />
                  ) : (
                    <Square size={16} />
                  )}
                  Select All ({selectedPaths.size}/{displayedImages.length})
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedPaths(new Set())}
                  className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
                >
                  Deselect all
                </button>
                <label className="ml-4 flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                  <input
                    type="checkbox"
                    checked={filterNewOnly}
                    onChange={(e) => {
                      setFilterNewOnly(e.target.checked);
                      if (e.target.checked) setFilterInDb(false);
                    }}
                    className="rounded text-violet-600"
                  />
                  New Only
                </label>
                <label className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                  Sort files
                  <select
                    aria-label="Sort files"
                    value={fileSort}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (value === "scanned" || value === "name" || value === "size") {
                        setFileSort(value);
                      }
                    }}
                    className="rounded border border-gray-300 bg-white px-1 py-0.5 dark:border-gray-600 dark:bg-gray-800"
                  >
                    <option value="scanned">As scanned</option>
                    <option value="name">Name</option>
                    <option value="size">Size</option>
                  </select>
                </label>
                <label className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                  <input
                    type="checkbox"
                    checked={filterInDb}
                    onChange={(e) => {
                      setFilterInDb(e.target.checked);
                      if (e.target.checked) setFilterNewOnly(false);
                    }}
                    className="rounded text-violet-600"
                  />
                  Show only in DB
                </label>
              </div>
              <span className="text-xs text-gray-500">
                Found {images.length} files ({images.filter((i) => i.in_database).length} in DB)
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1 pr-1">
              {listedImages.map((img) => {
                const isSelected = selectedPaths.has(img.path);
                return (
                  <div
                    key={img.path}
                    onClick={() => toggleSelect(img.path)}
                    className={`flex items-center justify-between rounded-lg border p-2 text-xs transition cursor-pointer ${
                      isSelected
                        ? "border-violet-500 bg-violet-50/50 dark:border-violet-400 dark:bg-violet-950/20"
                        : "border-gray-200 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      {isSelected ? (
                        <CheckSquare size={15} className="text-violet-600 flex-shrink-0" />
                      ) : (
                        <Square size={15} className="text-gray-400 flex-shrink-0" />
                      )}
                      <LibraryThumb path={img.path} hostClient={hostClient} />
                      <ImageIcon size={16} className="text-gray-400 flex-shrink-0" />
                      <span className="font-medium text-gray-800 dark:text-gray-200 truncate">{img.filename}</span>
                      <span className="text-gray-400">
                        {img.width && img.height ? `${img.width}×${img.height}` : ""}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-gray-400">{(img.size_bytes / 1024).toFixed(1)} KB</span>
                      {img.in_database ? (
                        <span className="flex items-center gap-0.5 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                          <CheckCircle2 size={10} /> In DB
                        </span>
                      ) : (
                        <span className="flex items-center gap-0.5 rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                          <Clock size={10} /> New
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm">Metadata & Tags</h3>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Group Name</label>
              <input
                type="text"
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder="e.g. Anime"
                list="scan-group-options"
                className="rounded-lg border border-gray-300 bg-transparent px-2.5 py-1.5 text-xs dark:border-gray-600 dark:text-white"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Subgroup Name</label>
              <input
                type="text"
                value={subgroupName}
                onChange={(e) => setSubgroupName(e.target.value)}
                placeholder="e.g. Wallpapers"
                list="scan-subgroup-options"
                className="rounded-lg border border-gray-300 bg-transparent px-2.5 py-1.5 text-xs dark:border-gray-600 dark:text-white"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Add Tags</label>
              <div className="flex gap-1.5">
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddTag())}
                  placeholder="tag name"
                  list="scan-tag-options"
                  className="flex-1 rounded-lg border border-gray-300 bg-transparent px-2.5 py-1.5 text-xs dark:border-gray-600 dark:text-white"
                />
                <button
                  type="button"
                  onClick={handleAddTag}
                  className="rounded-lg bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200"
                >
                  Add
                </button>
              </div>
            </div>

            {tagOptions.length > 0 ? (
              <div className="flex flex-col gap-1">
                {tagOptions.map((name) => (
                  <label
                    key={name}
                    className="flex items-center gap-1.5 text-xs text-gray-700 dark:text-gray-300"
                  >
                    <input
                      type="checkbox"
                      checked={tags.includes(name)}
                      onChange={(e) => toggleKnownTag(name, e.target.checked)}
                      className="rounded text-violet-600"
                    />
                    {`Tag ${name}`}
                  </label>
                ))}
              </div>
            ) : null}

            {tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {tags.map((t) => (
                  <span
                    key={t}
                    className="flex items-center gap-1 rounded bg-violet-100 px-2 py-0.5 text-[11px] font-medium text-violet-800 dark:bg-violet-950 dark:text-violet-300"
                  >
                    <Tag size={10} />
                    {t}
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(t)}
                      className="ml-0.5 hover:text-violet-950 dark:hover:text-white"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            <button
              type="button"
              onClick={() => void handlePreview()}
              disabled={selectedPaths.size === 0}
              data-testid="scan-preview"
              className="flex items-center justify-center gap-1.5 rounded-lg border border-gray-300 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              Preview selected
            </button>
            {previewText ? (
              <div data-testid="scan-preview-pane">
                <p>{previewText}</p>
                {previewPng ? <img alt="Scan preview" src={"data:image/png;base64," + previewPng} /> : null}
              </div>
            ) : null}

            <button
              type="button"
              onClick={handleSuggestTags}
              disabled={selectedPaths.size === 0}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-gray-300 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              <Sparkles size={14} className="text-violet-600" />
              Suggest from Path
            </button>

            <button
              type="button"
              onClick={handleSaveMetadata}
              disabled={saving || selectedPaths.size === 0}
              className="mt-auto flex items-center justify-center gap-1.5 rounded-lg bg-violet-600 py-2 text-xs font-semibold text-white shadow hover:bg-violet-700 disabled:opacity-50"
            >
              <Save size={14} />
              {saving ? "Saving…" : `Apply to Selected (${selectedPaths.size})`}
            </button>
          </div>
        </div>
      )}
      <datalist id="scan-group-options">
        {groupOptions.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </datalist>
      <datalist id="scan-subgroup-options">
        {subgroupOptionNames.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </datalist>
      <datalist id="scan-tag-options">
        {tagOptions.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </datalist>
    </div>
  );
}
