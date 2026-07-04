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

/** All content images on the page (icons and tracking pixels filtered out). */
export function collectImages(minPx: number = MIN_MEDIA_PX): string[] {
  const urls: string[] = [];
  const seen = new Set<string>();
  for (const img of document.querySelectorAll<HTMLImageElement>("img")) {
    const dim = Math.max(
      img.naturalWidth,
      img.naturalHeight,
      img.clientWidth,
      img.clientHeight,
    );
    if (dim < minPx) continue;
    const url = bestImageUrl(img);
    if (!url || !isDownloadableUrl(url) || seen.has(url)) continue;
    seen.add(url);
    urls.push(url);
  }
  return urls;
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
