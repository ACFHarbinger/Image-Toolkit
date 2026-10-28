import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type {
  ListGroupsResult,
  ListImagesResult,
  ListTagsResult,
} from "../../../../contracts/generated/ts";
import { ImageSearch } from "./ImageSearch";

afterEach(() => cleanup());

const images = [
  {
    id: 1,
    file_path: "/pics/a.png",
    filename: "a.png",
    group_name: "Trips",
    tags: ["night"],
  },
  {
    id: 2,
    file_path: "/pics/b.jpg",
    filename: "b.jpg",
    group_name: "Studio",
    tags: [],
  },
];

function stubClient(available = true) {
  return {
    listLibraryGroups: vi.fn(
      async (): Promise<ListGroupsResult> => ({
        available,
        groups: [
          { name: "Studio", subgroups: [] },
          { name: "Trips", subgroups: [] },
        ],
      }),
    ),
    listLibraryTags: vi.fn(
      async (): Promise<ListTagsResult> => ({ available, tags: ["night", "sunset"] }),
    ),
    listLibraryImages: vi.fn(
      async (params: Record<string, unknown> = {}): Promise<ListImagesResult> => {
        const formats = (params.input_formats as string[] | undefined) ?? [];
        const wanted = (params.group_names as string[] | undefined) ?? [];
        let rows = images;
        if (formats.length) {
          rows = rows.filter((image) => formats.includes(image.filename.split(".").pop() ?? ""));
        }
        if (wanted.length) {
          rows = rows.filter((image) => wanted.includes(image.group_name ?? ""));
        }
        return { available, images: rows };
      },
    ),
  };
}

test("loads filter options and searches over list_images on submit", async () => {
  const client = stubClient();
  render(<ImageSearch hostClient={client as never} />);

  expect(await screen.findByTestId("library-search")).toBeInTheDocument();
  // No search fired until the user submits the form.
  expect(client.listLibraryImages).not.toHaveBeenCalled();
  expect(screen.queryByTestId("library-search-rows")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });
  expect(await screen.findByText("a.png")).toBeInTheDocument();
  expect(screen.getByText("b.jpg")).toBeInTheDocument();
  expect(screen.getByTestId("library-search-count")).toHaveTextContent("2 images");
});

test("refresh reloads groups and tags, and every subgroup is offered", async () => {
  const client = stubClient();
  client.listLibraryGroups.mockResolvedValue({
    available: true,
    groups: [{ name: "Trips", subgroups: ["Beach"] }],
  });
  render(<ImageSearch hostClient={client as never} />);
  expect(await screen.findByRole("button", { name: "Beach" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  await waitFor(() => {
    expect(client.listLibraryGroups).toHaveBeenCalledTimes(2);
    expect(client.listLibraryTags).toHaveBeenCalledTimes(2);
  });
  expect(client.listLibraryImages).not.toHaveBeenCalled();
});

test("group, tag and format filters ride the search request", async () => {
  const client = stubClient();
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Trips" }));
  fireEvent.click(screen.getByRole("button", { name: "night" }));
  expect(screen.getByRole("button", { name: "avif" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "png" }));
  fireEvent.click(screen.getByRole("button", { name: "Search" }));

  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({
      limit: 10000,
      group_names: ["Trips"],
      tags: ["night"],
      input_formats: ["png"],
    });
  });
  await waitFor(() => {
    expect(screen.getByTestId("library-search-count")).toHaveTextContent("1 image");
  });
  expect(screen.queryByText("b.jpg")).not.toBeInTheDocument();
});

test("an unavailable store shows the daemon-lease notice", async () => {
  const client = stubClient(false);
  render(<ImageSearch hostClient={client as never} />);

  expect(await screen.findByTestId("library-search-unavailable")).toBeInTheDocument();
  expect(screen.queryByText("a.png")).not.toBeInTheDocument();
});

test("preview describe and frame follow the selected result", async () => {
  const client = stubClient();
  const preview = {
    libraryPreviewDescribe: vi.fn(async (params: { paths: string[] }) => ({
      items: [
        {
          path: params.paths[0],
          exists: true,
          width: 8,
          height: 4,
          animated: false,
          error: "",
        },
      ],
    })),
    libraryPreviewFrame: vi.fn(async (params: { path: string }) => ({
      path: params.path,
      width: 8,
      height: 4,
      png_base64: "aaaa",
      error: "",
    })),
  };
  render(<ImageSearch hostClient={{ ...client, ...preview } as never} />);
  await screen.findByTestId("library-search");
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByText("a.png");

  fireEvent.click(screen.getByTestId("library-search-next"));
  expect(screen.getByTestId("library-search-selected")).toHaveTextContent("b.jpg");
  fireEvent.click(screen.getByTestId("library-search-prev"));
  expect(screen.getByTestId("library-search-selected")).toHaveTextContent("a.png");

  fireEvent.click(screen.getByTestId("library-search-preview-open"));
  expect(await screen.findByTestId("library-search-preview")).toHaveTextContent("/pics/a.png 8x4");
  expect(preview.libraryPreviewDescribe).toHaveBeenCalledWith({ paths: ["/pics/a.png"] });
  expect(preview.libraryPreviewFrame).toHaveBeenCalledWith({ path: "/pics/a.png" });
  expect(screen.getByRole("img", { name: "Search preview" })).toBeInTheDocument();
});

test("the filename pattern rides the request", async () => {
  const client = stubClient();
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.change(screen.getByLabelText("filename filter"), { target: { value: "portrait" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({
      limit: 10000,
      filename_pattern: "portrait",
    });
  });
});

test("add all formats sends every format and remove all formats omits input_formats", async () => {
  const client = stubClient();
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Add all formats" }));
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({
      limit: 10000,
      input_formats: ["png", "jpg", "jpeg", "webp", "avif", "bmp", "tiff", "gif"],
    });
  });

  fireEvent.click(screen.getByRole("button", { name: "Remove all formats" }));
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenLastCalledWith({ limit: 10000 });
  });
});

