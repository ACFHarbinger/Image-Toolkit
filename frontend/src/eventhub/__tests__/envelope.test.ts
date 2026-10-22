import { describe, expect, it } from "vitest";
import { guardEvent } from "../envelope";
import { CHANNEL_NAMES } from "../generated/channels";
import { makeEvent } from "./helpers";

const known = new Set<string>(CHANNEL_NAMES);

describe("guardEvent", () => {
  it("accepts a well-formed frame for a known channel", () => {
    const result = guardEvent(makeEvent("jobs", 7), known);
    expect(result.ok).toBe(true);
  });

  it("rejects non-objects", () => {
    for (const frame of [null, undefined, 42, "jobs", ["jobs"]]) {
      expect(guardEvent(frame, known).ok).toBe(false);
    }
  });

  it("rejects unknown and malformed channels", () => {
    expect(guardEvent(makeEvent("nope", 1), known)).toMatchObject({ ok: false });
    expect(guardEvent(makeEvent("Jobs", 1), known)).toMatchObject({ ok: false });
    expect(guardEvent(makeEvent("jobs..x", 1), known)).toMatchObject({ ok: false });
  });

  it("rejects bad sequence numbers", () => {
    for (const seq of [0, -1, 1.5, Number.NaN, "1", null]) {
      expect(guardEvent(makeEvent("jobs", seq as number), known)).toMatchObject({ ok: false });
    }
  });

  it("rejects unknown kinds and non-boolean durable flags", () => {
    expect(guardEvent(makeEvent("jobs", 1, { kind: "notification" as never }), known)).toMatchObject({ ok: false });
    expect(guardEvent(makeEvent("jobs", 1, { durable: "yes" as never }), known)).toMatchObject({ ok: false });
  });

  it("rejects non-object payloads and non-string timestamps", () => {
    expect(guardEvent(makeEvent("jobs", 1, { payload: [1, 2] as never }), known)).toMatchObject({ ok: false });
    expect(guardEvent(makeEvent("jobs", 1, { payload: null as never }), known)).toMatchObject({ ok: false });
    expect(guardEvent(makeEvent("jobs", 1, { ts: 123 as never }), known)).toMatchObject({ ok: false });
  });
});
