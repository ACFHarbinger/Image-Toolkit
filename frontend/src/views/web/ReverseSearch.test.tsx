import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { EnginesResult, SearchResult } from "../../../../contracts/generated/ts";
import { ReverseSearchView } from "./ReverseSearch";

afterEach(() => cleanup());

const engines: EnginesResult = {
  engines: [
    { id: "google", label: "Google Lens" },
    { id: "tineye", label: "TinEye API" },
    { id: "local_cbir", label: "Local AI Search" },
  ],
};

function stubClient(searchResponse?: Partial<SearchResult>) {
  return {
    reverseSearchEngines: vi.fn(async (): Promise<EnginesResult> => engines),
    reverseSearch: vi.fn(
      async (params: Record<string, unknown>): Promise<SearchResult> => ({
        ok: true,
        engine: String(params.engine),
        results: [
          {
            url: "https://example.com/a",
            engine: String(params.engine),
            score: 0.8123,
            resolution: "1920x1080",
            title: "A match",
          },
        ],
        error: null,
        ...searchResponse,
      }),
    ),
  };
}

test("loads the engine catalog and searches through the capability", async () => {
  const client = stubClient();
  render(<ReverseSearchView hostClient={client as never} />);

  const engine = await screen.findByLabelText("Engine") as HTMLSelectElement;
  expect(engine.value).toBe("google");
  expect(screen.getByTestId("reverse-search-idle")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Image"), { target: { value: "/pics/q.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));

  await waitFor(() => {
    expect(client.reverseSearch).toHaveBeenCalledWith({
      engine: "google",
      image_path: "/pics/q.png",
      limit: 20,
      roi: undefined,
    });
  });
  expect(await screen.findByText("A match")).toBeInTheDocument();
  expect(screen.getByText(/1920x1080 · 81.2%/)).toBeInTheDocument();
});

test("the ROI fields ride the request when four numbers are given", async () => {
  const client = stubClient();
  render(<ReverseSearchView hostClient={client as never} />);
  await screen.findByLabelText("Engine");

  fireEvent.change(screen.getByLabelText("Image"), { target: { value: "/q.png" } });
  fireEvent.change(screen.getByLabelText(/ROI/), { target: { value: "10, 20, 30, 40" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));

  await waitFor(() => {
    expect(client.reverseSearch).toHaveBeenCalledWith({
      engine: "google",
      image_path: "/q.png",
      limit: 20,
      roi: [10, 20, 30, 40],
    });
  });
});

test("an empty image path never calls the engine", async () => {
  const client = stubClient();
  render(<ReverseSearchView hostClient={client as never} />);
  await screen.findByLabelText("Engine");

  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/pick an image/i);
  });
  expect(client.reverseSearch).not.toHaveBeenCalled();
});

test("a failed search surfaces the engine error without inventing results", async () => {
  const client = stubClient({ ok: false, results: [], error: "connection refused" });
  render(<ReverseSearchView hostClient={client as never} />);
  await screen.findByLabelText("Engine");

  fireEvent.change(screen.getByLabelText("Image"), { target: { value: "/q.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent("connection refused");
  });
  expect(screen.getByText(/No matches for this query/i)).toBeInTheDocument();
});
