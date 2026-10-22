// @vitest-environment node
import { describe, it } from "vitest";
// Conformance: the shared scenarios against SidecarTransport over a
// loopback FakeSidecar (W0-12, #876). The Python twin
// (`middleware/test/sidecar/test_conformance.py`) runs the same fixtures
// against the live sidecar subprocess.

import fixtures from "./fixtures/conformance.json";
import { FakeSidecar, loopbackPair } from "./loopback";
import { runScenario, type Scenario } from "./scenario";

const makeChannel = () => {
  const pair = loopbackPair();
  new FakeSidecar(pair.server);
  return pair;
};

describe("bridge conformance (shared fixtures)", () => {
  for (const scenario of fixtures.scenarios as unknown as Scenario[]) {
    it(scenario.name, async () => {
      await runScenario(scenario, fixtures, makeChannel);
    });
  }
});
