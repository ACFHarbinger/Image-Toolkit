import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { EntityReconDescribeResult, EntityReconResolveResult } from "../../../../contracts/generated/ts";
import { EntityReconView } from "./EntityRecon";

afterEach(() => cleanup());

const describe: EntityReconDescribeResult = {
  available: true,
  config: {
    search_scope: "local",
    privacy_mode: true,
    local_match_threshold: 0.55,
    top_k: 5,
    embed_mode: "face",
    reverse_engines: ["google_lens", "yandex", "bing", "saucenao"],
  },
};

const resolved: EntityReconResolveResult = {
  available: true,
  found: true,
  name: "rin tohsaka",
  confidence: 0.91,
  method: "ArcFace -> Local DB",
  origin: "local",
  local_matches: [{ label: "rin tohsaka", path: "/dataset/rin/001.png", score: 0.91 }],
  web_domains: [],
  report: {
    query_hash: "abc123",
    predicted_name: "rin tohsaka",
    confidence: 0.91,
    method: "ArcFace -> Local DB",
    created_at: "2026-10-25T00:00:00+00:00",
    entries: [
      { kind: "local", label: "rin tohsaka", source: "/dataset/rin/001.png", score: 0.91, method: "ArcFace -> Local DB" },
    ],
  },
  error: null,
};

function stubClient(overrides: { described?: Partial<EntityReconDescribeResult>; resolved?: Partial<EntityReconResolveResult> } = {}) {
  return {
    entityReconDescribe: vi.fn(async (): Promise<EntityReconDescribeResult> => ({
      ...describe,
      ...overrides.described,
    })),
    entityReconResolve: vi.fn(
      async (params: Record<string, unknown>): Promise<EntityReconResolveResult> => ({
        ...resolved,
        ...overrides.resolved,
      }),
    ),
  };
}

test("loads the config snapshot and resolves a cutout with provenance", async () => {
  const client = stubClient();
  render(<EntityReconView hostClient={client as never} />);

  expect(await screen.findByTestId("entity-recon")).toBeInTheDocument();
  expect(screen.getByTestId("entity-recon-idle")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Cutout image"), { target: { value: "/cutouts/rin.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Resolve" }));

  await waitFor(() => {
    expect(client.entityReconResolve).toHaveBeenCalledWith({
      image_path: "/cutouts/rin.png",
      search_scope: "local",
      local_match_threshold: 0.55,
      top_k: 5,
    });
  });
  expect(await screen.findByTestId("entity-recon-summary")).toHaveTextContent(/rin tohsaka · 91\.0%/);
  expect(screen.getByTestId("entity-recon-local-matches")).toBeInTheDocument();
  expect(screen.getByTestId("entity-recon-provenance")).toHaveTextContent(/local: rin tohsaka/);
});

test("scope overrides ride the resolve request and warn before web dispatch", async () => {
  const client = stubClient();
  render(<EntityReconView hostClient={client as never} />);
  await screen.findByTestId("entity-recon");

  fireEvent.change(screen.getByLabelText("Scope"), { target: { value: "web" } });
  expect(screen.getByTestId("entity-recon-web-warning")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Cutout image"), { target: { value: "/c.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
  await waitFor(() => {
    expect(client.entityReconResolve).toHaveBeenCalledWith(
      expect.objectContaining({ search_scope: "web" }),
    );
  });
});

test("an unavailable engine disables resolve instead of inventing an identity", async () => {
  const client = stubClient({ described: { available: false } });
  render(<EntityReconView hostClient={client as never} />);

  expect(await screen.findByTestId("entity-recon-unavailable")).toBeInTheDocument();
  const resolve = screen.getByRole("button", { name: "Resolve" }) as HTMLButtonElement;
  expect(resolve.disabled).toBe(true);
  expect(client.entityReconResolve).not.toHaveBeenCalled();
});

test("an empty path never calls the engine, and failed resolves surface the error", async () => {
  const client = stubClient({ resolved: { available: true, found: false, name: "", confidence: 0, method: "Web search (no consensus)", origin: "none", local_matches: [], error: "index is corrupt" } });
  render(<EntityReconView hostClient={client as never} />);
  await screen.findByTestId("entity-recon");

  fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent(/pick a cutout/i);
  });
  expect(client.entityReconResolve).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("Cutout image"), { target: { value: "/c.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent("index is corrupt");
  });
});
