/**
 * Metadata inspector page (§7.16A). The background worker stores the parsed
 * result under `lastInspect` in storage.local and opens this page in a popup
 * window.
 */
import { storageGet } from "../shared/api";
import type { ImageMetadata } from "../shared/imageMeta";

export interface LastInspect {
  imageUrl: string;
  meta: ImageMetadata;
  error?: string;
}

const $ = <T extends HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

function section(title: string): HTMLHeadingElement {
  const h = document.createElement("h3");
  h.textContent = title;
  return h;
}

function kvGrid(entries: Record<string, string>): HTMLDivElement {
  const grid = document.createElement("div");
  grid.className = "kv";
  for (const [k, v] of Object.entries(entries)) {
    const kEl = document.createElement("div");
    kEl.className = "k";
    kEl.textContent = k;
    const vEl = document.createElement("div");
    vEl.className = "v";
    vEl.textContent = v.length > 4000 ? `${v.slice(0, 4000)}…` : v;
    grid.append(kEl, vEl);
  }
  return grid;
}

function copyButton(text: string): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.textContent = "Copy";
  btn.addEventListener("click", () => {
    void navigator.clipboard.writeText(text);
    btn.textContent = "Copied ✓";
    setTimeout(() => (btn.textContent = "Copy"), 1200);
  });
  return btn;
}

function prettyMaybeJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function render(data: LastInspect): void {
  $<HTMLDivElement>("src").textContent = data.imageUrl;
  $<HTMLImageElement>("thumb").src = data.imageUrl;
  const content = $<HTMLDivElement>("content");
  content.replaceChildren();

  if (data.error) {
    content.textContent = `Failed: ${data.error}`;
    return;
  }
  const meta = data.meta;
  $<HTMLDivElement>("dims").textContent =
    `${meta.format.toUpperCase()}` +
    (meta.width ? ` · ${meta.width}×${meta.height}` : "");

  if (meta.ai) {
    content.appendChild(section("AI Generation Metadata"));
    const tool = document.createElement("span");
    tool.className = "ai-tool";
    tool.textContent = meta.ai.tool;
    content.appendChild(tool);
    content.appendChild(copyButton(meta.ai.raw));
    const pre = document.createElement("pre");
    pre.textContent = prettyMaybeJson(meta.ai.raw);
    content.appendChild(pre);
  }

  if (Object.keys(meta.exif).length > 0) {
    content.appendChild(section("EXIF"));
    content.appendChild(kvGrid(meta.exif));
  }

  const otherText = Object.fromEntries(
    Object.entries(meta.text).filter(
      ([k]) => !meta.ai || (k !== "parameters" && k !== "workflow" && k !== "prompt" && k !== "Comment" && k !== "invokeai_metadata"),
    ),
  );
  if (Object.keys(otherText).length > 0) {
    content.appendChild(section("Text Chunks"));
    content.appendChild(kvGrid(otherText));
  }

  if (!meta.ai && Object.keys(meta.exif).length === 0 && Object.keys(otherText).length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No embedded metadata found in this image.";
    content.appendChild(empty);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  void storageGet<{ lastInspect: LastInspect }>("lastInspect").then(
    ({ lastInspect }) => {
      if (lastInspect) render(lastInspect);
      else $<HTMLDivElement>("content").textContent = "Nothing inspected yet.";
    },
  );
});
