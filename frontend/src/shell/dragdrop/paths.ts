/**
 * Inbound drop validation for the S-05 drag-and-drop spike (#891).
 *
 * Pure path/file gatekeeping: no Tauri imports, no DOM. The injected
 * `stat`/`realpath` pair keeps every filesystem touch fakeable in tests
 * and lets production swap in `@tauri-apps/plugin-fs` later without
 * touching the rules below.
 *
 * The extension allowlist mirrors the Qt converter contract
 * (`SUPPORTED_IMG_FORMATS` in middleware/src/constants/app.py:5 — the
 * frontend copy in src/constants.ts is stale: it lacks tiff/avif); the
 * webview must not admit files the middleware converter would refuse.
 */

/** Image extensions the middleware converter accepts, lowercase, no dot. */
export const SUPPORTED_IMPORT_EXTENSIONS: readonly string[] = [
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "bmp",
  "tiff",
  "avif",
];

export const DEFAULT_MAX_FILE_BYTES = 512 * 1024 * 1024; // 512 MiB
export const DEFAULT_MAX_BATCH_ITEMS = 256;
export const DEFAULT_MAX_BATCH_BYTES = 2 * 1024 * 1024 * 1024; // 2 GiB

/** The subset of fs.Stats the validator cares about. */
export interface DropFsStat {
  readonly bytes: number;
  readonly isFile: boolean;
  readonly isDirectory: boolean;
  readonly isSymlink: boolean;
  readonly isSocket: boolean;
  readonly isFifo: boolean;
}

/** Injected filesystem pair (see module header for why this is not fs/promises). */
export interface DropFs {
  stat(path: string): Promise<DropFsStat>;
  realpath(path: string): Promise<string>;
}

export interface ValidateDropOptions {
  readonly fs: DropFs;
  /** Per-file size ceiling. Default 512 MiB. */
  readonly maxBytes?: number;
  /** Override of SUPPORTED_IMPORT_EXTENSIONS (lowercase, no dots). */
  readonly extensions?: readonly string[];
}

export interface DropValidation {
  readonly ok: boolean;
  /** Normalized path (symlinks resolved to their target). */
  readonly path: string;
  readonly reason?: string;
  /** File size in bytes; present only when ok. */
  readonly bytes?: number;
}

const MAX_SYMLINK_DEPTH = 8;

function reject(path: string, reason: string): DropValidation {
  return { ok: false, path, reason };
}

function allowedSet(extensions: readonly string[] | undefined): Set<string> {
  const source = extensions ?? SUPPORTED_IMPORT_EXTENSIONS;
  return new Set(source.map((ext) => ext.toLowerCase()));
}

/**
 * Best-effort syntactic key for dedup. Returns null for paths that can
 * never validate (relative, NUL, traversal) so the full validator can
 * produce the precise rejection reason.
 */
function dedupKey(raw: string): string | null {
  if (raw.length === 0 || raw.includes("\0") || !raw.startsWith("/")) return null;
  if (raw.split("/").includes("..")) return null;
  return "/" + raw.split("/").filter((seg) => seg.length > 0 && seg !== ".").join("/");
}

/**
 * Validate a single dropped path: absolute POSIX path, no NUL bytes, no
 * `..` segments (absolute paths cannot escape the root, so traversal is
 * redundant noise and gets rejected rather than collapsed), `.` segments
 * collapsed, extension allowlist (case-insensitive), then an injected
 * stat rejecting directories/sockets/FIFOs and oversized files.
 * Symlinks are resolved through the injected realpath and the resolved
 * target must re-pass the same extension and size checks — a symlink
 * whose target flips the extension (e.g. `link.png` -> `/etc/passwd`)
 * is rejected.
 */
export function validateDropPath(
  rawPath: string,
  opts: ValidateDropOptions,
): Promise<DropValidation> {
  return validatePathInternal(rawPath, opts, 0);
}

async function validatePathInternal(
  rawPath: string,
  opts: ValidateDropOptions,
  depth: number,
): Promise<DropValidation> {
  if (rawPath.length === 0) return reject(rawPath, "empty path");
  if (rawPath.includes("\0")) return reject(rawPath, "path contains a NUL byte");
  if (!rawPath.startsWith("/")) return reject(rawPath, "path is not absolute");
  const segments = rawPath.split("/");
  if (segments.includes("..")) {
    return reject(rawPath, "parent traversal (`..`) is not allowed");
  }
  const collapsed = segments.filter((seg) => seg.length > 0 && seg !== ".");
  const basename = collapsed[collapsed.length - 1] ?? "";
  if (basename.length === 0 || basename === "." || basename === "..") {
    return reject(rawPath, "missing filename");
  }
  const dot = basename.lastIndexOf(".");
  if (dot < 0) return reject(rawPath, "missing extension");
  const stem = dot > 0 ? basename.slice(0, dot) : "";
  if (stem.length === 0) return reject(rawPath, "missing filename stem");
  const ext = basename.slice(dot + 1).toLowerCase();
  if (!allowedSet(opts.extensions).has(ext)) {
    return reject(rawPath, `unsupported extension ".${ext}"`);
  }
  const normalized = "/" + collapsed.join("/");
  return validateFs(normalized, opts, depth);
}

