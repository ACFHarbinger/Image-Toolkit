/**
 * Client-side perceptual-hash pre-check (§7.16C).
 *
 * Computes a 64-bit DCT-based pHash entirely in the browser (canvas +
 * grayscale + 2D DCT-II + median threshold), matching the algorithm the app
 * server uses (`imagehash.phash`, per
 * https://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html
 * — see `backend/src/core/dir_phash_index.py::compute_phash_bytes`), and
 * sweeps it against a snapshot of the library's hashes cached in
 * `storage.local` (`getPhashSnapshot()`, refreshed periodically or on
 * demand) for an instant, no-round-trip "probably already have this" hint.
 *
 * Caveat, documented rather than hidden: canvas's built-in image resampling
 * (`drawImage` scaling) is not guaranteed to match PIL's `ANTIALIAS`
 * (Lanczos) resize bit-for-bit, so a client-computed hash for the exact same
 * image the server hashed may differ by a few bits rather than exactly zero.
 * This pre-check is explicitly a *hint*, not authoritative — the real
 * duplicate check (`dupCheck()`, §7.6) always re-verifies server-side
 * against the live index before anything is treated as a confirmed
 * duplicate.
 */
import { storageGet, storageSet } from "./api";
import { getPhashSnapshot } from "./bridge";

const HASH_SIZE = 8; // output hash is HASH_SIZE x HASH_SIZE bits (64 total)
const IMG_SIZE = HASH_SIZE * 4; // highfreq_factor=4, matching imagehash.phash's default

const SNAPSHOT_STORAGE_KEY = "phashSnapshot";

export interface PhashSnapshotCache {
  hashes: string[];
  generatedAt: string;
  cachedAt: number;
}

/** 1D DCT-II (scipy.fftpack.dct default: type=2, norm=None — unnormalized). */
function dct1d(input: Float64Array): Float64Array {
  const n = input.length;
  const out = new Float64Array(n);
  for (let k = 0; k < n; k++) {
    let sum = 0;
    for (let x = 0; x < n; x++) {
      sum += input[x] * Math.cos((Math.PI * k * (2 * x + 1)) / (2 * n));
    }
    out[k] = 2 * sum;
  }
  return out;
}

/** Separable 2D DCT-II: 1D DCT along columns (axis 0), then along rows (axis 1). */
function dct2d(matrix: Float64Array[]): Float64Array[] {
  const size = matrix.length;

  // Axis 0: transform each column.
  const afterCols: Float64Array[] = Array.from(
    { length: size },
    () => new Float64Array(size),
  );
  for (let col = 0; col < size; col++) {
    const column = new Float64Array(size);
    for (let row = 0; row < size; row++) column[row] = matrix[row][col];
    const transformed = dct1d(column);
    for (let row = 0; row < size; row++) afterCols[row][col] = transformed[row];
  }

  // Axis 1: transform each row of the column-transformed result.
  const afterRows: Float64Array[] = Array.from(
    { length: size },
    () => new Float64Array(size),
  );
  for (let row = 0; row < size; row++) {
    afterRows[row] = dct1d(afterCols[row]);
  }
  return afterRows;
}

/** PIL's 'L' (grayscale) conversion formula (ITU-R 601-2 luma transform). */
function toGrayscale(imageData: ImageData): Float64Array[] {
  const { data, width, height } = imageData;
  const gray: Float64Array[] = Array.from(
    { length: height },
    () => new Float64Array(width),
  );
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      gray[y][x] = r * 0.299 + g * 0.587 + b * 0.114;
    }
  }
  return gray;
}

/**
 * Compute the 64-bit pHash of an already-decoded image, as a 16-hex-digit
 * lowercase string (matching the server's `f"{phash:016x}"` format).
 */
