import { describe, expect, it, vi } from "vitest";

import type { BridgeRequest, BridgeResponse, HandshakeResult } from "../../../../contracts/generated/ts";
import { DjangoTransport, HostClient, RustTransport, SidecarTransport } from "..";
import type { SidecarConnection } from "../sidecar";
import type { BridgeTransport } from "../transport";

const HANDSHAKE: HandshakeResult = {
  protocol: "image-toolkit-bridge",
  version: "1.0.0",
  compatibility: { min: "1.0.0", max: "1.0.0" },
  capabilities: ["system", "jobs"],
};

function result(request: BridgeRequest, value: unknown): BridgeResponse {
  return { jsonrpc: "2.0", id: request.id, result: value as Record<string, unknown> };
}

function appError(request: BridgeRequest, code: string, retryable = false): BridgeResponse {
  return {
    jsonrpc: "2.0",
    id: request.id,
    error: {
      code: retryable ? -32000 : -32601,
      message: `bridge.errors.${code.split(".").pop()}`,
      data: {
        code,
        retryable,
        message_key: `bridge.errors.${code.split(".").pop()}`,
      },
    },
  };
}

function demoResponse(request: BridgeRequest): BridgeResponse {
  if (request.method === "system.handshake") return result(request, HANDSHAKE);
  if (request.method === "system.ping") return result(request, { ok: true });
  if (request.method === "jobs.cancel") return result(request, { ok: true });
  if (request.method === "jobs.status") return appError(request, "jobs.not_found");
  return appError(request, "bridge.method_not_found");
}

interface TransportCase {
  transport: BridgeTransport;
  requests(): BridgeRequest[];
}

function sidecarCase(handler: (request: BridgeRequest) => unknown[] = (request) => [demoResponse(request)]): TransportCase & {
  emit(frame: unknown): void;
} {
  const requests: BridgeRequest[] = [];
  const lineListeners = new Set<(line: string) => void>();
  const connection: SidecarConnection = {
    sendLine(line: string) {
      expect(line.endsWith("\n")).toBe(true);
      const request = JSON.parse(line) as BridgeRequest;
      requests.push(request);
      for (const response of handler(request)) {
        queueMicrotask(() => {
          for (const listener of lineListeners) listener(`${JSON.stringify(response)}\n`);
        });
      }
    },
    onLine(listener: (line: string) => void) {
      lineListeners.add(listener);
      return () => lineListeners.delete(listener);
    },
  };
  return {
    transport: new SidecarTransport(connection),
    requests: () => requests,
    emit(frame: unknown) {
      for (const listener of lineListeners) listener(JSON.stringify(frame));
    },
  };
}

function djangoCase(): TransportCase & { bodies: string[] } {
  const bodies: string[] = [];
  const fetchImpl = vi.fn(async (_input: string, init?: RequestInit) => {
    const body = String(init?.body ?? "");
    bodies.push(body);
    const request = JSON.parse(body) as BridgeRequest;
    return {
      ok: true,
      json: async () => demoResponse(request),
    } as Response;
  });
  return {
    transport: new DjangoTransport({ baseUrl: "http://api.test/api", fetchImpl }),
    requests: () => bodies.map((body) => JSON.parse(body) as BridgeRequest),
    bodies,
  };
}

function rustCase(): TransportCase & { calls: Array<{ command: string; args?: Record<string, unknown> }> } {
  const calls: Array<{ command: string; args?: Record<string, unknown> }> = [];
  const invokeImpl = async <T,>(command: string, args?: Record<string, unknown>): Promise<T> => {
    calls.push({ command, args });
    return demoResponse(args?.request as BridgeRequest) as T;
  };
  return {
    transport: new RustTransport({ invokeImpl }),
    requests: () => calls.map((call) => call.args?.request as BridgeRequest),
    calls,
  };
}

