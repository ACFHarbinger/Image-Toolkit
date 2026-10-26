import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SimilarityView } from "./SimilarityView";

afterEach(() => {
  cleanup();
});

test("compare lists pairs and does not delete", async () => {
  const hostClient = {
    similarityCompare: vi.fn().mockResolvedValue({
      items: [],
      pairs: [{ left: "/a.png", right: "/b.png", distance: 0 }],
    }),
    similarityScan: vi.fn(),
  };
  render(<SimilarityView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Images"), { target: { value: "/a.png\n/b.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Compare" }));
  expect(await screen.findByText("/a.png /b.png 0")).toBeInTheDocument();
  expect(hostClient.similarityCompare).toHaveBeenCalledWith({ paths: ["/a.png", "/b.png"], threshold: 8 });
  expect(hostClient.similarityScan).not.toHaveBeenCalled();
});

test("scan sends the directory and lists pairs", async () => {
  const hostClient = {
    similarityCompare: vi.fn(),
    similarityScan: vi.fn().mockResolvedValue({
      items: [],
      pairs: [{ left: "/dir/a.png", right: "/dir/b.png", distance: 2 }],
    }),
  };
  render(<SimilarityView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Directory"), { target: { value: "/dir" } });
  fireEvent.click(screen.getByRole("button", { name: "Scan directory" }));
  expect(await screen.findByText("/dir/a.png /dir/b.png 2")).toBeInTheDocument();
  expect(hostClient.similarityScan).toHaveBeenCalledWith({ directory: "/dir", threshold: 8 });
  expect(hostClient.similarityCompare).not.toHaveBeenCalled();
});
