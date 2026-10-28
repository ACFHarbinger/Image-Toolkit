import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type {
  ListGroupsResult,
  ListImagesResult,
  ListTagsResult,
} from "../../../../contracts/generated/ts";
import { Listings } from "./Listings";

afterEach(() => cleanup());

const groups: ListGroupsResult = {
  available: true,
  groups: [
    { name: "Studio", subgroups: [] },
    { name: "Trips", subgroups: ["Beach"] },
  ],
};

const images = [
  {
    id: 1,
    file_path: "/pics/a.png",
    filename: "a.png",
    group_name: "Trips",
    subgroup_name: "Beach",
    tags: ["night"],
  },
  { id: 2, file_path: "/pics/b.jpg", filename: "b.jpg", group_name: "Studio", tags: [] },
];

function stubClient(available = true) {
  return {
    listLibraryGroups: vi.fn(async (): Promise<ListGroupsResult> => ({
      ...groups,
      available,
    })),
    listLibraryTags: vi.fn(
      async (): Promise<ListTagsResult> => ({ available, tags: ["night", "sunset"] }),
    ),
    libraryAdminCatalog: vi.fn(async () => ({
      available: true,
      groups: [],
      tags: [
        { name: "night", category: "mood" },
        { name: "sunset", category: "" },
      ],
      tables: [],
    })),
    listLibraryImages: vi.fn(
      async (params: Record<string, unknown> = {}): Promise<ListImagesResult> => {
        const wanted = (params.group_names as string[] | undefined) ?? [];
        const selected =
          wanted.length > 0 ? images.filter((image) => wanted.includes(image.group_name ?? "")) : images;
        return { available, images: selected };
      },
    ),
  };
}

test("loads groups and images over the library capability", async () => {
  const client = stubClient();
  render(<Listings hostClient={client as never} />);

  expect(await screen.findByTestId("library-listings")).toBeInTheDocument();
  expect(await screen.findByText("a.png")).toBeInTheDocument();
  expect(screen.getByText("b.jpg")).toBeInTheDocument();
  expect(screen.getByTestId("library-listings-count")).toHaveTextContent("2 images");
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
});

test("group filters narrow the rows through list_images", async () => {
  const client = stubClient();
  render(<Listings hostClient={client as never} />);
  await screen.findByText("a.png");

  fireEvent.click(screen.getByLabelText("group Trips"));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000, group_names: ["Trips"] });
  });
  await waitFor(() => {
    expect(screen.getByTestId("library-listings-count")).toHaveTextContent("1 image");
  });
  expect(screen.queryByText("b.jpg")).not.toBeInTheDocument();

  fireEvent.click(screen.getByLabelText("group Trips"));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });
});

test("an unavailable store shows the daemon-lease notice and no rows", async () => {
  const client = stubClient(false);
  render(<Listings hostClient={client as never} />);

  expect(await screen.findByTestId("library-listings-unavailable")).toBeInTheDocument();
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  });
  expect(screen.queryByText("a.png")).not.toBeInTheDocument();
});

test("edits image metadata and deletes a group through the store methods", async () => {
  const client = stubClient();
  const extra = {
    scanSaveMetadata: vi.fn(async () => ({
      saved_count: 1,
      success: true,
      database_available: true,
      errors: [],
    })),
    libraryAdminMutate: vi.fn(async () => ({ available: true, applied: 1, error: "" })),
    libraryPreviewDescribe: vi.fn(async () => ({
      items: [{ path: "/pics/a.png", exists: true, width: 3, height: 2, animated: false, error: "" }],
    })),
    libraryPreviewFrame: vi.fn(async () => ({
      path: "/pics/a.png",
      width: 3,
      height: 2,
      png_base64: "bbbb",
      error: "",
    })),
  };
  render(<Listings hostClient={{ ...client, ...extra } as never} />);
  await screen.findByText("a.png");

  fireEvent.change(screen.getByTestId("library-listings-kind"), { target: { value: "image" } });
  fireEvent.change(screen.getByLabelText("image to edit"), { target: { value: "/pics/a.png" } });
  fireEvent.change(screen.getByLabelText("image group"), { target: { value: "Studio" } });
  fireEvent.click(screen.getByTestId("library-listings-save"));
  await waitFor(() => {
    expect(extra.scanSaveMetadata).toHaveBeenCalledWith({
      items: [
        {
          path: "/pics/a.png",
          tags: ["night"],
          group_name: "Studio",
          subgroup_name: "Beach",
        },
      ],
    });
  });

  fireEvent.click(screen.getByTestId("library-listings-preview"));
  expect(await screen.findByTestId("library-listings-preview-pane")).toHaveTextContent("/pics/a.png 3x2");

  fireEvent.change(screen.getByTestId("library-listings-kind"), { target: { value: "group" } });
  fireEvent.change(screen.getByLabelText("group to edit"), { target: { value: "Trips" } });
  fireEvent.click(screen.getByTestId("library-listings-delete"));
  await waitFor(() => {
    expect(extra.libraryAdminMutate).toHaveBeenCalledWith({ action: "remove_group", name: "Trips" });
  });
});

