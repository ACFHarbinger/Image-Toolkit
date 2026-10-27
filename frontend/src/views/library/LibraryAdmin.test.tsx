import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";
import type { BrowseParams, BrowseResult, CatalogResult, MutateParams, MutateResult } from "../../../../contracts/generated/ts";
import { DataBrowser } from "./DataBrowser";
import { LibraryManagement } from "./LibraryManagement";

beforeEach(() => {
  cleanup();
});

function catalog(available: boolean): CatalogResult {
  return {
    available,
    groups: available ? [{ name: "people", subgroups: ["faces"] }] : [],
    tags: available ? [{ name: "smile", category: "mood" }] : [],
    tables: available ? ["images"] : [],
  };
}

test("management shows the unattached store and applies a create", async () => {
  const calls: MutateParams[] = [];
  let available = false;
  const client = {
    libraryAdminCatalog: async () => catalog(available),
    libraryAdminMutate: async (params: MutateParams): Promise<MutateResult> => {
      calls.push(params);
      available = true;
      return { available: true, applied: 1, error: "" };
    },
  };
  render(<LibraryManagement client={client} />);
  expect(await screen.findByTestId("library-management-unavailable")).toBeTruthy();
  fireEvent.change(screen.getByTestId("library-management-name"), { target: { value: "places" } });
  fireEvent.click(screen.getByTestId("library-management-apply"));
  expect((await screen.findByTestId("library-management-notice")).textContent).toBe("Applied 1");
  expect(screen.getByText("people: faces")).toBeTruthy();
  expect(document.querySelector("#library-management-tag-options option")?.getAttribute("value")).toBe(
    "smile",
  );
  expect(calls[0]).toMatchObject({ action: "create_group", name: "places" });
  expect(screen.queryByTestId("library-management-unavailable")).toBeNull();
});

test("management renames a group and updates a tag", async () => {
  const calls: MutateParams[] = [];
  const client = {
    libraryAdminCatalog: async () => catalog(true),
    libraryAdminMutate: async (params: MutateParams): Promise<MutateResult> => {
      calls.push(params);
      return { available: true, applied: 1, error: "" };
    },
  };
  render(<LibraryManagement client={client} />);
  expect(await screen.findByTestId("library-management-action")).toBeTruthy();
  fireEvent.change(screen.getByTestId("library-management-action"), { target: { value: "rename_group" } });
  fireEvent.change(screen.getByTestId("library-management-name"), { target: { value: "people" } });
  fireEvent.change(screen.getByTestId("library-management-destination"), { target: { value: "folks" } });
  fireEvent.click(screen.getByTestId("library-management-apply"));
  expect((await screen.findByTestId("library-management-notice")).textContent).toBe("Applied 1");
  expect(calls[0]).toMatchObject({ action: "rename_group", name: "people", destination: "folks" });

  fireEvent.change(screen.getByTestId("library-management-action"), { target: { value: "update_tag" } });
  fireEvent.change(screen.getByTestId("library-management-name"), { target: { value: "smile" } });
  fireEvent.change(screen.getByTestId("library-management-category"), { target: { value: "Artist" } });
  fireEvent.click(screen.getByTestId("library-management-apply"));
  expect((await screen.findByText("Applied 1")).textContent).toBe("Applied 1");
  expect(calls[1]).toMatchObject({ action: "update_tag", name: "smile", category: "Artist" });
});

