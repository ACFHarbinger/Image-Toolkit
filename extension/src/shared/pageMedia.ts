/**
 * Page-wide media collection for the bulk grabber (§7.9).
 *
 * Collects downloadable image and video URLs from the current document:
 * images go through the §7.11 extractor for full-resolution candidates;
 * videos contribute their direct sources (`src` / `<source>` children).
 * blob: URLs (MediaSource streams) are skipped — they are page-scoped and
 * cannot be fetched by the downloads API.
 */
import { bestImageUrl } from "./extractor";

/** Minimum rendered or natural dimension for an image to count as content. */
export const MIN_MEDIA_PX = 64;

function isDownloadableUrl(url: string): boolean {
  return (
    url.startsWith("http:") ||
    url.startsWith("https:") ||
    url.startsWith("data:")
  );
}

/** One detected image on the page, with the dimensions used for size filtering. */
export interface PageImageItem {
  url: string;
  /** max(naturalWidth, clientWidth) — the larger of rendered/intrinsic size. */
  width: number;
  /** max(naturalHeight, clientHeight). */
  height: number;
}

/**
 * All content images on the page (icons and tracking pixels filtered out),
 * with per-image dimensions — feeds the §7.9 grid-preview page's size filter.
 */
export function collectImageDetails(minPx: number = MIN_MEDIA_PX): PageImageItem[] {
  const items: PageImageItem[] = [];
  const seen = new Set<string>();
  for (const img of document.querySelectorAll<HTMLImageElement>("img")) {
    const width = Math.max(img.naturalWidth, img.clientWidth);
    const height = Math.max(img.naturalHeight, img.clientHeight);
    if (Math.max(width, height) < minPx) continue;
    const url = bestImageUrl(img);
    if (!url || !isDownloadableUrl(url) || seen.has(url)) continue;
    seen.add(url);
    items.push({ url, width, height });
  }
  return items;
}

/** All content images on the page (icons and tracking pixels filtered out). */
export function collectImages(minPx: number = MIN_MEDIA_PX): string[] {
  return collectImageDetails(minPx).map((item) => item.url);
}

/** All directly-downloadable video sources on the page. */
export function collectVideos(): string[] {
  const urls: string[] = [];
  const seen = new Set<string>();
  const push = (url: string | null | undefined) => {
    if (!url || !isDownloadableUrl(url) || seen.has(url)) return;
    seen.add(url);
    urls.push(url);
  };
  for (const video of document.querySelectorAll<HTMLVideoElement>("video")) {
    push(video.currentSrc);
    push(video.src);
    for (const source of video.querySelectorAll("source")) {
      push(source.src);
    }
  }
  return urls;
}

export interface PageMedia {
  images: string[];
  videos: string[];
}

export function collectPageMedia(minPx: number = MIN_MEDIA_PX): PageMedia {
  return { images: collectImages(minPx), videos: collectVideos() };
}
