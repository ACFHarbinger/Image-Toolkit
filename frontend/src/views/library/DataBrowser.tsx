import { FormEvent, useCallback, useEffect, useState } from "react";
import type { BrowseParams, BrowseResult, CatalogResult } from "../../../../contracts/generated/ts";

export interface BrowserClient {
  libraryAdminCatalog(): Promise<CatalogResult>;
  libraryAdminBrowse(params: BrowseParams): Promise<BrowseResult>;
}

const PAGE = 50;

/** Paginated table view. Filters compare one column. No free-form SQL. */
export function DataBrowser({ client }: { client: BrowserClient }) {
  const [table, setTable] = useState("images");
  const [tables, setTables] = useState<string[]>([]);
  const [column, setColumn] = useState("");
  const [equals, setEquals] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<BrowseResult | null>(null);
  const [storeAvailable, setStoreAvailable] = useState<boolean | null>(null);
  const [exportText, setExportText] = useState("");

  const applyCatalog = useCallback((result: CatalogResult) => {
    setStoreAvailable(result.available);
    setTables(result.tables);
    setTable((current) =>
      result.tables.length > 0 && !result.tables.includes(current) ? result.tables[0] : current,
    );
  }, []);

  useEffect(() => {
    let cancelled = false;
    client.libraryAdminCatalog().then((result) => {
      if (cancelled) return;
      applyCatalog(result);
    });
    return () => {
      cancelled = true;
    };
  }, [client, applyCatalog]);

  async function browse(nextOffset: number, columnFilter: string, equalsFilter: string) {
    const result = await client.libraryAdminBrowse({
      table,
      limit: PAGE,
      offset: nextOffset,
      column: columnFilter,
      equals: equalsFilter,
    });
    setOffset(nextOffset);
    setPage(result);
  }

  async function load(nextOffset: number, event?: FormEvent) {
    event?.preventDefault();
    setExportText("");
    await browse(nextOffset, column, equals);
  }

  function clearFilters() {
    setColumn("");
    setEquals("");
    setExportText("");
    void browse(0, "", "");
  }

  function quoteCsv(field: string): string {
    return `"${field.split('"').join('""')}"`;
  }

  function showCsv() {
    if (!page) return;
    const lines = [page.columns.map(quoteCsv).join(",")];
    for (const row of page.rows) {
      lines.push(row.cells.map(quoteCsv).join(","));
    }
    setExportText(lines.join("\n"));
  }

  function showJson() {
    if (!page) return;
    const records = page.rows.map((row) => {
      const record: Record<string, string> = {};
      const count = Math.min(page.columns.length, row.cells.length);
      for (let index = 0; index < count; index += 1) {
        record[page.columns[index]] = row.cells[index];
      }
      return record;
    });
    setExportText(JSON.stringify(records, null, 2));
  }

  const exportReady = Boolean(page?.available && page.error === "" && page.columns.length > 0);

  function refreshCatalog() {
    void client.libraryAdminCatalog().then(applyCatalog);
  }

  return (
    <section data-testid="library-data-browser" className="flex flex-col gap-4 p-4">
      <h2>Data browser</h2>
      {storeAvailable === false && (
        <p role="status" data-testid="library-browser-unavailable">
          The library store is not attached.
        </p>
      )}
      <form onSubmit={(event) => void load(0, event)} className="flex flex-wrap gap-2">
        <label>
          Table
          <select
            data-testid="library-browser-table"
            value={table}
            onChange={(event) => setTable(event.target.value)}
          >
            {(tables.length > 0 ? tables : [table]).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={refreshCatalog}>
          Refresh
        </button>
        <label>
          Column
          <input
            data-testid="library-browser-column"
            value={column}
            onChange={(event) => setColumn(event.target.value)}
          />
        </label>
        <label>
          Equals
          <input
            data-testid="library-browser-equals"
            value={equals}
            onChange={(event) => setEquals(event.target.value)}
          />
        </label>
        <button type="submit" data-testid="library-browser-load">
          Load
        </button>
        <button type="button" data-testid="library-browser-clear" onClick={clearFilters}>
          Clear
        </button>
        <button type="button" disabled={!exportReady} onClick={showCsv}>
          Export CSV
        </button>
        <button type="button" disabled={!exportReady} onClick={showJson}>
          Export JSON
        </button>
      </form>
      <pre data-testid="library-browser-export">{exportText}</pre>
      {!page && <p data-testid="library-browser-status">Choose a table.</p>}
      {page && !page.available && storeAvailable !== false && (
        <p role="status" data-testid="library-browser-unavailable">
          The library store is not attached.
        </p>
      )}
      {page?.error && (
        <p role="alert" data-testid="library-browser-error">
          {page.error}
        </p>
      )}
      {page && page.available && page.error === "" && (
        <>
          <p data-testid="library-browser-count">{page.row_count} row(s)</p>
          <table>
            <thead>
              <tr>
                {page.columns.map((name) => (
                  <th key={name}>{name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.rows.map((row, index) => (
                <tr key={index} data-testid="library-browser-row">
                  {row.cells.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex gap-2">
            <button
              type="button"
              data-testid="library-browser-prev"
              disabled={offset === 0}
              onClick={() => void load(Math.max(0, offset - PAGE))}
            >
              Previous
            </button>
            <span data-testid="library-browser-page">Page {offset / PAGE + 1}</span>
            <button
              type="button"
              data-testid="library-browser-next"
              disabled={offset + PAGE >= page.row_count}
              onClick={() => void load(offset + PAGE)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
