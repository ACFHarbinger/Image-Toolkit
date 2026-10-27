import { open } from "@tauri-apps/plugin-dialog";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { FolderPicker } from "./FolderPicker";
import { JobProgress } from "./JobProgress";
import { ThumbnailGallery } from "./ThumbnailGallery";

test("the folder field edits without a dialog, and Browse uses the plugin when it returns a path", async () => {
  const onChange = vi.fn();
  render(<FolderPicker label="Source" value="/pics" onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Source"), { target: { value: "/other" } });
  expect(onChange).toHaveBeenCalledWith("/other");
  vi.mocked(open).mockResolvedValueOnce("/library");
  fireEvent.click(screen.getByRole("button", { name: "Browse…" }));
  await waitFor(() => expect(onChange).toHaveBeenCalledWith("/library"));
  expect(open).toHaveBeenCalled();
});

test("thumbnails are pressed buttons inside a list", () => {
  const onToggle = vi.fn();
  render(
    <ThumbnailGallery
      items={[
        { id: "a", name: "Alpha", path: "/a.png" },
        { id: "b", name: "Beta", path: "/b.png" },
      ]}
      selectedIds={["b"]}
      onToggle={onToggle}
    />,
  );
  expect(screen.getByRole("list").querySelectorAll('[role="listitem"]')).toHaveLength(2);
  const beta = screen.getByRole("button", { name: "Beta" });
  expect(beta).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Alpha" })).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(beta);
  expect(onToggle).toHaveBeenCalledWith("b");
});

test("progress shows a bar and Cancel only when a handler is set", () => {
  const onCancel = vi.fn();
  const { rerender } = render(<JobProgress label="Convert" done={1} total={4} />);
  expect(screen.getByRole("progressbar", { name: "Convert" })).toHaveAttribute("value", "1");
  expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  rerender(<JobProgress label="Convert" done={1} total={4} onCancel={onCancel} />);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onCancel).toHaveBeenCalledTimes(1);
});