async function validateFs(
  path: string,
  opts: ValidateDropOptions,
  depth: number,
): Promise<DropValidation> {
  if (depth >= MAX_SYMLINK_DEPTH) {
    return reject(path, "too many levels of symbolic links");
  }
  let stat: DropFsStat;
  try {
    stat = await opts.fs.stat(path);
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    return reject(path, `filesystem error: ${detail}`);
  }
  if (stat.isDirectory) return reject(path, "directories cannot be imported");
  if (stat.isSocket) return reject(path, "sockets cannot be imported");
  if (stat.isFifo) return reject(path, "FIFOs cannot be imported");
  if (stat.isSymlink) {
    let resolved: string;
    try {
      resolved = await opts.fs.realpath(path);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      return reject(path, `realpath failed: ${detail}`);
    }
    const retargeted = await validatePathInternal(resolved, opts, depth + 1);
    if (!retargeted.ok) {
      return reject(path, `symlink target rejected: ${retargeted.reason ?? "unknown"}`);
    }
    return { ok: true, path: retargeted.path, bytes: retargeted.bytes };
  }
  if (!stat.isFile) return reject(path, "not a regular file");
  const maxBytes = opts.maxBytes ?? DEFAULT_MAX_FILE_BYTES;
  if (stat.bytes > maxBytes) {
    return reject(path, `file size ${stat.bytes} exceeds ${maxBytes} byte limit`);
  }
  return { ok: true, path, bytes: stat.bytes };
}

export interface PlannedDrop {
  /** Normalized, symlink-resolved source path. */
  readonly path: string;
  readonly bytes: number;
}

export interface RejectedDrop {
  /** The path exactly as it was offered. */
  readonly path: string;
  readonly reason: string;
}

export interface DropPlan {
  readonly accepted: readonly PlannedDrop[];
  readonly rejected: readonly RejectedDrop[];
}

export interface PlanDropOptions {
  readonly fs: DropFs;
  /** Per-file ceiling passed through to validateDropPath. Default 512 MiB. */
  readonly maxBytesPerFile?: number;
  /** Maximum accepted items. Default 256. */
  readonly maxItems?: number;
  /** Total bytes across the batch. Default 2 GiB. */
  readonly maxTotalBytes?: number;
  readonly extensions?: readonly string[];
}

/**
 * Batch-plan a drop: dedup after syntactic normalization (duplicates are
 * reported, not silently dropped), cap the accepted count (default 256),
 * validate each survivor, and enforce a total-bytes budget (default
 * 2 GiB). The budget latches: once an item is refused for exceeding it,
 * later items are refused too — a partial-batch import is worse than an
 * obvious cut-off for the user to retry.
 */
export async function planDrop(
  paths: readonly string[],
  opts: PlanDropOptions,
): Promise<DropPlan> {
  const accepted: PlannedDrop[] = [];
  const rejected: RejectedDrop[] = [];
  const seen = new Map<string, string>();
  const maxItems = opts.maxItems ?? DEFAULT_MAX_BATCH_ITEMS;
  const maxTotal = opts.maxTotalBytes ?? DEFAULT_MAX_BATCH_BYTES;
  let spent = 0;
  let budgetExhausted = false;
  let capReached = false;
  for (const raw of paths) {
    const key = dedupKey(raw);
    if (key !== null && seen.has(key)) {
      rejected.push({ path: raw, reason: `duplicate of ${seen.get(key)}` });
      continue;
    }
    if (key !== null) seen.set(key, raw);
    if (capReached) {
      rejected.push({ path: raw, reason: `batch item cap ${maxItems} reached` });
      continue;
    }
    if (budgetExhausted) {
      rejected.push({ path: raw, reason: "batch byte budget exhausted by earlier items" });
      continue;
    }
    const verdict = await validateDropPath(raw, {
      fs: opts.fs,
      maxBytes: opts.maxBytesPerFile,
      extensions: opts.extensions,
    });
    if (!verdict.ok || verdict.bytes === undefined) {
      rejected.push({ path: raw, reason: verdict.reason ?? "unknown rejection" });
      continue;
    }
    if (spent + verdict.bytes > maxTotal) {
      budgetExhausted = true;
      rejected.push({ path: raw, reason: `batch byte budget ${maxTotal} exceeded` });
      continue;
    }
    spent += verdict.bytes;
    accepted.push({ path: verdict.path, bytes: verdict.bytes });
    if (accepted.length >= maxItems) capReached = true;
  }
  return { accepted, rejected };
}