test("unchecking a tag category hides its tags and drops them from search", async () => {
  const client = stubClient();
  const catalog = {
    libraryAdminCatalog: vi.fn(async () => ({
      available: true,
      groups: [],
      tables: [],
      tags: [
        { name: "night", category: "General" },
        { name: "sunset", category: "Artist" },
      ],
    })),
  };
  render(<ImageSearch hostClient={{ ...client, ...catalog } as never} />);

  expect(await screen.findByRole("button", { name: "night" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "sunset" })).toBeInTheDocument();
  expect(await screen.findByRole("checkbox", { name: "General" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Artist" })).toBeChecked();

  fireEvent.click(screen.getByRole("checkbox", { name: "General" }));
  expect(screen.queryByRole("button", { name: "night" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "sunset" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "sunset" }));
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({
      limit: 10000,
      tags: ["sunset"],
    });
  });
  const payload = client.listLibraryImages.mock.calls[0]?.[0] as { tags?: string[] };
  expect(payload.tags ?? []).not.toContain("night");
});

test("properties panel lists present fields on the selected result and toggles closed", async () => {
  const client = stubClient();
  client.listLibraryImages.mockResolvedValue({
    available: true,
    images: [
      {
        id: 1,
        file_path: "/pics/a.png",
        filename: "a.png",
        file_size: 1200,
        width: 10,
        height: 20,
        date_added: "2020-01-01",
        group_name: "Trips",
        tags: ["night"],
      },
    ],
  });
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });

  fireEvent.click(screen.getByRole("button", { name: "Properties" }));
  const panel = await screen.findByTestId("library-search-properties");
  expect(panel).toHaveTextContent("File size");
  expect(panel).toHaveTextContent("1200");
  expect(panel).toHaveTextContent("Width");
  expect(panel).toHaveTextContent("10");
  expect(panel).toHaveTextContent("Height");
  expect(panel).toHaveTextContent("20");
  expect(panel).toHaveTextContent("Date added");
  expect(panel).toHaveTextContent("2020-01-01");
  expect(panel).toHaveTextContent("Group");
  expect(panel).toHaveTextContent("Trips");
  expect(panel).toHaveTextContent("Tags");
  expect(panel).toHaveTextContent("night");
  expect(panel).not.toHaveTextContent("undefined");
  expect(panel).not.toHaveTextContent("null");

  fireEvent.click(screen.getByRole("button", { name: "Properties" }));
  expect(screen.queryByTestId("library-search-properties")).not.toBeInTheDocument();
});

test("result rows show present file size and date added only", async () => {
  const client = stubClient();
  client.listLibraryImages.mockResolvedValue({
    available: true,
    images: [
      {
        id: 1,
        file_path: "/pics/a.png",
        filename: "a.png",
        file_size: 0,
        date_added: "2020-01-01",
      },
      {
        id: 2,
        file_path: "/pics/b.jpg",
        filename: "b.jpg",
      },
    ],
  });
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });

  const rows = await screen.findByTestId("library-search-rows");
  expect(rows).toHaveTextContent("0 B");
  expect(rows).toHaveTextContent("2020-01-01");

  const rowElements = rows.querySelectorAll(":scope > div");
  const bRow = Array.from(rowElements).find((row) => row.textContent?.includes("b.jpg"));
  expect(bRow).toBeTruthy();
  expect(bRow?.textContent ?? "").not.toContain("undefined");
  expect(bRow?.textContent ?? "").not.toContain("null");

  const filename = screen.getByRole("button", { name: "a.png" });
  expect(filename).toHaveTextContent(/^a\.png$/);
  expect(filename.textContent ?? "").not.toContain("0 B");
  expect(filename.textContent ?? "").not.toContain("2020-01-01");
});

