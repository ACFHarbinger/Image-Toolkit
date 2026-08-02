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
  return applyUrlUpgrade(best?.url ?? baseline);
}

/** Extract a CSS background-image URL from an element, if any. */
export function backgroundImageUrl(el: Element): string | null {
  const bg = getComputedStyle(el).backgroundImage;
  const match = /url\(["']?([^"')]+)["']?\)/.exec(bg);
  if (!match) return null;
  return resolveUrl(match[1], document.baseURI);
}

/**
 * Read a `<canvas>`'s current contents as a PNG data URL, for sites that
 * render artwork directly to canvas instead of an `<img>` (e.g. some
 * viewers/editors). Cross-origin content drawn without CORS headers taints
 * the canvas and makes `toDataURL()` throw `SecurityError` — that's not
 * recoverable client-side, so it's treated as "no candidate" rather than an
 * error the caller needs to handle.
 */
export function canvasDataUrl(canvas: HTMLCanvasElement): string | null {
  if (canvas.width === 0 || canvas.height === 0) return null;
  try {
    return canvas.toDataURL("image/png");
  } catch {
    return null;
  }
}

/**
 * Per-site thumbnail → likely-original URL upgrade rules (§7.11), kept as a
 * data table rather than one-off code per site so adding a new site is a
 * one-line addition. Applied as a final pass after candidate scoring, since
 * it operates on the resolved URL string rather than any DOM state.
 */
interface UrlUpgradeRule {
  /** Only rules whose pattern matches the URL are attempted. */
  test: RegExp;
  /** Returns the upgraded URL, or throws/returns the input if not applicable. */
  upgrade: (url: string) => string;
}

const URL_UPGRADE_RULES: UrlUpgradeRule[] = [
  // Pixiv: /c/<size>/img-master/.../xxx_master1200.jpg -> img-original, no size suffix.
  {
    test: /\bpximg\.net\/.*\/img-master\//,
    upgrade: (u) =>
      u
        .replace(/\/c\/[^/]+\/img-master\//, "/img-original/")
        .replace("/img-master/", "/img-original/")
        .replace(/_master\d+(\.\w+)(\?.*)?$/, "$1"),
  },
  // Twitter/X media: ?name=small|medium|large|900x900 -> ?name=orig.
  {
    test: /\bpbs\.twimg\.com\/media\//,
    upgrade: (u) => {
      const url = new URL(u);
      url.searchParams.set("name", "orig");
      return url.toString();
    },
  },
  // Danbooru/Gelbooru-style sample images: .../sample/sample-<hash>.jpg -> .../<hash>.jpg
  {
    test: /\/sample\/sample-/,
    upgrade: (u) => u.replace(/\/sample\/sample-/, "/"),
  },
  // Tumblr media: trailing _75/_100/_250/_400/_500/_540 size suffix -> _1280 (largest CDN size).
  {
    test: /media\.tumblr\.com\/.*_(75|100|250|400|500|540)\.\w+(\?.*)?$/,
    upgrade: (u) => u.replace(/_(75|100|250|400|500|540)(\.\w+)(\?.*)?$/, "_1280$2$3"),
  },
  // Generic WordPress-style resized filenames: name-300x200.jpg -> name.jpg
  {
    test: /-\d+x\d+\.\w+(\?.*)?$/,
    upgrade: (u) => u.replace(/-\d+x\d+(\.\w+)(\?.*)?$/, "$1$2"),
  },
];

/** Apply the first matching URL-upgrade rule; returns the input unchanged if none apply. */
export function applyUrlUpgrade(url: string): string {
  for (const rule of URL_UPGRADE_RULES) {
    if (!rule.test.test(url)) continue;
    try {
      const upgraded = rule.upgrade(url);
      if (upgraded && upgraded !== url) return upgraded;
    } catch {
      /* rule didn't apply cleanly to this URL's shape; try the next one */
    }
  }
  return url;
}

export interface HitResult {
  url: string;
  /** The element the URL came from (for visual capture feedback). */
  element: Element;
}

/**
 * Find the best image at a viewport point: prefers <img> elements (with
 * full-res candidate upgrade), then <canvas> renders (art/editor sites that
 * never put a bitmap in an <img> at all), falls back to CSS background
 * images on the element chain.
 */
export function findImageAt(x: number, y: number): HitResult | null {
  const elements = document.elementsFromPoint(x, y);

  for (const el of elements) {
    if (el.tagName === "IMG" && (el as HTMLImageElement).src) {
      return { url: bestImageUrl(el as HTMLImageElement), element: el };
    }
  }
  for (const el of elements) {
    if (el.tagName === "CANVAS") {
      const dataUrl = canvasDataUrl(el as HTMLCanvasElement);
      if (dataUrl) return { url: dataUrl, element: el };
    }
  }
  for (const el of elements) {
    const bg = backgroundImageUrl(el);
    if (bg) return { url: bg, element: el };
  }
  return null;
}
