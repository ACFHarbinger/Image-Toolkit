import { FormEvent, useEffect, useState } from "react";
import type { CatalogResult, MutateAction, MutateParams, MutateResult } from "../../../../contracts/generated/ts";

type RegistryImage = {
  file_path: string;
  group_name?: string;
  subgroup_name?: string;
};

export interface ManagementClient {
  libraryAdminCatalog(): Promise<CatalogResult>;
  libraryAdminMutate(params: MutateParams): Promise<MutateResult>;
  listLibraryImages?(params: { limit: number }): Promise<{ images: RegistryImage[] }>;
}

const ACTIONS: MutateAction[] = [
  "create_group",
  "create_subgroup",
  "create_tag",
  "remove_group",
  "remove_subgroup",
  "remove_tag",
  "merge_tags",
  "rename_group",
  "rename_subgroup",
  "rename_tag",
  "update_tag",
];

const TAG_CATEGORIES = ["Artist", "Copyright", "Character", "General", "Meta"];

const SPLIT_CREATE: ReadonlySet<MutateAction> = new Set([
  "create_group",
  "create_subgroup",
  "create_tag",
]);

/** Only the fixed tag categories are selectable. Anything else is "(none)". */
function listedCategory(category: string): string {
  return TAG_CATEGORIES.indexOf(category) === -1 ? "" : category;
}

/** A JSON array of strings, or `{ tags: string[] }`. Non-strings are dropped. */
function namesFromTagJson(text: string): string[] | null {
  const trimmed = text.trim();
  if (trimmed === "") {
    return null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return null;
  }
  let entries: unknown[] | null = null;
  if (Array.isArray(parsed)) {
    entries = parsed;
  } else if (
    parsed !== null &&
    typeof parsed === "object" &&
    "tags" in parsed &&
    Array.isArray(parsed.tags)
  ) {
    entries = parsed.tags;
  }
  if (entries === null) {
    return null;
  }
  const names = entries
    .filter((entry): entry is string => typeof entry === "string")
    .map((entry) => entry.trim())
    .filter((entry) => entry !== "");
  return names.length === 0 ? null : names;
}

/** Copies the file path only. A missing clipboard API or a failed write leaves the row alone. */
function copyRegistryPath(filePath: string): void {
  const clipboard = navigator.clipboard;
  if (typeof clipboard?.writeText !== "function") {
    return;
  }
  try {
    void Promise.resolve(clipboard.writeText(filePath)).catch(() => undefined);
  } catch {
    // A thrown write or a rejected promise must not change the registry.
  }
}

