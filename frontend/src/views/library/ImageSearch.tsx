// Library Image Search (L-03 / #897): the HostClient-driven search page for
// `library.search`, riding the library capability from L-02 (#896). It
// replaces the legacy Rust-invoke SearchTab mapping; `search_files` /
// `get_all_tags` / `get_all_groups` in db.rs are the surfaces it stops
// calling (L-07 #901 retires them). The store reader arrives with the
// daemon lease; until then the results stay `available: false` and the
// view shows its unavailable notice.

import React, { useEffect, useState } from "react";
import type {
  GroupRecord,
  ImageRecord,
  ListGroupsResult,
  ListImagesResult,
  ListTagsResult,
} from "../../../../contracts/generated/ts";
import type { HostClient } from "../../hostclient";

export interface ImageSearchProps {
  hostClient: HostClient;
}

const FORMATS = ["png", "jpg", "jpeg", "webp", "avif", "bmp", "tiff", "gif"] as const;
const PAGE_SIZE = 100;

export function ImageSearch({ hostClient }: ImageSearchProps) {
  const [groups, setGroups] = useState<GroupRecord[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [selectedSubgroups, setSelectedSubgroups] = useState<string[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedFormats, setSelectedFormats] = useState<string[]>([]);
  const [pattern, setPattern] = useState("");
  const [images, setImages] = useState<ImageRecord[]>([]);
  const [available, setAvailable] = useState<boolean | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [searched, setSearched] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [preview, setPreview] = useState<{
    path: string;
    width: number;
    height: number;
    error: string;
    png: string;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [groupsResult, tagsResult]: [ListGroupsResult, ListTagsResult] = await Promise.all([
          hostClient.listLibraryGroups(),
          hostClient.listLibraryTags(),
        ]);
        if (cancelled) return;
        setGroups(groupsResult.groups);
        setTags(groupsResult.available ? tagsResult.tags : []);
        setAvailable(groupsResult.available);
        setReady(true);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    };
    void load();
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
      if (!selected.has(group.name)) continue;
      for (const subgroup of group.subgroups) {
        if (seen.has(subgroup)) continue;
        seen.add(subgroup);
        names.push(subgroup);
      }
    }
    return names;
  };

  const visibleSubgroups = subgroupsFor(selectedGroups);

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
  const pageImages = images.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
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

        <div className="flex flex-wrap gap-1" data-testid="library-search-tags">
          {tags.map((tag) => (
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
          <div
            className="min-h-0 flex-1 overflow-y-auto rounded border border-it-border"
            data-testid="library-search-rows"
          >
            {pageImages.map((image) => (
              <div
                key={image.id}
                className="flex items-center justify-between gap-2 border-b border-it-border px-2 py-1 text-sm"
              >
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