test("sort by filename reorders rows and does not search again", async () => {
  const client = stubClient();
  client.listLibraryImages.mockResolvedValue({
    available: true,
    images: [
      {
        id: 2,
        file_path: "/pics/b.jpg",
        filename: "b.jpg",
      },
      {
        id: 1,
        file_path: "/pics/a.png",
        filename: "a.png",
        date_modified: "2020-02-02",
      },
    ],
  });
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });

  const rows = await screen.findByTestId("library-search-rows");
  const returnedText = rows.textContent ?? "";
  expect(returnedText.indexOf("b.jpg")).toBeGreaterThanOrEqual(0);
  expect(returnedText.indexOf("b.jpg")).toBeLessThan(returnedText.indexOf("a.png"));

  const filename = screen.getByRole("button", { name: "a.png" });
  expect(filename).toHaveTextContent(/^a\.png$/);
  expect(filename.closest("div")?.textContent ?? "").toContain("2020-02-02");

  fireEvent.change(screen.getByRole("combobox", { name: "Sort" }), { target: { value: "filename" } });
  const filenameText = screen.getByTestId("library-search-rows").textContent ?? "";
  expect(filenameText.indexOf("a.png")).toBeGreaterThanOrEqual(0);
  expect(filenameText.indexOf("a.png")).toBeLessThan(filenameText.indexOf("b.jpg"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);

  fireEvent.change(screen.getByRole("combobox", { name: "Order" }), { target: { value: "desc" } });
  const descendingText = screen.getByTestId("library-search-rows").textContent ?? "";
  expect(descendingText.indexOf("b.jpg")).toBeGreaterThanOrEqual(0);
  expect(descendingText.indexOf("b.jpg")).toBeLessThan(descendingText.indexOf("a.png"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
});

test("images per page splits the loaded results without searching again", async () => {
  const client = stubClient();
  client.listLibraryImages.mockResolvedValue({
    available: true,
    images: Array.from({ length: 21 }, (_, index) => {
      const filename = `p${String(index).padStart(2, "0")}.png`;
      return { id: index, file_path: `/pics/${filename}`, filename };
    }),
  });
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });

  expect(screen.getByRole("button", { name: "p00.png" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "p19.png" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "p20.png" })).toBeInTheDocument();

  fireEvent.change(screen.getByRole("combobox", { name: "Images per page" }), {
    target: { value: "20" },
  });
  expect(screen.queryByRole("button", { name: "p20.png" })).not.toBeInTheDocument();
  expect(screen.getByTestId("library-search-page")).toHaveTextContent("Page 1 of 2");
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("button", { name: "p20.png" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "p00.png" })).not.toBeInTheDocument();
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
});

test("sort by extension reorders rows and does not search again", async () => {
  const client = stubClient();
  client.listLibraryImages.mockResolvedValue({
    available: true,
    images: [
      {
        id: 2,
        file_path: "/pics/b.jpg",
        filename: "b.jpg",
      },
      {
        id: 1,
        file_path: "/pics/a.PNG",
        filename: "a.PNG",
      },
    ],
  });
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });
  const payload = client.listLibraryImages.mock.calls[0]?.[0] as Record<string, unknown>;
  expect(payload).not.toHaveProperty("sort");

  fireEvent.change(screen.getByRole("combobox", { name: "Sort" }), { target: { value: "extension" } });
  const extensionText = screen.getByTestId("library-search-rows").textContent ?? "";
  expect(extensionText.indexOf("b.jpg")).toBeGreaterThanOrEqual(0);
  expect(extensionText.indexOf("b.jpg")).toBeLessThan(extensionText.indexOf("a.PNG"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);

  fireEvent.change(screen.getByRole("combobox", { name: "Order" }), { target: { value: "desc" } });
  const descendingText = screen.getByTestId("library-search-rows").textContent ?? "";
  expect(descendingText.indexOf("a.PNG")).toBeGreaterThanOrEqual(0);
  expect(descendingText.indexOf("a.PNG")).toBeLessThan(descendingText.indexOf("b.jpg"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
});

test("sort by date modified keeps missing values last and does not search again", async () => {
  const client = stubClient();
  client.listLibraryImages.mockResolvedValue({
    available: true,
    images: [
      {
        id: 1,
        file_path: "/pics/dated.png",
        filename: "dated.png",
        date_modified: "2020-01-02",
      },
      {
        id: 2,
        file_path: "/pics/bare.png",
        filename: "bare.png",
        date_modified: null,
      },
    ],
  });
  render(<ImageSearch hostClient={client as never} />);
  await screen.findByTestId("library-search");

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });

  fireEvent.change(screen.getByRole("combobox", { name: "Sort" }), { target: { value: "date_modified" } });
  const ascendingText = screen.getByTestId("library-search-rows").textContent ?? "";
  expect(ascendingText.indexOf("dated.png")).toBeGreaterThanOrEqual(0);
  expect(ascendingText.indexOf("dated.png")).toBeLessThan(ascendingText.indexOf("bare.png"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);

  fireEvent.change(screen.getByRole("combobox", { name: "Order" }), { target: { value: "desc" } });
  const descendingText = screen.getByTestId("library-search-rows").textContent ?? "";
  expect(descendingText.indexOf("dated.png")).toBeGreaterThanOrEqual(0);
  expect(descendingText.indexOf("dated.png")).toBeLessThan(descendingText.indexOf("bare.png"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
});
