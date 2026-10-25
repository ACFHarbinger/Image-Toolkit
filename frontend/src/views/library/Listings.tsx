// Library Listings (L-02 / #896): groups + subgroups in a sidebar, tag and
// filename filters, and the image rows over `library.list_images`.
// The store reader arrives with the daemon lease; until then the results
// stay `available: false` and the view shows its unavailable notice.
// Thumbnails are L-01's surface (asset:// viewers, #895); this view lists.

import React, { useCallback, useEffect, useState } from "react";
import type {
  GroupRecord,
  ImageRecord,
  ListGroupsResult,
  ListImagesResult,
  ListTagsResult,
} from "../../../../contracts/generated/ts";
import type { HostClient } from "../../hostclient";

export interface ListingsProps {
  hostClient: HostClient;
}

const PAGE_SIZE = 100;

export function Listings({ hostClient }: ListingsProps) {
  const [groups, setGroups] = useState<GroupRecord[] | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [selectedSubgroup, setSelectedSubgroup] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [pattern, setPattern] = useState("");
  const [images, setImages] = useState<ImageRecord[]>([]);
  const [rowsAvailable, setRowsAvailable] = useState<boolean | null>(null);
  const [page, setPage] = useState(0);
  // `ready` flips once, when the initial groups/tags load answers; the
  // search effect keys off it, so a search never re-triggers itself.
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const available = ready && rowsAvailable !== false;

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
        setRowsAvailable(groupsResult.available);
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

  const search = useCallback(async () => {
    setBusy(true);
    try {
      const result: ListImagesResult = await hostClient.listLibraryImages({
        group_names: selectedGroups.length ? selectedGroups : undefined,
        subgroup_name: selectedSubgroup ?? undefined,
        tags: selectedTags.length ? selectedTags : undefined,
        filename_pattern: pattern.trim() ? pattern.trim() : undefined,
      });
      setImages(result.images);
      setRowsAvailable(result.available);
      setPage(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [hostClient, selectedGroups, selectedSubgroup, selectedTags, pattern]);

  useEffect(() => {
    if (ready) {
      void search();
    }
  }, [ready, search]);

  const toggleGroup = (name: string) => {
    setSelectedSubgroup(null);
    setSelectedGroups((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  };

  const toggleTag = (name: string) => {
    setSelectedTags((current) =>
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name],
    );
  };

  if (!ready && !error) {
    return <p data-testid="library-listings-status">Loading library…</p>;
  }
  if (error && !ready) {
    return <p role="alert">{error}</p>;
  }
  if (!available) {
    return (
      <div data-testid="library-listings" className="flex min-h-0 flex-1 flex-col gap-2 p-4">
        <h2>Listings</h2>
        <p data-testid="library-listings-unavailable">
          The library store is not attached yet. It arrives with the daemon lease.
        </p>
      </div>
    );
  }

  const pageCount = Math.max(1, Math.ceil(images.length / PAGE_SIZE));
  const pageImages = images.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const visibleSubgroups = (groups ?? []).find((group) => selectedGroups.length === 1 && group.name === selectedGroups[0]);

  return (
    <div data-testid="library-listings" className="flex min-h-0 flex-1 gap-4 p-4">
      {error ? (
        <p role="alert" className="self-start rounded border border-it-border bg-it-surface px-2 py-1 text-sm">
          {error}
        </p>
      ) : null}
      <aside className="w-56 shrink-0 overflow-y-auto" data-testid="library-listings-groups">
        <h3 className="mb-2 text-sm text-it-muted-text">Groups</h3>
        {(groups ?? []).map((group) => (
          <div key={group.name} className="mb-1">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selectedGroups.includes(group.name)}
                onChange={() => toggleGroup(group.name)}
                aria-label={`group ${group.name}`}
              />
              <span>{group.name}</span>
            </label>
            {visibleSubgroups?.name === group.name && group.subgroups.length > 0 ? (
              <div className="ml-6">
                {group.subgroups.map((subgroup) => (
                  <button
                    key={subgroup}
                    type="button"
                    onClick={() => setSelectedSubgroup(subgroup === selectedSubgroup ? null : subgroup)}
                    className={`block rounded px-2 py-0.5 text-left text-sm ${
                      subgroup === selectedSubgroup ? "bg-it-accent text-it-window-bg" : "hover:bg-it-surface"
                    }`}
                    aria-pressed={subgroup === selectedSubgroup}
                  >
                    {subgroup}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </aside>

      <section className="flex min-h-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={pattern}
            onChange={(event) => setPattern(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void search();
            }}
            placeholder="filename contains…"
            aria-label="filename filter"
            className="w-56 rounded border border-it-border bg-it-window-bg px-2 py-1 text-it-text"
          />
          <button
            type="button"
            onClick={() => void search()}
            className="rounded border border-it-border px-3 py-1 text-it-text"
          >
            Search
          </button>
          <span className="text-sm text-it-muted-text" data-testid="library-listings-count">
            {images.length} image{images.length === 1 ? "" : "s"}
          </span>
        </div>

        <div className="flex flex-wrap gap-1" data-testid="library-listings-tags">
          {tags.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => toggleTag(tag)}
              aria-pressed={selectedTags.includes(tag)}
              className={`rounded-full px-2 py-0.5 text-xs ${
                selectedTags.includes(tag) ? "bg-it-accent text-it-window-bg" : "border border-it-border text-it-text"
              }`}
            >
              {tag}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto rounded border border-it-border" data-testid="library-listings-rows">
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
                {image.subgroup_name ? ` / ${image.subgroup_name}` : ""}
                {image.width && image.height ? ` · ${image.width}×${image.height}` : ""}
              </span>
            </div>
          ))}
          {images.length === 0 ? <p className="p-2 text-it-muted-text">No images match these filters.</p> : null}
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
          <span data-testid="library-listings-page">
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
      </section>
    </div>
  );
}
