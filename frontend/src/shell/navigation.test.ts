import { expect, test } from "vitest";
import { shellCatalog } from "./catalog";
import {
  ACTIVE_ALIAS_GATES,
  categoriesInOrder,
  defaultPageId,
  drawerEntries,
  frontendEntries,
  resolveAlias,
  ribbonRoutes,
} from "./navigation";

const entries = frontendEntries();

test("navigation ids are catalog ids, and the first page is system.convert", () => {
  expect(defaultPageId(entries)).toBe("system.convert");
  expect(entries.map((entry) => entry.id)).toContain("system.merge");
  expect(entries.some((entry) => entry.id === "convert")).toBe(false);
  expect(ACTIVE_ALIAS_GATES.has("experimental-dl")).toBe(false);
});

test("a category click's drawer lists pages and workspaces, not routes", () => {
  expect(categoriesInOrder(entries)[0]).toBe("System Tools");
  const stitching = drawerEntries(entries, "Image Stitching").map((entry) => entry.id);
  expect(stitching).toEqual(["stitch"]);
  expect(ribbonRoutes(entries, "stitch").map((entry) => entry.id)).toContain("stitch.canvas");
  expect(ribbonRoutes(entries, null)).toEqual([]);
});

test("experimental-dl aliases resolve only while that gate is on", () => {
  expect(resolveAlias("ml.training", shellCatalog.aliases, ACTIVE_ALIAS_GATES)).toBe(
    "ml.training",
  );
  expect(
    resolveAlias("ml.training", shellCatalog.aliases, new Set(["experimental-dl"])),
  ).toBe("dl.train");
  expect(resolveAlias("system.convert", shellCatalog.aliases, new Set(["experimental-dl"]))).toBe(
    "system.convert",
  );
});
