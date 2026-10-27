// Library Image Search (L-03 / #897): the HostClient-driven search page for
// `library.search`, riding the library capability from L-02 (#896). It
// replaces the legacy Rust-invoke SearchTab mapping; `search_files` /
// `get_all_tags` / `get_all_groups` in db.rs are the surfaces it stops
// calling (L-07 #901 retires them). The store reader arrives with the
// daemon lease; until then the results stay `available: false` and the
// view shows its unavailable notice.

import React, { useEffect, useState } from "react";
import { LibraryThumb } from "./LibraryThumb";
import type {
  GroupRecord,
  ImageRecord,
  ListGroupsResult,
  ListImagesResult,
  ListTagsResult,
  TagRecord,
} from "../../../../contracts/generated/ts";
import type { HostClient } from "../../hostclient";

export interface ImageSearchProps {
  hostClient: HostClient;
}

const FORMATS = ["png", "jpg", "jpeg", "webp", "avif", "bmp", "tiff", "gif"] as const;
const PAGE_SIZE = 100;

function categoryLabel(category: string): string {
  return category === "" ? "(No Category)" : category;
}

function distinctCategories(tags: TagRecord[]): string[] {
  const categories: string[] = [];
  for (const tag of tags) {
    const category = tag.category ?? "";
    if (!categories.includes(category)) categories.push(category);
  }
  return categories;
}

function categoryAllows(name: string, catalog: TagRecord[] | null, unchecked: readonly string[]): boolean {
  if (!catalog) return true;
  const record = catalog.find((tag) => tag.name === name);
  if (!record) return true;
  return !unchecked.includes(record.category ?? "");
}

type SortKey = "returned" | "filename" | "date_added" | "size";
type SortOrder = "asc" | "desc";

function isSortKey(value: string): value is SortKey {
  return value === "returned" || value === "filename" || value === "date_added" || value === "size";
}

function isSortOrder(value: string): value is SortOrder {
  return value === "asc" || value === "desc";
}

function compareMissingLast(
  left: string | number | null | undefined,
  right: string | number | null | undefined,
  comparePresent: (left: string | number, right: string | number) => number,
  descending: boolean,
): number {
  const leftMissing = left == null || left === "";
  const rightMissing = right == null || right === "";
  if (leftMissing || rightMissing) {
    if (leftMissing === rightMissing) return 0;
    return leftMissing ? 1 : -1;
  }
  const ordered = comparePresent(left, right);
  return descending ? -ordered : ordered;
}

function sortedImages(rows: readonly ImageRecord[], key: SortKey, order: SortOrder): ImageRecord[] {
  if (key === "returned") return rows.slice();
  const descending = order === "desc";
  const copy = rows.slice();
  copy.sort((left, right) => {
    if (key === "filename") {
      const ordered = left.filename.localeCompare(right.filename);
      return descending ? -ordered : ordered;
    }
    if (key === "date_added") {
      return compareMissingLast(
        left.date_added,
        right.date_added,
        (a, b) => String(a).localeCompare(String(b)),
        descending,
      );
    }
    return compareMissingLast(left.file_size, right.file_size, (a, b) => Number(a) - Number(b), descending);
  });
  return copy;
}

function rowFactSuffix(image: ImageRecord): string {
  const facts: string[] = [];
  if (typeof image.file_size === "number") facts.push(`${image.file_size} B`);
  if (typeof image.date_added === "string" && image.date_added !== "") facts.push(image.date_added);
  if (typeof image.date_modified === "string" && image.date_modified !== "") facts.push(image.date_modified);
  return facts.length ? ` · ${facts.join(" · ")}` : "";
}

function presentProperties(image: ImageRecord): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];
  const push = (label: string, value: string | number | null | undefined) => {
    if (value === null || value === undefined) return;
    rows.push({ label, value: String(value) });
  };
  push("Path", image.file_path);
  push("Filename", image.filename);
  push("Width", image.width);
  push("Height", image.height);
  push("File size", image.file_size);
  push("Date added", image.date_added);
  push("Date modified", image.date_modified);
  push("Group", image.group_name);
  push("Subgroup", image.subgroup_name);
  if (image.tags != null) {
    rows.push({ label: "Tags", value: image.tags.join(", ") });
  }
  push("Phash", image.phash);
  return rows;
}

