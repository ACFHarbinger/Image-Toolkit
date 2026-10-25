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
  expect(client.listLibraryImages).toHaveBeenCalledWith({});
});

test("group filters narrow the rows through list_images", async () => {
  const client = stubClient();
  render(<Listings hostClient={client as never} />);
  await screen.findByText("a.png");

  fireEvent.click(screen.getByLabelText("group Trips"));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ group_names: ["Trips"] });
  });
  await waitFor(() => {
    expect(screen.getByTestId("library-listings-count")).toHaveTextContent("1 image");
  });
  expect(screen.queryByText("b.jpg")).not.toBeInTheDocument();

  fireEvent.click(screen.getByLabelText("group Trips"));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({});
  });
});

test("an unavailable store shows the daemon-lease notice and no rows", async () => {
  const client = stubClient(false);
  render(<Listings hostClient={client as never} />);

  expect(await screen.findByTestId("library-listings-unavailable")).toBeInTheDocument();
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({});
  });
  expect(screen.queryByText("a.png")).not.toBeInTheDocument();
});

test("tag filters and pagination are client-side over the returned rows", async () => {
  const client = stubClient();
  render(<Listings hostClient={client as never} />);
  await screen.findByText("a.png");

  fireEvent.click(screen.getByRole("button", { name: "night" }));
  await waitFor(() => {
    expect(client.listLibraryImages).toHaveBeenCalledWith({ tags: ["night"] });
  });
  expect(screen.getByTestId("library-listings-page")).toHaveTextContent("Page 1 of 1");
});
