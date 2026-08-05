/**
 * Bulk page grabber — grid-preview page (§7.9C).
 *
 * Opened by the popup's "Grid preview…" button, which collects the page's
 * detected images via `collect_page_images` and stashes them under
 * `galleryData` in storage.local (see `GalleryData` in shared/messages.ts) —
 * a tab can't receive constructor arguments directly. This page renders that
 * list as a grid with size/format/URL filters, a per-item download
 * progress/status badge, and a duplicate-check badge that reuses the §7.16C
 * client-side pHash pre-check (no new dedup logic — this only wires the
 * existing `computePhashFromUrl` / `snapshotBestMatch` into a UI).
 */
import { api, storageGet } from "../shared/api";
import type {
  DownloadGalleryItemMsg,
  DownloadGalleryItemResponse,
  GalleryData,
} from "../shared/messages";
import type { PageImageItem } from "../shared/pageMedia";
import {
  computePhashFromUrl,
  getCachedPhashSnapshot,
  snapshotBestMatch,
} from "../shared/clientPhash";

const $ = <T extends HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

type DownloadStatus = "idle" | "downloading" | "done" | "error";
type DupStatus = "unknown" | "checking" | "none" | "possible" | "unavailable";

interface GalleryItem {
  item: PageImageItem;
  format: string;
  selected: boolean;
  status: DownloadStatus;
  statusError?: string;
  dup: DupStatus;
  dupHamming?: number;
  cell: HTMLDivElement;
  checkbox: HTMLInputElement;
  statusBadge: HTMLDivElement;
  dupBadge: HTMLDivElement;
}

let pageUrl = "";
let items: GalleryItem[] = [];

/** Best-effort file extension from a URL — "other" for anything unrecognized
 * (including data: URLs, whose extension lives in the MIME type instead). */
function formatOf(url: string): string {
  const dataMatch = /^data:image\/([a-z0-9+.-]+)/i.exec(url);
  if (dataMatch) return dataMatch[1].toLowerCase().replace("+xml", "");
  try {
    const path = new URL(url).pathname;
    const ext = /\.([a-z0-9]+)$/i.exec(path)?.[1]?.toLowerCase();
    if (ext) return ext;
  } catch {
    /* relative/invalid URL — fall through */
  }
  return "other";
}

/** Run `worker` over `list` with at most `limit` in flight at once. */
async function runPooled<T>(
  list: T[],
  limit: number,
  worker: (item: T) => Promise<void>,
): Promise<void> {
  let next = 0;
  const lane = async (): Promise<void> => {
    while (next < list.length) {
      const idx = next++;
      await worker(list[idx]);
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, list.length) }, () => lane()));
}

function setStatusBadge(g: GalleryItem): void {
  g.statusBadge.className = `badge badge-status ${g.status}`;
  g.statusBadge.textContent =
    g.status === "idle"
      ? ""
      : g.status === "downloading"
        ? "…"
        : g.status === "done"
          ? "✓"
          : "✕";
  g.statusBadge.title =
    g.status === "error" ? g.statusError ?? "Download failed" : "";
  g.statusBadge.style.display = g.status === "idle" ? "none" : "block";
}

function setDupBadge(g: GalleryItem): void {
  g.dupBadge.className = `badge badge-dup ${g.dup}`;
  g.dupBadge.style.display = g.dup === "unknown" ? "none" : "block";
  switch (g.dup) {
    case "checking":
      g.dupBadge.textContent = "…";
      g.dupBadge.title = "Checking against cached library hashes…";
      break;
    case "possible":
      g.dupBadge.textContent = `dup? d=${g.dupHamming}`;
      g.dupBadge.title =
        "Local pHash pre-check hint only — not authoritative. " +
        "Use \"Check if already downloaded\" for a confirmed match.";
      break;
    case "none":
      g.dupBadge.textContent = "new";
      g.dupBadge.title = "No close match in the cached pHash snapshot.";
      break;
    case "unavailable":
      g.dupBadge.textContent = "?";
      g.dupBadge.title = "Could not hash this image (fetch/CORS failure).";
      break;
    default:
      g.dupBadge.textContent = "";
  }
}

