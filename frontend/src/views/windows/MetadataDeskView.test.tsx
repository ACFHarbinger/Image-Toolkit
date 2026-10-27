import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MetadataDeskView } from "./MetadataDeskView";

afterEach(() => {
  cleanup();
});

test("describes name and size and shows the reason", async () => {
  const hostClient = {
    metadataDescribe: vi.fn().mockResolvedValue({
      found: true,
      path: "/tmp/note.txt",
      name: "note.txt",
      size: 4,
      suffix: ".txt",
      reason: "metadata is not edited",
    }),
  };
  render(<MetadataDeskView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Path"), { target: { value: "/tmp/note.txt" } });
  fireEvent.click(screen.getByRole("button", { name: "Describe" }));
  expect(await screen.findByText("metadata is not edited")).toBeInTheDocument();
  expect(screen.getByText("note.txt 4 .txt")).toBeInTheDocument();
  expect(hostClient.metadataDescribe).toHaveBeenCalledWith({ path: "/tmp/note.txt" });
});

test("a scanned thumbnail fills the path", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string) => {
    if (command === "scan_files") {
      return ["/pics/a.png"];
    }
    return {};
  });
  const hostClient = { metadataDescribe: vi.fn() };
  render(<MetadataDeskView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Image directory"), { target: { value: "/pics" } });
  fireEvent.click(screen.getByRole("button", { name: "Scan" }));
  fireEvent.click(await screen.findByRole("option", { name: "a.png" }));
  expect(screen.getByLabelText("Path")).toHaveValue("/pics/a.png");
  vi.mocked(invoke).mockReset();
});