test("renaming a tag does not send update_tag when the category is untouched", async () => {
  const client = stubClient();
  const extra = {
    libraryAdminMutate: vi.fn(async () => ({ available: true, applied: 1, error: "" })),
  };
  render(<Listings hostClient={{ ...client, ...extra } as never} />);
  await screen.findByText("a.png");

  fireEvent.change(screen.getByTestId("library-listings-kind"), { target: { value: "tag" } });
  fireEvent.change(screen.getByLabelText("tag to edit"), { target: { value: "night" } });
  expect(screen.getByLabelText("tag category")).toHaveValue("mood");
  fireEvent.change(screen.getByLabelText("record name"), { target: { value: "evening" } });
  fireEvent.click(screen.getByTestId("library-listings-save"));
  await waitFor(() => {
    expect(extra.libraryAdminMutate).toHaveBeenCalledTimes(1);
  });
  expect(extra.libraryAdminMutate).toHaveBeenCalledWith({
    action: "rename_tag",
    name: "night",
    destination: "evening",
  });
  expect(extra.libraryAdminMutate).not.toHaveBeenCalledWith(expect.objectContaining({ action: "update_tag" }));
});

test("clearing a loaded category sends an empty update and a loaded category does not", async () => {
  const client = stubClient();
  const extra = {
    libraryAdminMutate: vi.fn(async () => ({ available: true, applied: 1, error: "" })),
  };
  render(<Listings hostClient={{ ...client, ...extra } as never} />);
  await screen.findByText("a.png");

  fireEvent.change(screen.getByTestId("library-listings-kind"), { target: { value: "tag" } });
  fireEvent.change(screen.getByLabelText("tag to edit"), { target: { value: "night" } });
  expect(screen.getByLabelText("tag category")).toHaveValue("mood");
  fireEvent.click(screen.getByTestId("library-listings-save"));
  expect(await screen.findByTestId("library-listings-notice")).toHaveTextContent("No changes.");
  expect(extra.libraryAdminMutate).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("tag category"), { target: { value: "" } });
  fireEvent.click(screen.getByTestId("library-listings-save"));
  await waitFor(() => {
    expect(extra.libraryAdminMutate).toHaveBeenCalledTimes(1);
  });
  expect(extra.libraryAdminMutate).toHaveBeenCalledWith({
    action: "update_tag",
    name: "night",
    category: "",
  });
});

test("tag filters and pagination are client-side over the returned rows", async () => {
  const client = stubClient();
  render(<Listings hostClient={client as never} />);
  await screen.findByText("a.png");

  fireEvent.click(screen.getByRole("button", { name: "night" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000, tags: ["night"] });
  });
  expect(screen.getByTestId("library-listings-page")).toHaveTextContent("Page 1 of 1");
});

test("image rows show present file size and date added only", async () => {
  const client = stubClient();
  client.listLibraryImages = vi.fn(async (): Promise<ListImagesResult> => ({
    available: true,
    images: [
      {
        id: 1,
        file_path: "/pics/a.png",
        filename: "a.png",
        file_size: 1200,
        date_added: "2020-01-01",
      },
      { id: 2, file_path: "/pics/b.jpg", filename: "b.jpg" },
    ],
  }));
  render(<Listings hostClient={client as never} />);

  expect(await screen.findByText("a.png")).toBeInTheDocument();
  const rows = screen.getByTestId("library-listings-rows").children;
  const first = rows[0]?.textContent ?? "";
  const second = rows[1]?.textContent ?? "";
  expect(first).toContain("1200 B");
  expect(first).toContain("2020-01-01");
  expect(second).not.toContain(" B");
  expect(second).not.toContain("undefined");
  expect(second).not.toContain("null");
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
});

