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

it("registers events before issuing a command and detaches after close", async () => {
  const order: string[] = [];
  let receive: ((event: { payload: import("../../../../contracts/generated/ts").BridgeEvent }) => void) | undefined;
  const transport = new RustTransport({
    listenImpl: async (name, callback) => {
      order.push(name);
      receive = callback;
      return () => { order.push("unlisten"); };
    },
    invokeImpl: async <T,>() => {
      order.push("invoke");
      return { jsonrpc: "2.0", id: "1", result: {} } as T;
    },
  });
  const frames: unknown[] = [];
  const off = transport.onEvent(frame => frames.push(frame));
  await transport.request({ jsonrpc: "2.0", id: "1", method: "system.ping" });
  const frame = { channel: "jobs", seq: 1, kind: "fact", payload: { state: "done" } } as unknown as import("../../../../contracts/generated/ts").BridgeEvent;
  receive!({ payload: frame });
  expect(frames).toEqual([frame]);
  expect(order).toEqual(["bridge-event", "invoke"]);
  off();
  receive!({ payload: frame });
  expect(frames).toHaveLength(1);
  await transport.close();
  expect(order.at(-1)).toBe("unlisten");
  await expect(transport.request({ jsonrpc: "2.0", id: "2", method: "system.ping" })).rejects.toThrow("closed");
});

it("unsubscribes even when closed during asynchronous registration", async () => {
  let finish!: (unlisten: () => void) => void;
  let detached = false;
  const transport = new RustTransport({ listenImpl: () => new Promise(resolve => { finish = resolve; }) });
  transport.onEvent(() => {});
  const closing = transport.close();
  finish(() => { detached = true; });
  await closing;
  expect(detached).toBe(true);
});