test("the registry lists images, filters them, and refreshes", async () => {
  const calls: Array<{ limit: number }> = [];
  const client = {
    libraryAdminCatalog: async () => catalog(true),
    libraryAdminMutate: async (): Promise<MutateResult> => ({ available: true, applied: 0, error: "" }),
    listLibraryImages: async (params: { limit: number }) => {
      calls.push(params);
      return {
        images: [
          { file_path: "/pics/a.png", group_name: "people", subgroup_name: "faces" },
          { file_path: "/pics/b.png", group_name: "places", subgroup_name: "cities" },
        ],
      };
    },
  };
  render(<LibraryManagement client={client} />);
  expect(await screen.findByText("/pics/a.png people faces")).toBeTruthy();
  expect(screen.getByText("/pics/b.png places cities")).toBeTruthy();
  fireEvent.change(screen.getByRole("textbox", { name: "Registry filter" }), { target: { value: "PEOPLE" } });
  expect(screen.getByText("/pics/a.png people faces")).toBeTruthy();
  expect(screen.queryByText("/pics/b.png places cities")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Refresh registry" }));
  expect(calls).toEqual([{ limit: 10000 }, { limit: 10000 }]);
});

test("the data browser pages by column equality", async () => {
  const calls: BrowseParams[] = [];
  const client = {
    libraryAdminCatalog: async () => ({
      available: true,
      groups: [],
      tags: [],
      tables: ["groups", "images"],
    }),
    libraryAdminBrowse: async (params: BrowseParams): Promise<BrowseResult> => {
      calls.push(params);
      if (!params.table) {
        return { available: false, columns: [], rows: [], row_count: 0, error: "" };
      }
      return {
        available: true,
        columns: ["filename"],
        rows: [{ cells: [params.offset === 0 ? "a.png" : "b.png"] }],
        row_count: 60,
        error: "",
      };
    },
  };
  render(<DataBrowser client={client} />);
  fireEvent.change(screen.getByTestId("library-browser-column"), { target: { value: "filename" } });
  fireEvent.change(screen.getByTestId("library-browser-equals"), { target: { value: "a.png" } });
  fireEvent.click(screen.getByTestId("library-browser-load"));
  expect(await screen.findByText("a.png")).toBeTruthy();
  expect(calls[0]).toMatchObject({ table: "images", column: "filename", equals: "a.png", offset: 0 });
  expect(document.querySelector("#library-browser-columns option")?.getAttribute("value")).toBe("filename");
  fireEvent.click(screen.getByTestId("library-browser-next"));
  expect(await screen.findByText("b.png")).toBeTruthy();
  expect(calls[1].offset).toBe(50);
  expect(screen.getByTestId("library-browser-next")).toBeDisabled();
  expect(screen.getByTestId("library-browser-page").textContent).toBe("Page 2");
});

test("the data browser clears filters and refreshes the catalog", async () => {
  const calls: BrowseParams[] = [];
  let catalogCalls = 0;
  const client = {
    libraryAdminCatalog: async () => {
      catalogCalls += 1;
      return {
        available: true,
        groups: [],
        tags: [],
        tables: ["images"],
      };
    },
    libraryAdminBrowse: async (params: BrowseParams): Promise<BrowseResult> => {
      calls.push(params);
      return {
        available: true,
        columns: ["filename"],
        rows: [{ cells: ["a.png"] }],
        row_count: 1,
        error: "",
      };
    },
  };
  render(<DataBrowser client={client} />);
  fireEvent.change(screen.getByTestId("library-browser-column"), { target: { value: "filename" } });
  fireEvent.change(screen.getByTestId("library-browser-equals"), { target: { value: "a.png" } });
  fireEvent.click(screen.getByTestId("library-browser-load"));
  expect(await screen.findByText("a.png")).toBeTruthy();
  fireEvent.click(screen.getByTestId("library-browser-clear"));
  expect(calls[1]).toMatchObject({ table: "images", column: "", equals: "", offset: 0 });
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  expect(catalogCalls).toBe(2);
});

test("the data browser exports the current page as csv and json", async () => {
  const client = {
    libraryAdminCatalog: async () => ({
      available: true,
      groups: [],
      tags: [],
      tables: ["images"],
    }),
    libraryAdminBrowse: async (): Promise<BrowseResult> => ({
      available: true,
      columns: ["filename"],
      rows: [{ cells: ["a.png"] }],
      row_count: 1,
      error: "",
    }),
  };
  render(<DataBrowser client={client} />);
  fireEvent.click(screen.getByTestId("library-browser-load"));
  expect(await screen.findByText("a.png")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
  const exported = screen.getByTestId("library-browser-export");
  expect(exported.textContent).toContain("filename");
  expect(exported.textContent).toContain("a.png");
  fireEvent.click(screen.getByRole("button", { name: "Export JSON" }));
  expect(exported.textContent).toContain('"filename"');
  expect(exported.textContent).toContain('"a.png"');
});

test("the data browser sorts the current page by a column header", async () => {
  let browseCalls = 0;
  const client = {
    libraryAdminCatalog: async () => ({
      available: true,
      groups: [],
      tags: [],
      tables: ["images"],
    }),
    libraryAdminBrowse: async (): Promise<BrowseResult> => {
      browseCalls += 1;
      return {
        available: true,
        columns: ["filename"],
        rows: [{ cells: ["b.png"] }, { cells: ["a.png"] }],
        row_count: 2,
        error: "",
      };
    },
  };
  render(<DataBrowser client={client} />);
  fireEvent.click(screen.getByTestId("library-browser-load"));
  expect(await screen.findByText("b.png")).toBeTruthy();
  const rowText = () => screen.getAllByTestId("library-browser-row").map((row) => row.textContent);
  fireEvent.click(screen.getByRole("button", { name: "filename" }));
  expect(rowText()).toEqual(["a.png", "b.png"]);
  fireEvent.click(screen.getByRole("button", { name: "filename" }));
  expect(rowText()[0]).toBe("b.png");
  expect(browseCalls).toBe(1);
});
