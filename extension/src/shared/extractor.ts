/**
 * Full-resolution image extraction (§7.11).
 *
 * `img.src` is often a downscaled thumbnail. This module picks the best
 * available candidate for an image element:
 *   1. the largest `srcset` entry on the <img> and any parent <picture>
 *      <source> elements,
 *   2. common lazy-load attributes (data-src, data-original, …) when present,
 *   3. CSS background-image URLs when hit-testing non-<img> elements.
 */

export interface ImageCandidate {
  url: string;
  /** Width in px from a `w` descriptor, or density × 1000 for `x` descriptors. */
  score: number;
}

/** Lazy-load attributes checked on <img> elements, in priority order. */
const LAZY_ATTRS = [
  "data-src",
  "data-original",
  "data-lazy-src",
  "data-full-src",
  "data-orig-file",
  "data-large-file",
];

const LAZY_SRCSET_ATTRS = ["data-srcset", "data-lazy-srcset"];

/** Parse a srcset string into scored candidates. */
export function parseSrcset(srcset: string): ImageCandidate[] {
  const out: ImageCandidate[] = [];
  for (const part of srcset.split(",")) {
    const tokens = part.trim().split(/\s+/);
    const url = tokens[0];
    if (!url) continue;
    let score = 0;
    const desc = tokens[1];
    if (desc?.endsWith("w")) {
      score = parseFloat(desc);
    } else if (desc?.endsWith("x")) {
      score = parseFloat(desc) * 1000; // density-only srcsets: higher x wins
    }
    if (Number.isFinite(score)) out.push({ url, score });
  }
  return out;
}

function resolveUrl(url: string, base: string): string | null {
  try {
    const abs = new URL(url, base);
    if (abs.protocol === "http:" || abs.protocol === "https:" || abs.protocol === "data:" || abs.protocol === "blob:") {
      return abs.toString();
    }
  } catch {
    /* invalid URL */
  }
  return null;
}

/**
 * Pick the highest-resolution candidate URL for an <img> element.
 * Falls back to `currentSrc`/`src` when nothing better is found.
 */
export function bestImageUrl(img: HTMLImageElement): string {
  const candidates: ImageCandidate[] = [];
  const baseline = img.currentSrc || img.src;
  // The rendered source participates with its natural width as score.
  if (baseline) {
    candidates.push({ url: baseline, score: img.naturalWidth || 0 });
  }

  if (img.srcset) candidates.push(...parseSrcset(img.srcset));
  for (const attr of LAZY_SRCSET_ATTRS) {
    const v = img.getAttribute(attr);
    if (v) candidates.push(...parseSrcset(v));
  }
  // <picture><source srcset=…> variants
  const picture = img.closest("picture");
  if (picture) {
    for (const source of picture.querySelectorAll("source")) {
      if (source.srcset) candidates.push(...parseSrcset(source.srcset));
    }
  }
  // Lazy-load single-URL attributes: prefer over equal-score srcset entries
  // (sites usually put the full-size original there).
  for (const attr of LAZY_ATTRS) {
    const v = img.getAttribute(attr);
    if (v) candidates.push({ url: v, score: Number.MAX_SAFE_INTEGER });
  }

  let best: ImageCandidate | null = null;
  for (const c of candidates) {
    const abs = resolveUrl(c.url, document.baseURI);
    if (!abs) continue;
    if (!best || c.score > best.score) best = { url: abs, score: c.score };
  }
  return best?.url ?? baseline;
}

/** Extract a CSS background-image URL from an element, if any. */
export function backgroundImageUrl(el: Element): string | null {
  const bg = getComputedStyle(el).backgroundImage;
  const match = /url\(["']?([^"')]+)["']?\)/.exec(bg);
  if (!match) return null;
  return resolveUrl(match[1], document.baseURI);
}

export interface HitResult {
  url: string;
  /** The element the URL came from (for visual capture feedback). */
  element: Element;
}

/**
 * Find the best image at a viewport point: prefers <img> elements (with
 * full-res candidate upgrade), falls back to CSS background images on the
 * element chain.
 */
export function findImageAt(x: number, y: number): HitResult | null {
  const elements = document.elementsFromPoint(x, y);

  for (const el of elements) {
    if (el.tagName === "IMG" && (el as HTMLImageElement).src) {
      return { url: bestImageUrl(el as HTMLImageElement), element: el };
    }
  }
  for (const el of elements) {
    const bg = backgroundImageUrl(el);
    if (bg) return { url: bg, element: el };
  }
  return null;
}
