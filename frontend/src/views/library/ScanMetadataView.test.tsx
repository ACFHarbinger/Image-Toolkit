import * as matchers from "@testing-library/jest-dom/matchers";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
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
    });
    expect(screen.getByText("a.png")).toBeInTheDocument();
    expect(screen.getByText("b.jpg")).toBeInTheDocument();
  });
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
