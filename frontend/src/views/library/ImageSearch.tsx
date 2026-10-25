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

const FORMATS = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"] as const;
const PAGE_SIZE = 100;

export function ImageSearch({ hostClient }: ImageSearchProps) {
  const [groups, setGroups] = useState<GroupRecord[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
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

  const search = async () => {
    setBusy(true);
    setError("");
    try {
      const result: ListImagesResult = await hostClient.listLibraryImages({
        group_names: selectedGroups.length ? selectedGroups : undefined,
        tags: selectedTags.length ? selectedTags : undefined,
        input_formats: selectedFormats.length ? selectedFormats : undefined,
        filename_pattern: pattern.trim() ? pattern.trim() : undefined,
      });
      setImages(result.images);
      setAvailable(result.available);
      setPage(0);
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

  const pageCount = Math.max(1, Math.ceil(images.length / PAGE_SIZE));
  const pageImages = images.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

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
              onClick={() => toggle(group.name, selectedGroups, setSelectedGroups)}
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
          <div
            className="min-h-0 flex-1 overflow-y-auto rounded border border-it-border"
            data-testid="library-search-rows"
          >
            {pageImages.map((image) => (
              <div
                key={image.id}
                className="flex items-center justify-between gap-2 border-b border-it-border px-2 py-1 text-sm"
              >
                <span className="truncate" title={image.file_path}>
                  {image.filename}
                </span>
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
