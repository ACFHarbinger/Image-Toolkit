// Library Listings (L-02 / #896): groups + subgroups in a sidebar, tag and
// filename filters, and the image rows over `library.list_images`.
// The store reader arrives with the daemon lease; until then the results
// stay `available: false` and the view shows its unavailable notice.
// Stills come from library_preview.frame. The asset protocol only serves the render cache.

import React, { useCallback, useEffect, useState } from "react";
import type {
  CatalogResult,
  GroupRecord,
  ImageRecord,
  ListGroupsResult,
  ListImagesResult,
  ListTagsResult,
  MutateParams,
} from "../../../../contracts/generated/ts";
import type { HostClient } from "../../hostclient";
import { LibraryThumb } from "./LibraryThumb";

export interface ListingsProps {
  hostClient: HostClient;
}

const PAGE_SIZE = 100;

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

function categoriesFromCatalog(catalog: CatalogResult | null): Record<string, string> | null {
  if (!catalog) return null;
  const next: Record<string, string> = {};
  for (const tag of catalog.tags) {
    next[tag.name] = tag.category ?? "";
  }
  return next;
}

async function readTagCatalog(hostClient: HostClient): Promise<CatalogResult | null> {
  if (typeof hostClient.libraryAdminCatalog !== "function") {
    return null;
  }
  return hostClient.libraryAdminCatalog();
}

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
  const [sortKey, setSortKey] = useState<SortKey>("returned");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  // `ready` flips once, when the initial groups/tags load answers; the
  // search effect keys off it, so a search never re-triggers itself.
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [kind, setKind] = useState<"group" | "subgroup" | "tag" | "image">("group");
  const [originalName, setOriginalName] = useState("");
  const [editName, setEditName] = useState("");
  const [editParent, setEditParent] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [originalCategory, setOriginalCategory] = useState("");
  const [tagCategories, setTagCategories] = useState<Record<string, string>>({});
  const [selectedPath, setSelectedPath] = useState("");
  const [editGroup, setEditGroup] = useState("");
  const [editSubgroup, setEditSubgroup] = useState("");
  const [editTags, setEditTags] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<{ path: string; width: number; height: number; error: string; png: string } | null>(
    null,
  );
  const available = ready && rowsAvailable !== false;

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [groupsResult, tagsResult, catalog]: [ListGroupsResult, ListTagsResult, CatalogResult | null] =
          await Promise.all([hostClient.listLibraryGroups(), hostClient.listLibraryTags(), readTagCatalog(hostClient)]);
        if (cancelled) return;
        setGroups(groupsResult.groups);
        setTags(groupsResult.available ? tagsResult.tags : []);
        setRowsAvailable(groupsResult.available);
        const categories = categoriesFromCatalog(catalog);
        if (categories) setTagCategories(categories);
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

  const pickImage = (image: ImageRecord) => {
    setKind("image");
    setSelectedPath(image.file_path);
    setEditGroup(image.group_name ?? "");
    setEditSubgroup(image.subgroup_name ?? "");
    setEditTags((image.tags ?? []).join(", "));
    setPreview(null);
  };

  const reloadCatalog = async () => {
    const [groupsResult, tagsResult, catalog]: [ListGroupsResult, ListTagsResult, CatalogResult | null] =
      await Promise.all([hostClient.listLibraryGroups(), hostClient.listLibraryTags(), readTagCatalog(hostClient)]);
    setGroups(groupsResult.groups);
    setTags(groupsResult.available ? tagsResult.tags : []);
    setRowsAvailable(groupsResult.available);
    const categories = categoriesFromCatalog(catalog);
    if (categories) setTagCategories(categories);
  };

  const saveRecord = async () => {
    setNotice("");
    if (kind === "image") {
      if (!selectedPath) {
        setNotice("Choose a record first.");
        return;
      }
      const result = await hostClient.scanSaveMetadata({
        items: [
          {
            path: selectedPath,
            tags: editTags
              .split(",")
              .map((tag) => tag.trim())
              .filter((tag) => tag.length > 0),
            group_name: editGroup.trim() ? editGroup.trim() : null,
            subgroup_name: editSubgroup.trim() ? editSubgroup.trim() : null,
          },
        ],
      });
      if (!result.database_available || !result.success) {
        setNotice((result.errors && result.errors.join("; ")) || "Save failed. The database session is not attached.");
        return;
      }
      setNotice(`Saved ${result.saved_count}`);
      await search();
      return;
    }
    if (!originalName.trim()) {
      setNotice("Choose a record first.");
      return;
    }
    const params: MutateParams[] = [];
    if (kind === "group" && editName.trim() !== originalName) {
      params.push({ action: "rename_group", name: originalName, destination: editName.trim() });
    } else if (kind === "subgroup" && editName.trim() !== originalName) {
      params.push({
        action: "rename_subgroup",
        name: originalName,
        parent: editParent.trim(),
        destination: editName.trim(),
      });
    } else if (kind === "tag") {
      if (editName.trim() !== originalName) {
        params.push({ action: "rename_tag", name: originalName, destination: editName.trim() });
      }
      if (editCategory !== originalCategory) {
        params.push({ action: "update_tag", name: editName.trim(), category: editCategory });
      }
    }
    if (params.length === 0) {
      setNotice("No changes.");
      return;
    }
    for (const paramsItem of params) {
      const result = await hostClient.libraryAdminMutate(paramsItem);
      if (!result.available) {
        setNotice("The library store is not attached.");
        return;
      }
      if (result.error || result.applied === 0) {
        setNotice(result.error || "Save failed.");
        return;
      }
    }
    setOriginalName(editName.trim());
    setOriginalCategory(editCategory);
    setNotice("Saved");
    await reloadCatalog();
    await search();
  };

  const deleteRecord = async () => {
    setNotice("");
    let params: MutateParams | null = null;
    if (kind === "image") {
      if (!selectedPath) {
        setNotice("Choose a record first.");
        return;
      }
      params = { action: "delete_image", name: selectedPath };
    } else if (!originalName.trim()) {
      setNotice("Choose a record first.");
      return;
    } else if (kind === "group") {
      params = { action: "remove_group", name: originalName };
    } else if (kind === "subgroup") {
      params = { action: "remove_subgroup", name: originalName, parent: editParent.trim() };
    } else {
      params = { action: "remove_tag", name: originalName };
    }
    const result = await hostClient.libraryAdminMutate(params);
    if (!result.available) {
      setNotice("The library store is not attached.");
      return;
    }
    if (result.error || result.applied === 0) {
      setNotice(result.error || "Delete failed.");
      return;
    }
    setNotice("Deleted");
    setOriginalName("");
    setEditName("");
    setSelectedPath("");
    await reloadCatalog();
    await search();
  };

  const openPreview = async () => {
    if (!selectedPath) {
      setNotice("Choose a record first.");
      return;
    }
    const described = await hostClient.libraryPreviewDescribe({ paths: [selectedPath] });
    const frame = await hostClient.libraryPreviewFrame({ path: selectedPath });
    const item = described.items[0];
    setPreview({
      path: selectedPath,
      width: item ? item.width : 0,
      height: item ? item.height : 0,
      error: (item && item.error) || frame.error,
      png: frame.png_base64,
    });
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
  const pageImages = sortedImages(images, sortKey, sortOrder).slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
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

        <form
          data-testid="library-listings-editor"
          className="flex flex-col gap-2 rounded border border-it-border p-2"
          onSubmit={(event) => {
            event.preventDefault();
            void saveRecord();
          }}
        >
          <label>
            Record
            <select
              data-testid="library-listings-kind"
              value={kind}
              onChange={(event) => setKind(event.target.value as "group" | "subgroup" | "tag" | "image")}
            >
              <option value="group">Group</option>
              <option value="subgroup">Subgroup</option>
              <option value="tag">Tag</option>
              <option value="image">Image</option>
            </select>
          </label>
          {kind === "group" ? (
            <select
              aria-label="group to edit"
              value={originalName}
              onChange={(event) => {
                setOriginalName(event.target.value);
                setEditName(event.target.value);
              }}
            >
              <option value="">Select a group</option>
              {(groups ?? []).map((group) => (
                <option key={group.name} value={group.name}>
                  {group.name}
                </option>
              ))}
            </select>
          ) : null}
          {kind === "tag" ? (
            <select
              aria-label="tag to edit"
              value={originalName}
              onChange={(event) => {
                const name = event.target.value;
                const category = name ? (tagCategories[name] ?? "") : "";
                setOriginalName(name);
                setEditName(name);
                setEditCategory(category);
                setOriginalCategory(category);
              }}
            >
              <option value="">Select a tag</option>
              {tags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
          ) : null}
          {kind !== "image" ? (
            <input
              data-testid="library-listings-name"
              aria-label="record name"
              value={editName}
              onChange={(event) => setEditName(event.target.value)}
            />
          ) : null}
          {kind === "subgroup" ? (
            <>
              <select
                aria-label="subgroup to edit"
                value={originalName && editParent ? editParent + "\t" + originalName : ""}
                onChange={(event) => {
                  const parts = event.target.value.split("\t");
                  setEditParent(parts[0] ?? "");
                  setOriginalName(parts[1] ?? "");
                  setEditName(parts[1] ?? "");
                }}
              >
                <option value="">Select a subgroup</option>
                {(groups ?? []).flatMap((group) =>
                  group.subgroups.map((subgroup) => (
                    <option key={group.name + "/" + subgroup} value={group.name + "\t" + subgroup}>
                      {group.name} / {subgroup}
                    </option>
                  )),
                )}
              </select>
              <input
                data-testid="library-listings-parent"
                aria-label="parent group"
                value={editParent}
                onChange={(event) => setEditParent(event.target.value)}
              />
            </>
          ) : null}
          {kind === "tag" ? (
            <input
              data-testid="library-listings-category"
              aria-label="tag category"
              value={editCategory}
              onChange={(event) => setEditCategory(event.target.value)}
            />
          ) : null}
          {kind === "image" ? (
            <>
              <select
                aria-label="image to edit"
                value={selectedPath}
                onChange={(event) => {
                  const image = images.find((item) => item.file_path === event.target.value);
                  if (image) pickImage(image);
                }}
              >
                <option value="">Select an image</option>
                {images.map((image) => (
                  <option key={image.id} value={image.file_path}>
                    {image.filename}
                  </option>
                ))}
              </select>
              <input
                data-testid="library-listings-group"
                aria-label="image group"
                value={editGroup}
                onChange={(event) => setEditGroup(event.target.value)}
              />
              <input
                data-testid="library-listings-subgroup"
                aria-label="image subgroup"
                value={editSubgroup}
                onChange={(event) => setEditSubgroup(event.target.value)}
              />
              <input
                data-testid="library-listings-tags-edit"
                aria-label="image tags"
                value={editTags}
                onChange={(event) => setEditTags(event.target.value)}
              />
            </>
          ) : null}
          <div className="flex gap-2">
            <button type="submit" data-testid="library-listings-save">
              Save record
            </button>
            <button type="button" data-testid="library-listings-delete" onClick={() => void deleteRecord()}>
              Delete record
            </button>
            {kind === "image" ? (
              <button type="button" data-testid="library-listings-preview" onClick={() => void openPreview()}>
                Preview
              </button>
            ) : null}
          </div>
          {notice ? (
            <p role="status" data-testid="library-listings-notice">
              {notice}
            </p>
          ) : null}
          {preview ? (
            <div data-testid="library-listings-preview-pane">
              <p>
                {preview.path} {preview.width}x{preview.height}
              </p>
              {preview.error ? <p role="alert">{preview.error}</p> : null}
              {preview.png ? <img alt="Listing preview" src={"data:image/png;base64," + preview.png} /> : null}
            </div>
          ) : null}
        </form>

        <div className="min-h-0 flex-1 overflow-y-auto rounded border border-it-border" data-testid="library-listings-rows">
          {pageImages.map((image) => (
            <div
              key={image.id}
              className="flex items-center justify-between gap-2 border-b border-it-border px-2 py-1 text-sm"
              onClick={() => pickImage(image)}
            >
              <span className="flex min-w-0 items-center gap-2" title={image.file_path}>
                <LibraryThumb path={image.file_path} hostClient={hostClient} />
                <span className="truncate">{image.filename}</span>
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
