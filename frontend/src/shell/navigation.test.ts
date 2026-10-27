import { expect, test } from "vitest";
import { shellCatalog } from "./catalog";
import {
  ACTIVE_ALIAS_GATES,
  categoriesInOrder,
  classicPages,
  classicSubtabs,
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
  expect(drawerEntries(entries, "System Tools").every((entry) => entry.kind !== "route")).toBe(true);
  expect(ribbonRoutes(entries, "stitch").map((entry) => entry.id)).toContain("stitch.canvas");
  expect(ribbonRoutes(entries, null)).toEqual([]);
});

test("classic pages keep stitch under Image Editor and its routes as subtabs", () => {
  const pages = classicPages(entries, "Image Editor");
  expect(pages.map((entry) => entry.id)).toEqual(["editor.hybrid", "stitch"]);
  expect(classicSubtabs(entries, pages[1]).map((entry) => entry.id)).toContain("stitch.canvas");
  expect(classicSubtabs(entries, pages[0])).toEqual([]);
  expect(categoriesInOrder(entries)).not.toContain("Image Stitching");
});

test("stitch panels share the Image Editor drawer", () => {
  expect(categoriesInOrder(entries)).not.toContain("Image Stitching");
  expect(categoriesInOrder(entries)).toContain("Image Editor");
  expect(drawerEntries(entries, "Image Editor").map((entry) => entry.id)).toEqual([
    "editor.hybrid",
    "stitch.stitch",
    "stitch.graph",
    "stitch.adjust",
    "stitch.canvas",
    "stitch.statistics",
    "stitch.sequence-builder",
    "stitch.hybrid",
    "stitch.animation-clusters",
  ]);
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