// Kept off the groups/tags Promise.all. A missing method, an unavailable
// catalog, or a throw leaves every listLibraryTags name visible.
async function readTagCatalog(hostClient: HostClient): Promise<TagRecord[] | null> {
  if (typeof hostClient.libraryAdminCatalog !== "function") return null;
  try {
    const catalog = await hostClient.libraryAdminCatalog();
    if (!catalog.available) return null;
    return catalog.tags;
  } catch {
    return null;
  }
}

export function ImageSearch({ hostClient }: ImageSearchProps) {
  const [groups, setGroups] = useState<GroupRecord[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [selectedSubgroups, setSelectedSubgroups] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [catalogTags, setCatalogTags] = useState<TagRecord[] | null>(null);
  const [uncheckedCategories, setUncheckedCategories] = useState<string[]>([]);
  const [selectedFormats, setSelectedFormats] = useState<string[]>([]);
  const [pattern, setPattern] = useState("");
  const [images, setImages] = useState<ImageRecord[]>([]);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("returned");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [searched, setSearched] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [propertiesOpen, setPropertiesOpen] = useState(false);
  const [preview, setPreview] = useState<{
    path: string;
    width: number;
    height: number;
    error: string;
    png: string;
  } | null>(null);

  const applyFilters = (groupsResult: ListGroupsResult, tagsResult: ListTagsResult) => {
    setGroups(groupsResult.groups);
    setTags(groupsResult.available ? tagsResult.tags : []);
    setAvailable(groupsResult.available);
    setReady(true);
  };

  const acceptCatalog = (next: TagRecord[] | null) => {
    setCatalogTags(next);
    if (!next) return;
    setSelectedTags((current) => current.filter((name) => categoryAllows(name, next, uncheckedCategories)));
  };

  const loadFilters = async () => {
    const [groupsResult, tagsResult] = await Promise.all([
      hostClient.listLibraryGroups(),
      hostClient.listLibraryTags(),
    ]);
    applyFilters(groupsResult, tagsResult);
    acceptCatalog(await readTagCatalog(hostClient));
  };

  useEffect(() => {
    let cancelled = false;
    void Promise.all([hostClient.listLibraryGroups(), hostClient.listLibraryTags()])
      .then(([groupsResult, tagsResult]) => {
        if (!cancelled) applyFilters(groupsResult, tagsResult);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      });
    void readTagCatalog(hostClient).then((next) => {
      if (!cancelled) acceptCatalog(next);
    });
    return () => {
      cancelled = true;
    };
  }, [hostClient]);

  const toggle = (name: string, list: string[], setList: (next: string[]) => void) => {
    setList(list.includes(name) ? list.filter((item) => item !== name) : [...list, name]);
  };

  const subgroupsFor = (groupNames: string[]): string[] => {
    const selected = new Set(groupNames);
    const seen = new Set<string>();
    const names: string[] = [];
    for (const group of groups) {
      if (selected.size > 0 && !selected.has(group.name)) continue;
      for (const subgroup of group.subgroups) {
        if (seen.has(subgroup)) continue;
        seen.add(subgroup);
        names.push(subgroup);
      }
    }
    return names;
  };

  const visibleSubgroups = subgroupsFor(selectedGroups);

  const setCategoryChecked = (category: string, checked: boolean) => {
    const nextUnchecked = checked
      ? uncheckedCategories.filter((item) => item !== category)
      : uncheckedCategories.includes(category)
        ? uncheckedCategories
        : [...uncheckedCategories, category];
    setUncheckedCategories(nextUnchecked);
    if (!checked) {
      setSelectedTags((current) => current.filter((name) => categoryAllows(name, catalogTags, nextUnchecked)));
    }
  };

  const toggleGroup = (name: string) => {
    const nextGroups = selectedGroups.includes(name)
      ? selectedGroups.filter((item) => item !== name)
      : [...selectedGroups, name];
    const allowed = new Set(subgroupsFor(nextGroups));
    setSelectedGroups(nextGroups);
    setSelectedSubgroups((current) => current.filter((item) => allowed.has(item)));
  };

  const search = async () => {
    setBusy(true);
    setError("");
    try {
      const result: ListImagesResult = await hostClient.listLibraryImages({
        limit: 10000,
        group_names: selectedGroups.length ? selectedGroups : undefined,
        ...(selectedSubgroups.length === 1
          ? { subgroup_name: selectedSubgroups[0] }
          : selectedSubgroups.length > 1
            ? { subgroup_names: selectedSubgroups }
            : {}),
        tags: selectedTags.length ? selectedTags : undefined,
        input_formats: selectedFormats.length ? selectedFormats : undefined,
        filename_pattern: pattern.trim() ? pattern.trim() : undefined,
      });
      setImages(result.images);
      setAvailable(result.available);
      setPage(0);
      setSelectedIndex(0);
      setPreview(null);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (!ready && !error) {
    return <p data-testid="library-search-status">Loading library…</p>;
  }
  if (!ready && error) {
    return <p role="alert">{error}</p>;
  }
  if (available === false) {
    return (
      <div data-testid="library-search" className="flex min-h-0 flex-1 flex-col gap-2 p-4">
        <h2>Image Search</h2>
        <p data-testid="library-search-unavailable">
          The library store is not attached yet. It arrives with the daemon lease.
        </p>
      </div>
    );
  }

  const openPreview = async (index: number) => {
    const image = images[index];
    if (!image) return;
    setSelectedIndex(index);
    const described = await hostClient.libraryPreviewDescribe({ paths: [image.file_path] });
    const frame = await hostClient.libraryPreviewFrame({ path: image.file_path });
    const item = described.items[0];
    setPreview({
      path: image.file_path,
      width: item ? item.width : 0,
      height: item ? item.height : 0,
      error: (item && item.error) || frame.error,
      png: frame.png_base64,
    });
  };

  const moveSelection = (delta: number) => {
    if (images.length === 0) return;
    const next = Math.min(images.length - 1, Math.max(0, selectedIndex + delta));
    setSelectedIndex(next);
    if (preview) {
      void openPreview(next);
    }
  };

  const pageCount = Math.max(1, Math.ceil(images.length / PAGE_SIZE));
  const pageImages = sortedImages(images, sortKey, sortOrder).slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const selected = images[selectedIndex];

  return (
    <div data-testid="library-search" className="flex min-h-0 flex-1 flex-col gap-3 p-4">
      {error ? (
        <p role="alert" className="self-start rounded border border-it-border bg-it-surface px-2 py-1 text-sm">
          {error}
        </p>
      ) : null}

      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={pattern}
            onChange={(event) => setPattern(event.target.value)}
            placeholder="filename contains…"
            aria-label="filename filter"
            className="w-64 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded border border-it-border px-3 py-1 text-it-text disabled:opacity-50"
          >
            {busy ? "Searching…" : "Search"}
          </button>
          <button type="button" onClick={() => void loadFilters().catch((err: unknown) => setError(String(err)))}>
            Refresh
          </button>
          <span className="text-sm text-it-muted-text" data-testid="library-search-count">
            {images.length} image{images.length === 1 ? "" : "s"}
          </span>
        </div>

        <div className="flex flex-wrap gap-1" data-testid="library-search-groups">
          {groups.map((group) => (
            <button
              key={group.name}
              type="button"
              onClick={() => toggleGroup(group.name)}
              aria-pressed={selectedGroups.includes(group.name)}
              className={`rounded-full px-2 py-0.5 text-xs ${
                selectedGroups.includes(group.name)
                  ? "bg-it-accent text-it-window-bg"
                  : "border border-it-border text-it-text"
              }`}
            >
              {group.name}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-1" data-testid="library-search-subgroups">
          {visibleSubgroups.map((subgroup) => (
            <button
              key={subgroup}
              type="button"
              onClick={() => toggle(subgroup, selectedSubgroups, setSelectedSubgroups)}
              aria-pressed={selectedSubgroups.includes(subgroup)}
              className={`rounded-full px-2 py-0.5 text-xs ${
                selectedSubgroups.includes(subgroup)
                  ? "bg-it-accent text-it-window-bg"
                  : "border border-it-border text-it-text"
              }`}
            >
              {subgroup}
            </button>
          ))}
        </div>

        {catalogTags ? (
          <div className="flex flex-wrap gap-2" data-testid="library-search-categories">
            {distinctCategories(catalogTags).map((category) => (
              <label key={category} className="flex items-center gap-1 text-xs text-it-text">
                <input
                  type="checkbox"
                  checked={!uncheckedCategories.includes(category)}
                  aria-label={categoryLabel(category)}
                  onChange={(event) => setCategoryChecked(category, event.target.checked)}
                />
                {categoryLabel(category)}
              </label>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-1" data-testid="library-search-tags">
          {tags.filter((tag) => categoryAllows(tag, catalogTags, uncheckedCategories)).map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => toggle(tag, selectedTags, setSelectedTags)}
              aria-pressed={selectedTags.includes(tag)}
              className={`rounded-full px-2 py-0.5 text-xs ${
                selectedTags.includes(tag) ? "bg-it-accent text-it-window-bg" : "border border-it-border text-it-text"
              }`}
            >
              {tag}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-1" data-testid="library-search-formats">
          {FORMATS.map((format) => (
            <button
              key={format}
              type="button"
              onClick={() => toggle(format, selectedFormats, setSelectedFormats)}
              aria-pressed={selectedFormats.includes(format)}
              className={`rounded-full px-2 py-0.5 text-xs ${
                selectedFormats.includes(format)
                  ? "bg-it-accent text-it-window-bg"
                  : "border border-it-border text-it-text"
              }`}
            >
              {format}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setSelectedFormats([...FORMATS])}
            className="rounded-full border border-it-border px-2 py-0.5 text-xs text-it-text"
          >
            Add all formats
          </button>
          <button
            type="button"
            onClick={() => setSelectedFormats([])}
            className="rounded-full border border-it-border px-2 py-0.5 text-xs text-it-text"
          >
            Remove all formats
          </button>
        </div>
      </form>

      {searched ? (
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              data-testid="library-search-preview-open"
              disabled={!selected}
              onClick={() => void openPreview(selectedIndex)}
            >
              Preview
            </button>
            <button
              type="button"
              disabled={!selected}
              onClick={() => setPropertiesOpen((open) => !open)}
            >
              Properties
            </button>
            <button
              type="button"
              data-testid="library-search-prev"
              disabled={selectedIndex <= 0}
              onClick={() => moveSelection(-1)}
            >
              Previous result
            </button>
            <button
              type="button"
              data-testid="library-search-next"
              disabled={selectedIndex >= images.length - 1}
              onClick={() => moveSelection(1)}
            >
              Next result
            </button>
            <span data-testid="library-search-selected">
              {selected ? `Selected: ${selected.filename}` : "None selected"}
            </span>
          </div>
          {propertiesOpen && selected ? (
            <dl data-testid="library-search-properties" className="text-sm">
              {presentProperties(selected).map((row) => (
                <div key={row.label}>
                  <dt className="inline">{row.label}</dt> <dd className="inline">{row.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {preview ? (
            <div data-testid="library-search-preview">
              <p>
                {preview.path} {preview.width}x{preview.height}
              </p>
              {preview.error ? <p role="alert">{preview.error}</p> : null}
              {preview.png ? (
                <img alt="Search preview" src={"data:image/png;base64," + preview.png} />
              ) : null}
            </div>
          ) : null}
          {images.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <select
                aria-label="Sort"
                value={sortKey}
                onChange={(event) => {
                  const next = event.target.value;
                  if (!isSortKey(next)) return;
                  setSortKey(next);
                  setPage(0);
                }}
              >
                <option value="returned">As returned</option>
                <option value="filename">Filename</option>
                <option value="date_added">Date added</option>
                <option value="size">Size</option>
              </select>
              <select
                aria-label="Order"
                value={sortOrder}
                onChange={(event) => {
                  const next = event.target.value;
                  if (!isSortOrder(next)) return;
                  setSortOrder(next);
                  setPage(0);
                }}
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </div>
          ) : null}
          <div
            className="min-h-0 flex-1 overflow-y-auto rounded border border-it-border"
            data-testid="library-search-rows"
          >
            {pageImages.map((image) => (
              <div
                key={image.id}
                className="flex items-center justify-between gap-2 border-b border-it-border px-2 py-1 text-sm"
              >
                <LibraryThumb path={image.file_path} hostClient={hostClient} />
                <button
                  type="button"
                  className="truncate text-left"
                  title={image.file_path}
                  aria-pressed={selected?.file_path === image.file_path}
                  onClick={() => setSelectedIndex(images.indexOf(image))}
                >
                  {image.filename}
                </button>
                <span className="shrink-0 text-it-muted-text">
                  {image.group_name ?? "—"}
                  {image.width && image.height ? ` · ${image.width}×${image.height}` : ""}
                  {rowFactSuffix(image)}
                </span>
              </div>
            ))}
            {images.length === 0 ? (
              <p className="p-2 text-it-muted-text">No images match these filters.</p>
            ) : null}
          </div>
          <div className="flex items-center justify-between text-sm">
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage((value) => Math.max(0, value - 1))}
              className="rounded border border-it-border px-2 py-0.5 disabled:opacity-50"
            >
              Previous
            </button>
            <span data-testid="library-search-page">
              Page {page + 1} of {pageCount}
            </span>
            <button
              type="button"
              disabled={page >= pageCount - 1}
              onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}
              className="rounded border border-it-border px-2 py-0.5 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
