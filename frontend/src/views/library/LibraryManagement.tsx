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
    const listImages = client.listLibraryImages;
    let cancelled = false;
    listImages({ limit: 10000 }).then((result) => {
      if (!cancelled) {
        setRegistry(result.images);
      }
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
    const result = await client.libraryAdminMutate({
      action,
      name,
      parent,
      category,
      destination,
    });
    setNotice(result.available ? result.error || `Applied ${result.applied}` : "");
    if (result.available && result.error === "") {
      setName("");
      await reload();
    }
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
      <ul data-testid="library-management-groups">
        {catalog.groups
          .filter((group) => groupFilter === "" || group.name === groupFilter)
          .map((group) => (
            <li key={group.name}>
              {group.name}
              {group.subgroups.length > 0 ? `: ${group.subgroups.join(", ")}` : ""}
            </li>
          ))}
      </ul>
      <ul data-testid="library-management-tags">
        {catalog.tags.map((tag) => (
          <li key={tag.name}>
            {tag.name}
            {tag.category ? ` (${tag.category})` : ""}
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
                return <li key={line}>{line}</li>;
              })}
          </ul>
        </div>
      )}
    </section>
  );
}
