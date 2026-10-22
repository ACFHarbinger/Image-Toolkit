// @vitest-environment node
import { describe, expect, it } from "vitest";
import { HostClientError } from "../errors";
import { HttpTransport } from "../http";

function fakeFetch(status: number, body: unknown) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchFn = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as Response;
  }) as typeof fetch;
  return { calls, fetchFn };
}

describe("HttpTransport", () => {
  it("posts params to {baseUrl}/bridge/<method> and returns the result", async () => {
    const { calls, fetchFn } = fakeFetch(200, { ok: true });
    const transport = new HttpTransport({ baseUrl: "http://localhost:8000/api/", fetchFn });
    await expect(transport.request("system.ping", {})).resolves.toEqual({ ok: true });
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("http://localhost:8000/api/bridge/system.ping");
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({});
  });

  it("decodes a non-200 error envelope body into HostClientError", async () => {
    const envelope = {
      code: "jobs.not_found",
      retryable: false,
      message_key: "bridge.errors.not_found",
      details: { job_id: "nope" },
    };
    const { fetchFn } = fakeFetch(404, envelope);
    const transport = new HttpTransport({ baseUrl: "http://localhost:8000/api", fetchFn });
    const error = await transport
      .request("jobs.status", { job_id: "nope" })
      .catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(HostClientError);
    expect(error).toMatchObject({ code: "jobs.not_found", retryable: false });
  });
});
