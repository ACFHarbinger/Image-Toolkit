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