/** Groups, subgroups, and tags. The store stays closed until the lease arrives. */
export function LibraryManagement({ client }: { client: ManagementClient }) {
  const [catalog, setCatalog] = useState<CatalogResult | null>(null);
  const [action, setAction] = useState<MutateAction>("create_group");
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [category, setCategory] = useState("");
  const [destination, setDestination] = useState("");
  const [notice, setNotice] = useState("");
  const [tagJson, setTagJson] = useState("");
  const [registry, setRegistry] = useState<RegistryImage[]>([]);
  const [registryFilter, setRegistryFilter] = useState("");

  async function reload() {
    const next = await client.libraryAdminCatalog();
    setCatalog(next);
  }

  useEffect(() => {
    let cancelled = false;
    client.libraryAdminCatalog().then((next) => {
      if (!cancelled) {
        setCatalog(next);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [client]);

  useEffect(() => {
    if (typeof client.listLibraryImages !== "function") {
      return;
    }
    let cancelled = false;
    client.listLibraryImages({ limit: 10000 }).then((result) => {
      if (!cancelled) {
        setRegistry(result.images);
      }
    }).catch((error: unknown) => {
      if (!cancelled) setNotice(error instanceof Error ? error.message : String(error));
    });
    return () => {
      cancelled = true;
    };
  }, [client]);

  async function refreshRegistry() {
    if (typeof client.listLibraryImages !== "function") {
      return;
    }
    const result = await client.listLibraryImages({ limit: 10000 });
    setRegistry(result.images);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const pieces = SPLIT_CREATE.has(action)
      ? name
          .split(",")
          .map((piece) => piece.trim())
          .filter((piece) => piece !== "")
      : [name];
    if (pieces.length === 0) {
      setNotice("Name is required.");
      return;
    }
    let applied = 0;
    for (const piece of pieces) {
      const result = await client.libraryAdminMutate({
        action,
        name: piece,
        parent,
        category,
        destination,
      });
      if (!result.available) {
        setNotice("");
        return;
      }
      if (result.error !== "") {
        setNotice(result.error);
        return;
      }
      applied += result.applied;
    }
    setNotice(`Applied ${applied}`);
    setName("");
    await reload();
  }

  async function importTags() {
    const names = namesFromTagJson(tagJson);
    if (names === null) {
      setNotice("Tag JSON is not valid.");
      return;
    }
    let applied = 0;
    for (const tagName of names) {
      const result = await client.libraryAdminMutate({
        action: "create_tag",
        name: tagName,
        parent,
        category,
        destination,
      });
      if (!result.available) {
        setNotice("");
        return;
      }
      if (result.error !== "") {
        setNotice(result.error);
        return;
      }
      applied += result.applied;
    }
    setNotice(`Applied ${applied}`);
    setTagJson("");
    await reload();
  }

  if (!catalog) {
    return <p data-testid="library-management-status">Loading the catalog…</p>;
  }

  return (
    <section data-testid="library-management" className="flex flex-col gap-4 p-4">
      <h2>Library management</h2>
      {!catalog.available && (
        <p role="status" data-testid="library-management-unavailable">
          The library store is not attached.
        </p>
      )}
      <label>
        Show group
        <select
          data-testid="library-management-filter"
          value={groupFilter}
          onChange={(event) => setGroupFilter(event.target.value)}
        >
          <option value="">(all)</option>
          {catalog.groups.map((group) => (
            <option key={group.name} value={group.name}>
              {group.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" onClick={() => void reload()}>
        Refresh list
      </button>
      <ul data-testid="library-management-groups">
        {catalog.groups
          .filter((group) => groupFilter === "" || group.name === groupFilter)
          .map((group) => (
            <li key={group.name}>
              <span>
                {group.name}
                {group.subgroups.length > 0 ? `: ${group.subgroups.join(", ")}` : ""}
              </span>
              <button type="button" onClick={() => setName(group.name)}>
                Use group {group.name}
              </button>
              {group.subgroups.map((subgroup) => (
                <button
                  key={subgroup}
                  type="button"
                  onClick={() => {
                    setName(subgroup);
                    setParent(group.name);
                  }}
                >
                  Use subgroup {group.name} {subgroup}
                </button>
              ))}
            </li>
          ))}
      </ul>
      <ul data-testid="library-management-tags">
        {catalog.tags.map((tag) => (
          <li key={tag.name}>
            <span>
              {tag.name}
              {tag.category ? ` (${tag.category})` : ""}
            </span>
            <button
              type="button"
              onClick={() => {
                setName(tag.name);
                setCategory(listedCategory(tag.category));
              }}
            >
              Use tag {tag.name}
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={onSubmit} className="flex flex-col gap-2">
        <label>
          Action
          <select
            data-testid="library-management-action"
            value={action}
            onChange={(event) => setAction(event.target.value as MutateAction)}
          >
            {ACTIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Name
          <input
            data-testid="library-management-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Parent group
          <select
            data-testid="library-management-parent"
            value={parent}
            onChange={(event) => setParent(event.target.value)}
          >
            <option value="">(none)</option>
            {catalog.groups.map((group) => (
              <option key={group.name} value={group.name}>
                {group.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Category
          <select
            data-testid="library-management-category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">(none)</option>
            {TAG_CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Merge into
          <input
            data-testid="library-management-destination"
            value={destination}
            list="library-management-tag-options"
            onChange={(event) => setDestination(event.target.value)}
          />
          <datalist id="library-management-tag-options">
            {catalog.tags.map((tag) => (
              <option key={tag.name} value={tag.name} />
            ))}
          </datalist>
        </label>
        <button type="submit" data-testid="library-management-apply">
          Apply
        </button>
      </form>
      <label>
        Tag JSON
        <textarea value={tagJson} onChange={(event) => setTagJson(event.target.value)} />
      </label>
      <button type="button" onClick={() => void importTags()}>
        Import tags from JSON
      </button>
      {notice && (
        <p role="alert" data-testid="library-management-notice">
          {notice}
        </p>
      )}
      {typeof client.listLibraryImages === "function" && (
        <div className="flex flex-col gap-2">
          <label>
            Registry filter
            <input
              aria-label="Registry filter"
              value={registryFilter}
              onChange={(event) => setRegistryFilter(event.target.value)}
            />
          </label>
          <button type="button" onClick={() => void refreshRegistry()}>
            Refresh registry
          </button>
          <ul data-testid="library-management-registry">
            {registry
              .filter((image) => {
                const needle = registryFilter.trim().toLowerCase();
                if (needle === "") {
                  return true;
                }
                const haystack = [image.file_path, image.group_name ?? "", image.subgroup_name ?? ""]
                  .join(" ")
                  .toLowerCase();
                return haystack.includes(needle);
              })
              .map((image) => {
                const line = [image.file_path, image.group_name ?? "", image.subgroup_name ?? ""]
                  .filter((part) => part !== "")
                  .join(" ");
                return (
                  <li key={line}>
                    <span>{line}</span>
                    <button type="button" onClick={() => copyRegistryPath(image.file_path)}>
                      Copy path {image.file_path}
                    </button>
                  </li>
                );
              })}
          </ul>
        </div>
      )}
    </section>
  );
}
