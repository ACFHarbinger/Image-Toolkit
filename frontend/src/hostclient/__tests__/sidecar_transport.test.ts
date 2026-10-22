// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { HostClientError } from "../errors";
import { SidecarTransport } from "../sidecar";
import type { BridgeEvent } from "../types";
import { FakeSidecar, loopbackPair } from "./loopback";

function setup(options = {}, transportOptions = {}) {
  const pair = loopbackPair();
  new FakeSidecar(pair.server, options);
  const transport = new SidecarTransport(pair.client, transportOptions);
  return { pair, transport };
}

describe("SidecarTransport", () => {
  it("attaches with handshake and negotiates the version range", async () => {
    const { transport } = setup();
    const result = await transport.attach();
    expect(result.protocol).toBe("image-toolkit-bridge");
    expect(result.compatibility).toEqual({ min: "1.0.0", max: "1.0.0" });
    expect(result.capabilities).toEqual(["system", "jobs"]);
  });

  it("rejects attach when the sidecar reports a version mismatch", async () => {
    const { transport } = setup({}, { clientVersion: "0.0.1" });
    await expect(transport.attach()).rejects.toMatchObject({
      code: "bridge.version_mismatch",
      retryable: false,
    });
  });

  it("rejects attach locally when the reported range excludes our version", async () => {
    const pair = loopbackPair();
    pair.server.onLine((line) => {
      const frame = JSON.parse(line);
      pair.server.send(
        JSON.stringify({
          jsonrpc: "2.0",
          id: frame.id,
          result: {
            protocol: "image-toolkit-bridge",
            version: "2.0.0",
            compatibility: { min: "2.0.0", max: "2.0.0" },
            capabilities: ["system"],
          },
        }),
      );
    });
    const transport = new SidecarTransport(pair.client, { clientVersion: "1.0.0" });
    await expect(transport.attach()).rejects.toMatchObject({
      code: "bridge.version_mismatch",
      retryable: false,
    });
  });

  it("round-trips a request after implicit attach", async () => {
    const { transport } = setup();
    await expect(transport.request("system.ping", {})).resolves.toEqual({ ok: true });
  });

  it("decodes the wire error envelope into HostClientError", async () => {
    const { transport } = setup();
    const error = await transport
      .request("jobs.status", { job_id: "nope" })
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(HostClientError);
    expect(error).toMatchObject({
      code: "jobs.not_found",
      retryable: false,
      details: { job_id: "nope" },
    });
    expect((error as HostClientError).message_key).toBeTruthy();
  });

  it("forwards event frames to onEvent", async () => {
    const events: BridgeEvent[] = [];
    const { transport } = setup({}, { onEvent: (event: BridgeEvent) => events.push(event) });
    await transport.request("jobs.submit", { kind: "demo", spec: {} });
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ channel: "jobs", durable: true, payload: { state: "queued" } });
  });

  it("rejects in-flight requests on close with bridge.down", async () => {
    const pair = loopbackPair(); // no responder attached
    const transport = new SidecarTransport(pair.client);
    const pending = transport.request("system.ping", {});
    transport.close();
    await expect(pending).rejects.toMatchObject({ code: "bridge.down", retryable: true });
  });

  it("reports a non-JSON line as a protocol error", () => {
    const onProtocolError = vi.fn();
    const pair = loopbackPair();
    const transport = new SidecarTransport(pair.client, { onProtocolError });
    pair.server.send("this is not json");
    expect(onProtocolError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "bridge.parse_error" }),
    );
    transport.close();
  });
});
