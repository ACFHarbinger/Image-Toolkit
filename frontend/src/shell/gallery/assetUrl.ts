import { convertFileSrc } from "@tauri-apps/api/core";

/** Matches the default-deny scope in tauri.conf.json. Originals never match. */
export const RENDER_CACHE_SEGMENT = "/.image-toolkit/cache/render/";

export function renderCacheAssetUrl(cachePath: string): string | null {
  const normalized = cachePath.replaceAll("\\", "/");
  if (!normalized || normalized.includes("..")) {
    return null;
  }
  const marker = normalized.indexOf(RENDER_CACHE_SEGMENT);
  if (marker < 0) {
    return null;
  }
  const rest = normalized.slice(marker + RENDER_CACHE_SEGMENT.length);
  if (!rest || rest.startsWith("/") || rest.endsWith("/")) {
    return null;
  }
  return convertFileSrc(cachePath);
}