function runTransportConformance(name: string, make: () => TransportCase): void {
  describe(`${name} conformance`, () => {
    it("handshakes before commands and sends the shared flat envelope", async () => {
      const testCase = make();
      const client = new HostClient(testCase.transport, {
        clientName: "conformance",
        clientVersion: "1.0.0",
        reconnectAttempts: 1,
      });
      const handshake = await client.connect();
      expect(handshake.capabilities).toEqual(["system", "jobs"]);
      await expect(client.ping()).resolves.toEqual({ ok: true });

      const [handshakeRequest, pingRequest] = testCase.requests();
      expect(handshakeRequest).toEqual({
        jsonrpc: "2.0",
        id: "host-1",
        method: "system.handshake",
        params: {
          protocol: "image-toolkit-bridge",
          client: { name: "conformance", version: "1.0.0" },
        },
      });
      expect(pingRequest.method).toBe("system.ping");
      expect(pingRequest).not.toHaveProperty("request");
      expect(pingRequest).not.toHaveProperty("envelope");
    });

    it("maps the shared error envelope", async () => {
      const client = new HostClient(make().transport, {
        clientName: "conformance",
        clientVersion: "1.0.0",
        reconnectAttempts: 1,
      });
      await expect(client.jobStatus("missing")).rejects.toMatchObject({
        code: "jobs.not_found",
        retryable: false,
        messageKey: "bridge.errors.not_found",
      });
    });

    it("sends idempotent cancel through the same method surface", async () => {
      const testCase = make();
      const client = new HostClient(testCase.transport, {
        clientName: "conformance",
        clientVersion: "1.0.0",
        reconnectAttempts: 1,
      });
      await expect(client.cancelJob("job-1")).resolves.toEqual({ ok: true });
      const cancel = testCase.requests().at(-1);
      expect(cancel?.method).toBe("jobs.cancel");
      expect(cancel?.params).toEqual({ job_id: "job-1" });
    });
  });
}

runTransportConformance("sidecar", () => sidecarCase());
runTransportConformance("Django", () => djangoCase());
runTransportConformance("Rust", () => rustCase());

describe("SidecarTransport", () => {
  it("routes decoded event frames without treating them as responses", async () => {
    const testCase = sidecarCase((request) => [
      {
        channel: "jobs",
        seq: 1,
        kind: "fact",
        durable: true,
        ts: "2026-10-23T00:00:00Z",
        payload: { job_id: "job-1", state: "queued" },
      },
      demoResponse(request),
    ]);
    const events: unknown[] = [];
    testCase.transport.onEvent?.((frame) => events.push(frame));
    const client = new HostClient(testCase.transport, {
      clientName: "events",
      clientVersion: "1.0.0",
      reconnectAttempts: 1,
    });
    await client.connect();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ channel: "jobs", seq: 1 });
  });
});

describe("HostClient", () => {
  it("rejects an incompatible sidecar version before commands", async () => {
    const testCase = sidecarCase((request) => [
      result(request, {
        ...HANDSHAKE,
        compatibility: { min: "2.0.0", max: "2.0.0" },
      }),
    ]);
    const client = new HostClient(testCase.transport, {
      clientName: "version-gate",
      clientVersion: "1.0.0",
      reconnectAttempts: 1,
    });
    await expect(client.connect()).rejects.toMatchObject({ code: "bridge.version_mismatch" });
    expect(testCase.requests()).toHaveLength(1);
  });

  it("bounds reconnect attempts for transport failures", async () => {
    let attempts = 0;
    const transport: BridgeTransport = {
      async request() {
        attempts += 1;
        throw new Error("not retryable by HostClient");
      },
      reset: vi.fn(),
    };
    const client = new HostClient(transport, {
      clientName: "retry",
      clientVersion: "1.0.0",
      reconnectAttempts: 3,
      reconnectDelayMs: 0,
    });
    await expect(client.connect()).rejects.toThrow("not retryable");
    expect(attempts).toBe(1);
    expect(transport.reset).not.toHaveBeenCalled();
  });
});
