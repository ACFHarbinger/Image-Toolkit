/**
 * Folder resolution and filename templating (§7.10).
 */
import type { ExtensionSettings, SiteRule } from "./settings";

/** Characters illegal in filenames on common filesystems. */
const ILLEGAL = /[<>:"\\|?*]/g;

function sanitizeComponent(s: string): string {
  return s.replace(ILLEGAL, "_").replace(/\//g, "_").trim();
}

/** Match a hostname against a rule pattern with `*` wildcards. */
export function hostMatches(hostname: string, pattern: string): boolean {
  const p = pattern.trim().toLowerCase();
  if (!p) return false;
  const re = new RegExp(
    "^" + p.split("*").map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join(".*") + "$",
  );
  return re.test(hostname.toLowerCase());
}

/**
 * Resolve the Downloads/ subfolder for a capture: first site rule whose
 * pattern matches the page hostname wins; otherwise the global target folder.
 */
export function resolveFolder(
  settings: Pick<ExtensionSettings, "targetFolder" | "siteRules">,
  pageUrl: string | undefined,
): string {
  if (pageUrl) {
    let host = "";
    try {
      host = new URL(pageUrl).hostname;
    } catch {
      /* not a URL */
    }
    if (host) {
      for (const rule of settings.siteRules as SiteRule[]) {
        if (rule.folder && hostMatches(host, rule.pattern)) {
          return rule.folder;
        }
      }
    }
  }
  return settings.targetFolder || "data";
}

/**
 * Build the relative download path from the filename template.
 * Tokens: {name} {ext} {site} {date} {time}. `/` in the template creates
 * subfolders; each path component is sanitized individually.
 */
export function buildFilename(
  template: string,
  imageUrl: string,
  pageUrl: string | undefined,
  now: Date = new Date(),
): string {
  // Original name/extension from the image URL
  let base = "";
  try {
    base = new URL(imageUrl).pathname.split("/").pop() ?? "";
  } catch {
    base = imageUrl.split("/").pop()?.split("?")[0] ?? "";
  }
  base = decodeURIComponent(base);
  const dot = base.lastIndexOf(".");
  let name = dot > 0 ? base.slice(0, dot) : base;
  let ext = dot > 0 ? base.slice(dot + 1).toLowerCase() : "";
  if (!name || name.length > 150) name = `image_${now.getTime()}`;
  if (!ext || ext.length > 5) ext = "jpg";

  let site = "";
  try {
    site = new URL(pageUrl || imageUrl).hostname.replace(/^www\./, "");
  } catch {
    /* keep empty */
  }

  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;

  const tokens: Record<string, string> = { name, ext, site, date, time };
  const raw = (template || "{name}.{ext}").replace(
    /\{(name|ext|site|date|time)\}/g,
    (_m, key: string) => tokens[key] ?? "",
  );

  const parts = raw
    .split("/")
    .map(sanitizeComponent)
    .filter((p) => p.length > 0);
  const result = parts.join("/");
  return result || `image_${now.getTime()}.jpg`;
}
