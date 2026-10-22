// @vitest-environment node
import { describe, expect, it } from "vitest";
import { RustTransport } from "../rust";

describe("RustTransport", () => {
  it("passes native ops through the injected invoke", async () => {
    const calls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const invoke = async (command: string, args?: Record<string, unknown>) => {
      calls.push({ command, args });
      return ["/tmp/a.png"];
    };
    const transport = new RustTransport(invoke);
    await expect(transport.request("pick_files", { multiple: true })).resolves.toEqual([
      "/tmp/a.png",
    ]);
    expect(calls).toEqual([{ command: "pick_files", args: { multiple: true } }]);
  });
});