export function computePhashFromImageBitmap(
  image: ImageBitmap | HTMLImageElement | HTMLCanvasElement,
): string {
  const canvas = new OffscreenCanvas(IMG_SIZE, IMG_SIZE);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2D canvas context unavailable.");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(image, 0, 0, IMG_SIZE, IMG_SIZE);
  const imageData = ctx.getImageData(0, 0, IMG_SIZE, IMG_SIZE);

  const gray = toGrayscale(imageData);
  const dct = dct2d(gray);

  const lowFreq: number[] = [];
  for (let row = 0; row < HASH_SIZE; row++) {
    for (let col = 0; col < HASH_SIZE; col++) {
      lowFreq.push(dct[row][col]);
    }
  }

  const sorted = [...lowFreq].sort((a, b) => a - b);
  const mid = sorted.length / 2;
  const median =
    sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[Math.floor(mid)];

  // Row-major flatten, first element = MSB, matching numpy's
  // `hash.flatten()` + `int(bit_string, 2)` in imagehash's __str__.
  let bits = 0n;
  for (const value of lowFreq) {
    bits = (bits << 1n) | (value > median ? 1n : 0n);
  }
  return bits.toString(16).padStart(16, "0");
}

/** Fetch an image URL and decode it into an ImageBitmap for hashing. */
export async function computePhashFromUrl(imageUrl: string): Promise<string> {
  const resp = await fetch(imageUrl);
  const blob = await resp.blob();
  const bitmap = await createImageBitmap(blob);
  try {
    return computePhashFromImageBitmap(bitmap);
  } finally {
    bitmap.close();
  }
}

/** Popcount of a 64-bit BigInt via an 8-bit lookup table (8 lookups/call). */
const POPCOUNT_TABLE = new Uint8Array(256);
for (let i = 0; i < 256; i++) {
  POPCOUNT_TABLE[i] = (i & 1) + POPCOUNT_TABLE[i >> 1];
}
function hammingDistanceHex(hexA: string, hexB: string): number {
  let xor = BigInt(`0x${hexA}`) ^ BigInt(`0x${hexB}`);
  let count = 0;
  for (let i = 0; i < 8; i++) {
    count += POPCOUNT_TABLE[Number(xor & 0xffn)];
    xor >>= 8n;
  }
  return count;
}

/** Refresh the cached snapshot from the app bridge. Throws BridgeError if unreachable. */
export async function refreshPhashSnapshot(): Promise<PhashSnapshotCache> {
  const result = await getPhashSnapshot();
  const cache: PhashSnapshotCache = {
    hashes: result.hashes,
    generatedAt: result.generated_at,
    cachedAt: Date.now(),
  };
  await storageSet({ [SNAPSHOT_STORAGE_KEY]: cache });
  return cache;
}

interface PhashSnapshotStorage {
  phashSnapshot?: PhashSnapshotCache;
}

export async function getCachedPhashSnapshot(): Promise<PhashSnapshotCache | null> {
  const stored = await storageGet<PhashSnapshotStorage>([SNAPSHOT_STORAGE_KEY]);
  return stored.phashSnapshot ?? null;
}

export interface SnapshotHint {
  /** Lowest Hamming distance found in the cached snapshot (0-64). */
  bestHamming: number;
  /** Convenience boolean: bestHamming <= threshold. */
  probablyDuplicate: boolean;
  /** How many hashes the snapshot held at check time. */
  snapshotSize: number;
}

const DEFAULT_HINT_THRESHOLD = 12; // slightly looser than the server's own
// DEFAULT_THRESHOLD=10, to absorb the canvas-vs-PIL resize mismatch noted
// in the module docstring above -- this is a *hint*, false negatives here
// just mean falling through to the authoritative server check anyway.

/**
 * Sweep a computed hash against the cached snapshot (no network call).
 * Returns `null` if no snapshot has been cached yet (caller should fall
 * back to the authoritative bridge check, or trigger `refreshPhashSnapshot`).
 */
export async function snapshotBestMatch(
  hash: string,
  threshold = DEFAULT_HINT_THRESHOLD,
): Promise<SnapshotHint | null> {
  const cache = await getCachedPhashSnapshot();
  if (!cache || cache.hashes.length === 0) return null;

  let best = 64;
  for (const candidate of cache.hashes) {
    const d = hammingDistanceHex(hash, candidate);
    if (d < best) best = d;
    if (best === 0) break;
  }
  return {
    bestHamming: best,
    probablyDuplicate: best <= threshold,
    snapshotSize: cache.hashes.length,
  };
}
