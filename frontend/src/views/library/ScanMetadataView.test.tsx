import { open } from "@tauri-apps/plugin-dialog";
import * as matchers from "@testing-library/jest-dom/matchers";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { FrameParams, FrameResult } from "../../../../contracts/generated/ts";
import type { HostClient } from "../../hostclient";
import { ScanMetadataView } from "./ScanMetadataView";

expect.extend(matchers);

afterEach(() => cleanup());

function stubClient(overrides: Partial<HostClient> = {}) {
  return {
    scanDirectory: vi.fn(async () => ({
      directory: "/test/photos",
      total_found: 2,
      database_available: true,
      images: [
        {
          path: "/test/photos/a.png",
          filename: "a.png",
          extension: "png",
          size_bytes: 2048,
          width: 800,
          height: 600,
          in_database: true,
          tags: ["art"],
          group_name: "Anime",
          subgroup_name: null,
        },
        {
          path: "/test/photos/b.jpg",
          filename: "b.jpg",
          extension: "jpg",
          size_bytes: 1024,
          width: 400,
          height: 300,
          in_database: false,
          tags: [],
          group_name: null,
          subgroup_name: null,
        },
      ],
    })),
    scanSaveMetadata: vi.fn(async () => ({
      saved_count: 2,
      success: true,
      database_available: true,
    })),
    scanSuggestTags: vi.fn(async () => ({
      suggestions: {
        "/test/photos/a.png": ["anime", "render"],
        "/test/photos/b.jpg": ["scenery"],
      },
    })),
    ...overrides,
  } as unknown as HostClient;
}

test("browse sets the directory without scanning", async () => {
  const client = stubClient();
  vi.mocked(open).mockResolvedValueOnce("/picked/dir");
  render(<ScanMetadataView hostClient={client} showModal={vi.fn()} />);

  fireEvent.click(screen.getByRole("button", { name: "Browse" }));

  await waitFor(() => {
    expect(screen.getByPlaceholderText("/path/to/image/folder")).toHaveValue("/picked/dir");
  });
  expect(client.scanDirectory).not.toHaveBeenCalled();
});

test("shows one preview image for a readable frame", async () => {
  const client = stubClient({
    libraryPreviewFrame: vi.fn(async (params: FrameParams): Promise<FrameResult> => {
      if (params.path === "/test/photos/a.png") {
        return { path: params.path, width: 1, height: 1, png_base64: "QQ==", error: "" };
      }
      return { path: params.path, width: 1, height: 1, png_base64: "", error: "unreadable" };
    }),
  });
  const { container } = render(<ScanMetadataView hostClient={client} showModal={vi.fn()} />);

  fireEvent.change(screen.getByPlaceholderText("/path/to/image/folder"), {
    target: { value: "/test/photos" },
  });
  fireEvent.click(screen.getByRole("button", { name: /scan directory/i }));

  await waitFor(() => {
    expect(screen.getByText("a.png")).toBeInTheDocument();
    expect(screen.getByText("b.jpg")).toBeInTheDocument();
  });
  await waitFor(() => {
    const imgs = container.querySelectorAll("img");
    expect(imgs).toHaveLength(1);
    expect(imgs[0]).toHaveAttribute("src", "data:image/png;base64,QQ==");
  });
});

test("renders scan directory input and executes scan", async () => {
  const client = stubClient();
  const showModal = vi.fn();
  render(<ScanMetadataView hostClient={client} showModal={showModal} />);

  const input = screen.getByPlaceholderText("/path/to/image/folder");
  fireEvent.change(input, { target: { value: "/test/photos" } });

  const scanBtn = screen.getByRole("button", { name: /scan directory/i });
  fireEvent.click(scanBtn);

  await waitFor(() => {
    expect(client.scanDirectory).toHaveBeenCalledWith({
      directory: "/test/photos",
      recursive: false,
      formats: ["webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff"],
      max_results: 50000,
    });
    expect(screen.getByText("a.png")).toBeInTheDocument();
    expect(screen.getByText("b.jpg")).toBeInTheDocument();
  });
});

