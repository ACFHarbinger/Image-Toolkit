// @vitest-environment node
import { describe, expect, it } from "vitest";

import type { BridgeRequest, BridgeResponse } from "../../../../contracts/generated/ts";
import { RustTransport } from "../rust";

describe("RustTransport", () => {
  it("passes the bridge request through the injected invoke", async () => {
    const calls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const request: BridgeRequest = { jsonrpc: "2.0", id: "1", method: "system.ping", params: {} };
    const invokeImpl = async <T,>(command: string, args?: Record<string, unknown>): Promise<T> => {
      calls.push({ command, args });
      return { jsonrpc: "2.0", id: "1", result: { ok: true } } as T;
    };
    const transport = new RustTransport({ invokeImpl });
    await expect(transport.request(request)).resolves.toEqual({
      jsonrpc: "2.0",
      id: "1",
      result: { ok: true },
    } satisfies BridgeResponse);
    expect(calls).toEqual([{ command: "bridge_request", args: { request } }]);
  });
});
