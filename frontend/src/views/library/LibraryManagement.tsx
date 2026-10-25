import { FormEvent, useEffect, useState } from "react";
import type { CatalogResult, MutateAction, MutateParams, MutateResult } from "../../../../contracts/generated/ts";

export interface ManagementClient {
  libraryAdminCatalog(): Promise<CatalogResult>;
  libraryAdminMutate(params: MutateParams): Promise<MutateResult>;
}

const ACTIONS: MutateAction[] = [
  "create_group",
  "create_subgroup",
  "create_tag",
  "remove_group",
  "remove_subgroup",
  "remove_tag",
  "merge_tags",
];

/** Groups, subgroups, and tags. The store stays closed until the lease arrives. */
export function LibraryManagement({ client }: { client: ManagementClient }) {
  const [catalog, setCatalog] = useState<CatalogResult | null>(null);
  const [action, setAction] = useState<MutateAction>("create_group");
  const [name, setName] = useState("");
  const [parent, setParent] = useState("");
  const [category, setCategory] = useState("");
  const [destination, setDestination] = useState("");
  const [notice, setNotice] = useState("");

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
      <ul data-testid="library-management-groups">
        {catalog.groups.map((group) => (
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
          <input
            data-testid="library-management-parent"
            value={parent}
            onChange={(event) => setParent(event.target.value)}
          />
        </label>
        <label>
          Category
          <input
            data-testid="library-management-category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          />
        </label>
        <label>
          Merge into
          <input
            data-testid="library-management-destination"
            value={destination}
            onChange={(event) => setDestination(event.target.value)}
          />
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
    </section>
  );
}