function buildCell(item: PageImageItem): GalleryItem {
  const cell = document.createElement("div");
  cell.className = "cell";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "cell-select";
  checkbox.checked = true;

  const thumbWrap = document.createElement("div");
  thumbWrap.className = "thumb-wrap";
  const img = document.createElement("img");
  img.src = item.url;
  img.loading = "lazy";
  img.alt = "";
  thumbWrap.appendChild(img);

  const statusBadge = document.createElement("div");
  statusBadge.className = "badge badge-status";
  statusBadge.style.display = "none";

  const dupBadge = document.createElement("div");
  dupBadge.className = "badge badge-dup";
  dupBadge.style.display = "none";

  thumbWrap.append(checkbox, statusBadge, dupBadge);

  const meta = document.createElement("div");
  meta.className = "cell-meta";
  const format = formatOf(item.url);
  meta.innerHTML = "";
  const dims = document.createElement("span");
  dims.textContent = item.width && item.height ? `${item.width}×${item.height}` : "?";
  const fmt = document.createElement("span");
  fmt.textContent = format.toUpperCase();
  meta.append(dims, fmt);

  const actions = document.createElement("div");
  actions.className = "cell-actions";
  const downloadBtn = document.createElement("button");
  downloadBtn.textContent = "Download";
  actions.appendChild(downloadBtn);

  cell.append(thumbWrap, meta, actions);

  const g: GalleryItem = {
    item,
    format,
    selected: true,
    status: "idle",
    dup: "unknown",
    cell,
    checkbox,
    statusBadge,
    dupBadge,
  };

  checkbox.addEventListener("change", () => {
    g.selected = checkbox.checked;
  });
  downloadBtn.addEventListener("click", () => {
    void downloadOne(g);
  });

  return g;
}

async function downloadOne(g: GalleryItem): Promise<void> {
  g.status = "downloading";
  g.statusError = undefined;
  setStatusBadge(g);
  const msg: DownloadGalleryItemMsg = {
    action: "download_gallery_item",
    url: g.item.url,
    pageUrl,
  };
  try {
    const resp = (await api.runtime.sendMessage(msg)) as
      | DownloadGalleryItemResponse
      | undefined;
    if (resp?.ok) {
      g.status = "done";
    } else {
      g.status = "error";
      g.statusError = resp?.error ?? "Download failed";
    }
  } catch (err) {
    g.status = "error";
    g.statusError = String(err);
  }
  setStatusBadge(g);
}

async function checkDupOne(g: GalleryItem): Promise<void> {
  g.dup = "checking";
  setDupBadge(g);
  try {
    const hash = await computePhashFromUrl(g.item.url);
    const hint = await snapshotBestMatch(hash);
    if (!hint) {
      g.dup = "unavailable";
      g.dupBadge.title = "No cached pHash snapshot yet — refresh it in the options page.";
    } else if (hint.probablyDuplicate) {
      g.dup = "possible";
      g.dupHamming = hint.bestHamming;
    } else {
      g.dup = "none";
    }
  } catch {
    g.dup = "unavailable";
  }
  setDupBadge(g);
}

// --- Filters ---

function currentFilters(): { minDim: number; url: string; formats: Set<string> } {
  const minDim = Number($<HTMLInputElement>("filter-min-dim").value) || 0;
  const url = $<HTMLInputElement>("filter-url").value.trim().toLowerCase();
  const formats = new Set(
    Array.from(document.querySelectorAll<HTMLDivElement>(".chip.active")).map(
      (c) => c.dataset.format ?? "",
    ),
  );
  return { minDim, url, formats };
}

function applyFilters(): void {
  const { minDim, url, formats } = currentFilters();
  let shown = 0;
  for (const g of items) {
    const matchesDim = Math.max(g.item.width, g.item.height) >= minDim;
    const matchesUrl = !url || g.item.url.toLowerCase().includes(url);
    const matchesFormat = formats.size === 0 || formats.has(g.format);
    const visible = matchesDim && matchesUrl && matchesFormat;
    g.cell.classList.toggle("hidden", !visible);
    if (visible) shown++;
  }
  renderSummary(shown);
}

