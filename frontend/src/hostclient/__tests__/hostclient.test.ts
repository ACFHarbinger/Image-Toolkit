// @vitest-environment node
import { describe, expect, it } from "vitest";
import { HostClientError } from "../errors";
import { HostClient } from "../hostclient";
import { OPERATION_MANIFEST } from "../manifest";
import type { Transport } from "../transport";

function spyTransport(results: Record<string, unknown> = {}) {
  const calls: Array<{ method: string; params?: Record<string, unknown> }> = [];
  const transport: Transport = {
    request: async (method, params) => {
      calls.push({ method, params });
      return results[method] ?? null;
    },
    close: () => undefined,
  };
  return { calls, transport };
}

describe("HostClient", () => {
  it("routes bridge operations to the sidecar transport", async () => {
    const sidecar = spyTransport({
      "system.ping": { ok: true },
      "jobs.submit": { job_id: "job-1" },
      "jobs.cancel": { ok: true },
      "jobs.status": { job_id: "job-1", kind: "demo", state: "queued" },
      "jobs.list": { jobs: [] },
    });
    const client = new HostClient({ sidecar: sidecar.transport });

    await expect(client.ping()).resolves.toEqual({ ok: true });
    await expect(client.submitJob("demo", { a: 1 })).resolves.toEqual({ job_id: "job-1" });
    await expect(client.cancelJob("job-1")).resolves.toEqual({ ok: true });
    await expect(client.jobStatus("job-1")).resolves.toMatchObject({ state: "queued" });
    await expect(client.listJobs({ states: ["queued"], limit: 10 })).resolves.toEqual({ jobs: [] });

    expect(sidecar.calls).toEqual([
      { method: "system.ping", params: {} },
      { method: "jobs.submit", params: { kind: "demo", spec: { a: 1 } } },
      { method: "jobs.cancel", params: { job_id: "job-1" } },
      { method: "jobs.status", params: { job_id: "job-1" } },
      { method: "jobs.list", params: { states: ["queued"], limit: 10 } },
    ]);
  });

  it("routes native operations to the rust transport", async () => {
    const rust = spyTransport({ pick_files: ["/tmp/a.png"] });
    const client = new HostClient({ rust: rust.transport });
    await expect(client.pickFiles({ multiple: true })).resolves.toEqual(["/tmp/a.png"]);
    expect(rust.calls[0]).toEqual({ method: "pick_files", params: { multiple: true } });
  });

  it("fails when the routed transport is not provided", async () => {
    const client = new HostClient({}); // no transports bound
    await expect(client.ping()).rejects.toMatchObject({
      code: "hostclient.no_transport",
      details: { operation: "ping", transport: "sidecar" },
    });
  });

  it("exposes manifest metadata", () => {
    const client = new HostClient({});
    expect(client.transportFor("submitJob")).toBe("sidecar");
    expect(client.transportFor("pickFiles")).toBe("rust");
    expect(client.isCancelable("submitJob")).toBe(false);
    expect(() => client.transportFor("nope")).toThrow(HostClientError);
  });

  it("manifest rows cover every HostClient operation exactly once", () => {
    const operations = OPERATION_MANIFEST.map((row) => row.operation);
    expect(new Set(operations).size).toBe(operations.length);
    for (const row of OPERATION_MANIFEST) {
      if (row.transport === "rust") {
        // Native-only: no bridge (dotted) method may route to Rust.
        expect(row.method).not.toMatch(/^(system|jobs)\./);
      } else {
        expect(row.method).toMatch(/^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$/);
      }
    }
  });
});
