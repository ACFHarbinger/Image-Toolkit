// @vitest-environment node
import { describe, expect, it } from "vitest";

import type { BridgeRequest } from "../../../../contracts/generated/ts";
import { BridgeTransportError } from "../errors";
import { SidecarTransport, type SidecarConnection } from "../sidecar";

function jsonLine(frame: unknown): string {
  return `${JSON.stringify(frame)}\n`;
}

function request(id: string, method: string): BridgeRequest {
  return { jsonrpc: "2.0", id, method, params: {} };
}

interface Harness {
  connection: SidecarConnection;
  sent: string[];
  emit(line: string): void;
  drop(reason?: unknown): void;
  failReconnect(error: Error): void;
  reconnects(): number;
}

function harness(): Harness {
  const sent: string[] = [];
  const lineListeners = new Set<(line: string) => void>();
  const closeListeners = new Set<(reason?: unknown) => void>();
  let reconnects = 0;
  let reconnectError: Error | undefined;
  const connection: SidecarConnection = {
    sendLine(line: string) {
      sent.push(line);
    },
    onLine(listener: (line: string) => void) {
      lineListeners.add(listener);
      return () => lineListeners.delete(listener);
    },
    onClose(listener: (reason?: unknown) => void) {
      closeListeners.add(listener);
      return () => closeListeners.delete(listener);
    },
    reconnect() {
      if (reconnectError) {
        throw reconnectError;
      }
      reconnects += 1;
    },
  };
  return {
    connection,
    sent,
    emit(line: string) {
      for (const listener of lineListeners) listener(line);
    },
    drop(reason?: unknown) {
      for (const listener of closeListeners) listener(reason);
    },
    failReconnect(error: Error) {
      reconnectError = error;
    },
    reconnects: () => reconnects,
  };
}

describe("SidecarTransport", () => {
  it("sends one JSON line and resolves the matching response", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    const pending = transport.request(request("1", "system.ping"));
    expect(pipe.sent).toEqual([jsonLine(request("1", "system.ping"))]);
    pipe.emit(jsonLine({ jsonrpc: "2.0", id: "1", result: { ok: true } }));
    await expect(pending).resolves.toMatchObject({ id: "1", result: { ok: true } });
  });

  it("returns an error envelope for the caller to decode", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    const pending = transport.request(request("2", "jobs.status"));
    pipe.emit(
      jsonLine({
        jsonrpc: "2.0",
        id: "2",
        error: {
          code: -32000,
          message: "bridge.errors.not_found",
          data: { code: "jobs.not_found", retryable: false, message_key: "bridge.errors.not_found" },
        },
      }),
    );
    await expect(pending).resolves.toMatchObject({
      id: "2",
      error: { data: { code: "jobs.not_found", retryable: false } },
    });
  });

  it("forwards event frames and still resolves the later response", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    const events: unknown[] = [];
    transport.onEvent((frame) => events.push(frame));
    const pending = transport.request(request("3", "jobs.submit"));
    pipe.emit(
      jsonLine({
        channel: "jobs",
        seq: 1,
        kind: "fact",
        durable: true,
        ts: "2026-10-23T00:00:00Z",
        payload: { state: "queued" },
      }),
    );
    expect(events).toEqual([expect.objectContaining({ channel: "jobs", payload: { state: "queued" } })]);
    pipe.emit(jsonLine({ jsonrpc: "2.0", id: "3", result: { job_id: "job-1" } }));
    await expect(pending).resolves.toMatchObject({ id: "3" });
  });

  it("rejects a null id before sending", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    await expect(
      transport.request({ jsonrpc: "2.0", id: null, method: "system.ping" }),
    ).rejects.toBeInstanceOf(BridgeTransportError);
    expect(pipe.sent).toEqual([]);
  });

  it("rejects in-flight work on close and does not send after that", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    const pending = transport.request(request("4", "system.ping"));
    await transport.close();
    await expect(pending).rejects.toBeInstanceOf(BridgeTransportError);
    await transport.reset();
    await expect(transport.request(request("5", "system.ping"))).rejects.toMatchObject({
      message: "sidecar transport is closed",
    });
    expect(pipe.sent).toHaveLength(1);
    expect(pipe.reconnects()).toBe(0);
  });

  it("rejects pending requests when a line is not JSON", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    const pending = transport.request(request("6", "system.ping"));
    pipe.emit("this is not json\n");
    await expect(pending).rejects.toMatchObject({ message: "sidecar emitted a non-JSON frame" });
  });

  it("blocks the next request after the connection drops", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    const pending = transport.request(request("7", "system.ping"));
    pipe.drop(new BridgeTransportError("sidecar closed"));
    await expect(pending).rejects.toMatchObject({ message: "sidecar closed" });
    await expect(transport.request(request("8", "system.ping"))).rejects.toMatchObject({
      message: "sidecar transport is closed",
    });
    expect(pipe.sent).toHaveLength(1);
  });

  it("sends again after reconnect and stays closed when reconnect fails", async () => {
    const pipe = harness();
    const transport = new SidecarTransport(pipe.connection);
    pipe.drop();
    await transport.reset();
    expect(pipe.reconnects()).toBe(1);
    const pending = transport.request(request("9", "system.ping"));
    expect(pipe.sent.at(-1)).toBe(jsonLine(request("9", "system.ping")));
    pipe.emit(jsonLine({ jsonrpc: "2.0", id: "9", result: { ok: true } }));
    await expect(pending).resolves.toMatchObject({ id: "9" });

    pipe.failReconnect(new Error("bind failed"));
    pipe.drop();
    await expect(transport.reset()).rejects.toThrow("bind failed");
    await expect(transport.request(request("10", "system.ping"))).rejects.toMatchObject({
      message: "sidecar transport is closed",
    });
    expect(pipe.sent).toEqual([jsonLine(request("9", "system.ping"))]);
    expect(pipe.reconnects()).toBe(1);
  });
});
