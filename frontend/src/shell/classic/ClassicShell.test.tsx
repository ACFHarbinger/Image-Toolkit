import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { frontendEntries } from "../navigation";
import { ClassicShell } from "./ClassicShell";

const entries = frontendEntries();

test("category select and tablists follow the catalog, with stitch under Image Editor", () => {
  const onSelect = vi.fn();
  render(
    <ClassicShell entries={entries} activeId="system.convert" onSelect={onSelect}>
      <div data-testid="view">convert</div>
    </ClassicShell>,
  );
  expect(screen.getByTestId("view")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Convert" })).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByRole("option", { name: "Image Stitching" })).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Image Editor" })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Image Editor" } });
  expect(onSelect).toHaveBeenCalledWith("editor.hybrid");
  cleanup();

  onSelect.mockClear();
  render(
    <ClassicShell entries={entries} activeId="stitch.canvas" onSelect={onSelect}>
      <div>canvas</div>
    </ClassicShell>,
  );
  expect(screen.getByRole("tab", { name: "Image Stitching" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "Canvas" })).toHaveAttribute("data-catalog-id", "stitch.canvas");
  fireEvent.click(screen.getByRole("tab", { name: "Stitch" }));
  expect(onSelect).toHaveBeenCalledWith("stitch.stitch");
});
