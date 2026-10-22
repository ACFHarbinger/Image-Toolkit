import { expect } from "vitest";
// Shared scenario driver for the conformance fixtures — the TS twin of
// `middleware/test/sidecar/test_conformance.py`. Keep the DSL in sync with
// the `description` field in `fixtures/conformance.json`.

import { HostClientError } from "../errors";
import { SidecarTransport } from "../sidecar";
import type { StdioChannel } from "../sidecar";

export interface Scenario {
  name: string;
  attach?: {
    client?: { name: string; version: string };
    expect?: Expectation;
  };
  steps: Array<{
    method: string;
    params?: Record<string, unknown>;
    expect: Expectation;
    capture?: Record<string, string>;
  }>;
}

export type Expectation = { result?: unknown; error?: unknown };

export function substitute(value: unknown, captures: Record<string, unknown>): unknown {
  if (typeof value === "string") {
    return value.replace(/\$\{([a-z_]+)\}/g, (_m, name: string) => String(captures[name]));
  }
  if (Array.isArray(value)) return value.map((item) => substitute(item, captures));
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, substitute(item, captures)]),
    );
  }
  return value;
}

export function assertSubset(expected: unknown, actual: unknown, path = "$"): void {
  if (expected === "*") {
    expect(actual).not.toBeUndefined();
    expect(actual).not.toBeNull();
    return;
  }
  if (Array.isArray(expected)) {
    expect(Array.isArray(actual), `${path}: expected array`).toBe(true);
    expect((actual as unknown[]).length, `${path}.length`).toBe(expected.length);
    expected.forEach((item, index) => assertSubset(item, (actual as unknown[])[index], `${path}[${index}]`));
    return;
  }
  if (typeof expected === "object" && expected !== null) {
    expect(typeof actual, `${path}: expected object`).toBe("object");
    for (const [key, item] of Object.entries(expected)) {
      expect(actual, `${path}.${key}: missing`).toHaveProperty(key);
      assertSubset(item, (actual as Record<string, unknown>)[key], `${path}.${key}`);
    }
    return;
  }
  expect(actual, path).toEqual(expected);
}

function errorEnvelope(error: HostClientError): Record<string, unknown> {
  return {
    code: error.code,
    retryable: error.retryable,
    message_key: error.message_key,
    ...(error.details ? { details: error.details } : {}),
  };
}

async function expectCall(
  call: () => Promise<unknown>,
  expectBlock: Expectation,
): Promise<unknown> {
  if (expectBlock.error !== undefined) {
    const error = await call().then(
      () => {
        throw new Error("expected the call to reject");
      },
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(HostClientError);
    assertSubset(expectBlock.error, errorEnvelope(error as HostClientError));
    return undefined;
  }
  const result = await call();
  if (expectBlock.result !== undefined) assertSubset(expectBlock.result, result);
  return result;
}

export async function runScenario(
  scenario: Scenario,
  defaults: { protocol: string; client: { name: string; version: string } },
  makeChannel: () => { client: StdioChannel; server: StdioChannel },
): Promise<void> {
  void defaults.protocol; // the protocol const lives in SidecarTransport
  const identity = scenario.attach?.client ?? defaults.client;
  const { client } = makeChannel();
  const transport = new SidecarTransport(client, {
    clientName: identity.name,
    clientVersion: identity.version,
  });
  const attachExpect = scenario.attach?.expect ?? { result: "*" };
  await expectCall(() => transport.attach(), attachExpect);
  if (attachExpect.error !== undefined) return; // failed attach: no steps follow
  const captures: Record<string, unknown> = {};
  for (const step of scenario.steps) {
    const params = substitute(step.params ?? {}, captures) as Record<string, unknown>;
    const expectBlock = substitute(step.expect, captures) as Expectation;
    const result = await expectCall(() => transport.request(step.method, params), expectBlock);
    for (const [name, source] of Object.entries(step.capture ?? {})) {
      const field = source.replace(/^result\./, "");
      captures[name] = (result as Record<string, unknown>)[field];
    }
  }
  transport.close();
}