test("show only in DB filters to in-database rows and yields to new only", async () => {
  const client = stubClient();
  render(<ScanMetadataView hostClient={client} showModal={vi.fn()} />);

  fireEvent.change(screen.getByPlaceholderText("/path/to/image/folder"), {
    target: { value: "/test/photos" },
  });
  fireEvent.click(screen.getByRole("button", { name: /scan directory/i }));

  await waitFor(() => {
    expect(client.scanDirectory).toHaveBeenCalledWith({
      directory: "/test/photos",
      recursive: false,
      formats: ["webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff"],
      max_results: 50000,
    });
    expect(screen.getByText("a.png")).toBeInTheDocument();
    expect(screen.getByText("b.jpg")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("checkbox", { name: "Show only in DB" }));
  expect(screen.getByText("a.png")).toBeInTheDocument();
  expect(screen.queryByText("b.jpg")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("checkbox", { name: "New Only" }));
  expect(screen.getByRole("checkbox", { name: "Show only in DB" })).not.toBeChecked();
  expect(screen.getByText("b.jpg")).toBeInTheDocument();
  expect(screen.queryByText("a.png")).not.toBeInTheDocument();
});

test("toggles image selection and runs tag suggestion", async () => {
  const client = stubClient();
  const showModal = vi.fn();
  render(<ScanMetadataView hostClient={client} showModal={showModal} />);

  fireEvent.change(screen.getByPlaceholderText("/path/to/image/folder"), {
    target: { value: "/test/photos" },
  });
  fireEvent.click(screen.getByRole("button", { name: /scan directory/i }));

  await waitFor(() => {
    expect(screen.getByText("a.png")).toBeInTheDocument();
  });

  // Select a.png
  fireEvent.click(screen.getByText("a.png"));

  const suggestBtn = screen.getByRole("button", { name: /suggest from path/i });
  expect(suggestBtn).not.toBeDisabled();
  fireEvent.click(suggestBtn);

  await waitFor(() => {
    expect(client.scanSuggestTags).toHaveBeenCalledWith({
      paths: ["/test/photos/a.png"],
    });
    expect(screen.getByText("anime")).toBeInTheDocument();
    expect(screen.getByText("render")).toBeInTheDocument();
  });
});

test("saves metadata for selected items", async () => {
  const client = stubClient();
  const showModal = vi.fn();
  render(<ScanMetadataView hostClient={client} showModal={showModal} />);

  fireEvent.change(screen.getByPlaceholderText("/path/to/image/folder"), {
    target: { value: "/test/photos" },
  });
  fireEvent.click(screen.getByRole("button", { name: /scan directory/i }));

  await waitFor(() => {
    expect(screen.getByText("a.png")).toBeInTheDocument();
  });

  // Select All
  fireEvent.click(screen.getByText(/select all/i));

  // Add a manual tag
  const tagInput = screen.getByPlaceholderText("tag name");
  fireEvent.change(tagInput, { target: { value: "cyberpunk" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));

  expect(screen.getByText("cyberpunk")).toBeInTheDocument();

  // Apply to Selected
  const saveBtn = screen.getByRole("button", { name: /apply to selected/i });
  fireEvent.click(saveBtn);

  await waitFor(() => {
    expect(client.scanSaveMetadata).toHaveBeenCalled();
    expect(showModal).toHaveBeenCalledWith(
      expect.stringContaining("Successfully saved metadata for 2 image(s)"),
      "success"
    );
  });
});

test("known tag checkbox writes the catalog name into saved tags", async () => {
  const client = stubClient({
    listLibraryGroups: vi.fn(async () => ({
      available: true,
      groups: [],
    })),
    listLibraryTags: vi.fn(async () => ({
      available: true,
      tags: ["scenery"],
    })),
  });
  render(<ScanMetadataView hostClient={client} showModal={vi.fn()} />);

  fireEvent.change(screen.getByPlaceholderText("/path/to/image/folder"), {
    target: { value: "/test/photos" },
  });
  fireEvent.click(screen.getByRole("button", { name: /scan directory/i }));

  await waitFor(() => {
    expect(screen.getByText("a.png")).toBeInTheDocument();
  });
  fireEvent.click(screen.getByText("a.png"));

  const scenery = screen.getByRole("checkbox", { name: "Tag scenery" });
  expect(scenery).not.toBeChecked();
  fireEvent.click(scenery);
  expect(scenery).toBeChecked();

  fireEvent.click(screen.getByRole("button", { name: /apply to selected/i }));

  await waitFor(() => {
    expect(client.scanSaveMetadata).toHaveBeenCalledWith({
      items: [
        {
          path: "/test/photos/a.png",
          tags: ["scenery"],
          group_name: null,
          subgroup_name: null,
        },
      ],
    });
  });

  fireEvent.click(screen.getByRole("checkbox", { name: "Tag scenery" }));
  expect(screen.getByRole("checkbox", { name: "Tag scenery" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: /apply to selected/i }));

  await waitFor(() => {
    expect(client.scanSaveMetadata).toHaveBeenLastCalledWith({
      items: [
        {
          path: "/test/photos/a.png",
          tags: [],
          group_name: null,
          subgroup_name: null,
        },
      ],
    });
  });
});

test("displays offline database banner when database_available is false", async () => {
  const client = stubClient({
    scanDirectory: vi.fn(async () => ({
      directory: "/test/photos",
      total_found: 1,
      database_available: false,
      images: [
        {
          path: "/test/photos/a.png",
          filename: "a.png",
          extension: "png",
          size_bytes: 2048,
          in_database: false,
        },
      ],
    })),
  });

  render(<ScanMetadataView hostClient={client} />);

  fireEvent.change(screen.getByPlaceholderText("/path/to/image/folder"), {
    target: { value: "/test/photos" },
  });
  fireEvent.click(screen.getByRole("button", { name: /scan directory/i }));

  await waitFor(() => {
    expect(screen.getByText(/No database session is attached/i)).toBeInTheDocument();
    expect(screen.queryByText(/queue/i)).not.toBeInTheDocument();
  });
});

test("offers library catalog names as editable datalist suggestions", async () => {
  const client = stubClient({
    listLibraryGroups: vi.fn(async () => ({
      available: true,
      groups: [{ name: "Anime", subgroups: ["Wallpapers"] }],
    })),
    listLibraryTags: vi.fn(async () => ({
      available: true,
      tags: ["scenery"],
    })),
  });
  const { container } = render(<ScanMetadataView hostClient={client} showModal={vi.fn()} />);

  await waitFor(() => {
    expect(container.querySelector("datalist#scan-group-options option")).toHaveTextContent("Anime");
    expect(container.querySelector("datalist#scan-subgroup-options option")).toHaveTextContent("Wallpapers");
    expect(container.querySelector("datalist#scan-tag-options option")).toHaveTextContent("scenery");
  });
});

test("sorts the scanned file list by name without changing the scan request", async () => {
  const client = stubClient({
    scanDirectory: vi.fn(async () => ({
      directory: "/test/photos",
      total_found: 2,
      database_available: true,
      images: [
        {
          path: "/test/photos/b.jpg",
          filename: "b.jpg",
          extension: "jpg",
          size_bytes: 1024,
          in_database: false,
        },
        {
          path: "/test/photos/a.png",
          filename: "a.png",
          extension: "png",
          size_bytes: 2048,
          in_database: true,
        },
      ],
    })),
  });
  render(<ScanMetadataView hostClient={client} showModal={vi.fn()} />);

  fireEvent.change(screen.getByPlaceholderText("/path/to/image/folder"), {
    target: { value: "/test/photos" },
  });
  fireEvent.click(screen.getByRole("button", { name: /scan directory/i }));

  await waitFor(() => {
    const text = document.body.textContent || "";
    expect(text.indexOf("b.jpg")).toBeLessThan(text.indexOf("a.png"));
  });

  fireEvent.change(screen.getByRole("combobox", { name: "Sort files" }), {
    target: { value: "name" },
  });

  const sorted = document.body.textContent || "";
  expect(sorted.indexOf("a.png")).toBeLessThan(sorted.indexOf("b.jpg"));
  expect(client.scanDirectory).toHaveBeenCalledWith({
    directory: "/test/photos",
    recursive: false,
    formats: ["webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff"],
    max_results: 50000,
  });
});
