import { FormEvent, useState } from "react";
import type { BrowseParams, BrowseResult } from "../../../../contracts/generated/ts";

export interface BrowserClient {
  libraryAdminBrowse(params: BrowseParams): Promise<BrowseResult>;
}

const PAGE = 50;

/** Paginated table view. Filters compare one column. No free-form SQL. */
export function DataBrowser({ client }: { client: BrowserClient }) {
  const [table, setTable] = useState("images");
  const [column, setColumn] = useState("");
  const [equals, setEquals] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<BrowseResult | null>(null);

  async function load(nextOffset: number, event?: FormEvent) {
    event?.preventDefault();
    const result = await client.libraryAdminBrowse({
      table,
      limit: PAGE,
      offset: nextOffset,
      column,
      equals,
    });
    setOffset(nextOffset);
    setPage(result);
  }

  return (
    <section data-testid="library-data-browser" className="flex flex-col gap-4 p-4">
      <h2>Data browser</h2>
      <form onSubmit={(event) => void load(0, event)} className="flex flex-wrap gap-2">
        <label>
          Table
          <input
            data-testid="library-browser-table"
            value={table}
            onChange={(event) => setTable(event.target.value)}
          />
        </label>
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
      </form>
      {!page && <p data-testid="library-browser-status">Choose a table.</p>}
      {page && !page.available && (
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
            <button
              type="button"
              data-testid="library-browser-next"
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
