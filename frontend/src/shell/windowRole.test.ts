import { afterEach, expect, test } from "vitest";
import { windowRole } from "./windowRole";

afterEach(() => {
  window.history.replaceState({}, "", "/");
});

test("defaults to main", () => {
  expect(windowRole()).toBe("main");
});

test("reads the window query used by the cloud.jobs pop-out", () => {
  window.history.replaceState({}, "", "/?window=cloud.jobs");
  expect(windowRole()).toBe("cloud.jobs");
});