test("rows show date modified and tags and can sort by date modified", async () => {
  const client = stubClient();
  client.listLibraryImages = vi.fn(async (): Promise<ListImagesResult> => ({
    available: true,
    images: [
      {
        id: 1,
        file_path: "/pics/a.png",
        filename: "a.png",
        date_modified: "2020-03-03",
        tags: ["night", "dawn"],
      },
      { id: 2, file_path: "/pics/b.jpg", filename: "b.jpg" },
    ],
  }));
  render(<Listings hostClient={client as never} />);

  expect(await screen.findByText("a.png")).toBeInTheDocument();
  const rows = screen.getByTestId("library-listings-rows").children;
  const first = rows[0]?.textContent ?? "";
  const second = rows[1]?.textContent ?? "";
  expect(first).toContain("2020-03-03");
  expect(first).toContain("night, dawn");
  expect(second).not.toContain("undefined");
  expect(second).not.toContain("null");
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  expect(client.listLibraryImages.mock.calls[0]?.[0]).not.toHaveProperty("sort");

  fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "date_modified" } });
  fireEvent.change(screen.getByLabelText("Order"), { target: { value: "desc" } });

  const after = screen.getByTestId("library-listings-rows").children;
  expect(after).toHaveLength(2);
  expect(after[0]?.textContent ?? "").toContain("a.png");
  expect(after[1]?.textContent ?? "").toContain("b.jpg");
  expect(screen.getByText("a.png")).toBeInTheDocument();
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
});

test("extension sort reorders loaded rows and does not send a sort field", async () => {
  const client = stubClient();
  client.listLibraryImages = vi.fn(async (): Promise<ListImagesResult> => ({
    available: true,
    images: [
      { id: 2, file_path: "/pics/b.jpg", filename: "b.jpg" },
      { id: 1, file_path: "/pics/a.PNG", filename: "a.PNG" },
    ],
  }));
  render(<Listings hostClient={client as never} />);

  await screen.findByText("b.jpg");
  const before = screen.getByTestId("library-listings-rows").textContent ?? "";
  expect(before.indexOf("b.jpg")).toBeLessThan(before.indexOf("a.PNG"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  expect(client.listLibraryImages.mock.calls[0]?.[0]).not.toHaveProperty("sort");

  fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "extension" } });

  const ascending = screen.getByTestId("library-listings-rows").textContent ?? "";
  expect(ascending.indexOf("b.jpg")).toBeLessThan(ascending.indexOf("a.PNG"));

  fireEvent.change(screen.getByLabelText("Order"), { target: { value: "desc" } });

  const descending = screen.getByTestId("library-listings-rows").textContent ?? "";
  expect(descending.indexOf("a.PNG")).toBeLessThan(descending.indexOf("b.jpg"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
  expect(client.listLibraryImages.mock.calls[0]?.[0]).not.toHaveProperty("sort");
});

test("filename sort reorders loaded rows and does not send a sort field", async () => {
  const client = stubClient();
  client.listLibraryImages = vi.fn(async (): Promise<ListImagesResult> => ({
    available: true,
    images: [
      { id: 2, file_path: "/pics/b.jpg", filename: "b.jpg" },
      { id: 1, file_path: "/pics/a.png", filename: "a.png" },
    ],
  }));
  render(<Listings hostClient={client as never} />);

  await screen.findByText("b.jpg");
  const before = screen.getByTestId("library-listings-rows").textContent ?? "";
  expect(before.indexOf("b.jpg")).toBeLessThan(before.indexOf("a.png"));

  fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "filename" } });

  const after = screen.getByTestId("library-listings-rows").textContent ?? "";
  expect(after.indexOf("a.png")).toBeLessThan(after.indexOf("b.jpg"));
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
  expect(client.listLibraryImages).toHaveBeenCalledWith({ limit: 10000 });
});

test("images per page slices loaded rows without listing again", async () => {
  const client = stubClient();
  client.listLibraryImages = vi.fn(async (): Promise<ListImagesResult> => ({
    available: true,
    images: Array.from({ length: 21 }, (_, id) => {
      const filename = "p" + String(id).padStart(2, "0") + ".png";
      return { id, file_path: "/pics/" + filename, filename };
    }),
  }));
  render(<Listings hostClient={client as never} />);

  expect(await screen.findByText("p00.png")).toBeInTheDocument();
  expect(screen.getByText("p20.png")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Images per page"), { target: { value: "20" } });

  expect(screen.queryByText("p20.png")).not.toBeInTheDocument();
  expect(screen.getByTestId("library-listings-page")).toHaveTextContent("Page 1 of 2");
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole("button", { name: "Next" }));

  expect(screen.getByText("p20.png")).toBeInTheDocument();
  expect(screen.queryByText("p00.png")).not.toBeInTheDocument();
  expect(client.listLibraryImages).toHaveBeenCalledTimes(1);
  for (const call of client.listLibraryImages.mock.calls) {
    expect(call[0]).toEqual({ limit: 10000 });
    expect(call[0]).not.toHaveProperty("sort");
  }
});

test("refresh searches again with the same cap", async () => {
  const client = stubClient();
  render(<Listings hostClient={client as never} />);
  await screen.findByText("a.png");
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledTimes(2);
  });
  expect(client.listLibraryImages).toHaveBeenLastCalledWith({ limit: 10000 });
});