function renderSummary(shown: number): void {
  const selected = items.filter((g) => g.selected && !g.cell.classList.contains("hidden")).length;
  const done = items.filter((g) => g.status === "done").length;
  const errors = items.filter((g) => g.status === "error").length;
  const summary = $<HTMLDivElement>("summary");
  let text = `${shown} of ${items.length} shown · ${selected} selected`;
  if (done > 0 || errors > 0) {
    text += ` · ${done} downloaded`;
    if (errors > 0) text += `, ${errors} failed`;
  }
  summary.textContent = text;
}

function buildFormatChips(): void {
  const container = $<HTMLDivElement>("format-chips");
  container.replaceChildren();
  const formats = Array.from(new Set(items.map((g) => g.format))).sort();
  for (const format of formats) {
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.textContent = format.toUpperCase();
    chip.dataset.format = format;
    chip.addEventListener("click", () => {
      chip.classList.toggle("active");
      applyFilters();
    });
    container.appendChild(chip);
  }
}

// --- Bulk actions ---

async function downloadSelected(): Promise<void> {
  const targets = items.filter(
    (g) => g.selected && !g.cell.classList.contains("hidden") && g.status !== "downloading",
  );
  if (targets.length === 0) return;
  const btn = $<HTMLButtonElement>("download-selected");
  btn.disabled = true;
  try {
    await runPooled(targets, 4, async (g) => {
      await downloadOne(g);
      renderSummary(
        items.filter((i) => !i.cell.classList.contains("hidden")).length,
      );
    });
  } finally {
    btn.disabled = false;
  }
}

async function checkDuplicates(): Promise<void> {
  const cache = await getCachedPhashSnapshot();
  const btn = $<HTMLButtonElement>("check-dups");
  if (!cache) {
    btn.title = "No cached pHash snapshot — refresh it from the options page's " +
      "\"Local pHash Pre-Check\" section first.";
  }
  const targets = items.filter((g) => !g.cell.classList.contains("hidden"));
  btn.disabled = true;
  try {
    await runPooled(targets, 4, checkDupOne);
  } finally {
    btn.disabled = false;
  }
}

// --- Init ---

function render(data: GalleryData): void {
  pageUrl = data.pageUrl;
  $<HTMLDivElement>("page-url").textContent = data.pageUrl;

  const grid = $<HTMLDivElement>("grid");
  grid.replaceChildren();
  items = data.images.map((item) => buildCell(item));
  for (const g of items) grid.appendChild(g.cell);

  if (items.length === 0) {
    $<HTMLDivElement>("empty").style.display = "block";
  }

  buildFormatChips();
  applyFilters();
}

document.addEventListener("DOMContentLoaded", () => {
  void storageGet<{ galleryData: GalleryData }>("galleryData").then(({ galleryData }) => {
    if (galleryData) render(galleryData);
    else {
      $<HTMLDivElement>("empty").style.display = "block";
      $<HTMLDivElement>("empty").textContent =
        "No page scan found. Open this from the popup's \"Grid preview…\" button.";
    }
  });

  $<HTMLInputElement>("filter-min-dim").addEventListener("input", applyFilters);
  $<HTMLInputElement>("filter-url").addEventListener("input", applyFilters);
  $<HTMLButtonElement>("select-all").addEventListener("click", () => {
    for (const g of items) {
      if (!g.cell.classList.contains("hidden")) {
        g.selected = true;
        g.checkbox.checked = true;
      }
    }
    applyFilters();
  });
  $<HTMLButtonElement>("select-none").addEventListener("click", () => {
    for (const g of items) {
      if (!g.cell.classList.contains("hidden")) {
        g.selected = false;
        g.checkbox.checked = false;
      }
    }
    applyFilters();
  });
  $<HTMLButtonElement>("download-selected").addEventListener("click", () => {
    void downloadSelected();
  });
  $<HTMLButtonElement>("check-dups").addEventListener("click", () => {
    void checkDuplicates();
  });
});
