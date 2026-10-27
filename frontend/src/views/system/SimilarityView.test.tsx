import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SimilarityView } from "./SimilarityView";

afterEach(() => {
  cleanup();
  vi.mocked(invoke).mockReset();
  vi.mocked(invoke).mockImplementation(() => Promise.resolve({}));
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

test("compare lists width, height, and ahash", async () => {
  const hostClient = {
    similarityCompare: vi.fn().mockResolvedValue({
      items: [{ path: "/a.png", width: 8, height: 4, ahash: "abcd", error: "" }],
      pairs: [{ left: "/a.png", right: "/b.png", distance: 0 }],
    }),
  };
  render(<SimilarityView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Images"), { target: { value: "/a.png\n/b.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Compare" }));
  expect(await screen.findByText("/a.png /b.png 0")).toBeInTheDocument();
  expect(screen.getByText("/a.png 8x4 abcd")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /delete/i })).toBeNull();
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

test("left and right scans compare their union", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string, args?: unknown) => {
    if (command !== "scan_files") {
      return {};
    }
    const directory = (args as { directory?: string } | undefined)?.directory;
    if (directory === "/left") {
      return ["/left/a.png", "/shared.png"];
    }
    if (directory === "/right") {
      return ["/shared.png", "/right/b.png"];
    }
    return [];
  });
  const hostClient = {
    similarityCompare: vi.fn().mockResolvedValue({ items: [], pairs: [] }),
  };
  render(<SimilarityView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Left directory"), { target: { value: "/left" } });
  fireEvent.change(screen.getByLabelText("Right directory"), { target: { value: "/right" } });
  const scans = screen.getAllByRole("button", { name: "Scan" });
  fireEvent.click(scans[0]);
  fireEvent.click(scans[1]);
  await waitFor(() => {
    expect(screen.getByLabelText("Images")).toHaveValue("/left/a.png\n/shared.png\n/right/b.png");
  });
  fireEvent.click(screen.getByRole("button", { name: "Compare" }));
  expect(hostClient.similarityCompare).toHaveBeenCalledWith({
    paths: ["/left/a.png", "/shared.png", "/right/b.png"],
    threshold: 8,
  });
});

test("compare shows a still only for a readable preview frame", async () => {
  const hostClient = {
    similarityCompare: vi.fn().mockResolvedValue({
      items: [],
      pairs: [{ left: "/a.png", right: "/b.png", distance: 0 }],
    }),
    libraryPreviewFrame: vi.fn(async (params: { path: string }) => {
      if (params.path === "/a.png") {
        return { png_base64: "QQ==", error: "" };
      }
      return { png_base64: "", error: "unreadable" };
    }),
  };
  render(<SimilarityView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Images"), { target: { value: "/a.png\n/b.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Compare" }));
  expect(await screen.findByText("/a.png /b.png 0")).toBeInTheDocument();
  expect(hostClient.similarityCompare).toHaveBeenCalledWith({ paths: ["/a.png", "/b.png"], threshold: 8 });
  await waitFor(() => {
    expect(document.querySelector("img")?.getAttribute("src")).toBe("data:image/png;base64,QQ==");
  });
  expect(document.querySelectorAll("img").length).toBe(1);
});
