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
