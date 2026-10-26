import { open } from "@tauri-apps/plugin-dialog";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { CatalogEntry } from "./catalog";
import { CatalogView } from "./views";

const hybridEntry: CatalogEntry = {
  id: "editor.hybrid",
  title: "Hybrid Editor",
  category: "Image Editor",
  kind: "page",
  order_index: 24,
  window_id: "main",
  workspace_id: null,
  route_key: null,
  icon_name: "layers",
  capability_flags: [],
  search_terms: [],
  surfaces: ["frontend"],
  legacy_frontend_id: "hie_editor",
  companion_window_id: null,
};

afterEach(() => {
  cleanup();
  vi.mocked(open).mockReset();
  vi.mocked(open).mockImplementation(() => Promise.resolve(null));
});

test("CatalogView forwards hostClient into the mounted hybrid editor", async () => {
  const hostClient = {
    hieListCapabilities: vi.fn().mockResolvedValue({
      capabilities: ["brush_assistant"],
      models_available: ["birefnet"],
    }),
    hieOpenDocument: vi.fn().mockResolvedValue({
      success: true,
      document_id: "doc-catalog",
      frame_count: 1,
      width: 0,
      height: 0,
      elapsed_seconds: 0,
    }),
  };
  vi.mocked(open).mockResolvedValueOnce("/catalog/photo.png");

  render(
    <CatalogView
      entry={hybridEntry}
      showModal={vi.fn()}
      hostClient={hostClient as never}
    />,
  );

  expect(await screen.findByRole("button", { name: /Open Media/i })).toBeInTheDocument();
  await waitFor(() => {
    expect(hostClient.hieListCapabilities).toHaveBeenCalled();
  });

  fireEvent.click(screen.getByRole("button", { name: /Open Media/i }));
  await waitFor(() => {
    expect(hostClient.hieOpenDocument).toHaveBeenCalledWith(
      expect.objectContaining({ source: "/catalog/photo.png" }),
    );
  });
});
