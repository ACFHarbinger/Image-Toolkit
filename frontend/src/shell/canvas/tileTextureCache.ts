// Tile texture pipeline for the shared canvas host (Y-00 / #902).
//
// Productionizes the S-02 spike's deferred piece (#888 / PR #950): visible
// tiles resolve to asset:// URLs under the render-cache scope and are
// uploaded into the renderer's GL texture set on demand. The cache is
// LRU-bounded with in-flight dedupe so a pan/zoom burst over a
// 50,000 × 30,000 document never queues one request per tile, and eviction
// frees the GL texture, not just the JS entry.

import type { ResolvedTile } from "./cullWorker";

export type TileTextureSource = TexImageSource;

export type TileTextureLoader = (url: string) => Promise<TileTextureSource>;

export interface TileTextureStats {
  entries: number;
  inFlight: number;
  hits: number;
  misses: number;
  evictions: number;
  loadFailures: number;
}

export interface TileTextureCacheOptions {
  /** Maximum cached sources; the least recently used beyond this evict. */
  maxEntries?: number;
  /** Source factory; the default decodes an HTMLImageElement from the URL. */
  loader?: TileTextureLoader;
  /** Fires when an entry leaves the cache (the GL texture must be freed). */
  onEvict?: (url: string) => void;
}

const DEFAULT_MAX_ENTRIES = 256;

/** Browser loader: decode() when available so the first paint never blocks on layout. */
export function createImageLoader(): TileTextureLoader {
  return (url: string) =>
    new Promise<TileTextureSource>((resolve, reject) => {
      const image = new Image();
      image.decoding = "async";
      image.onload = () => {
        if (typeof image.decode === "function") {
          void image.decode().then(() => resolve(image), () => resolve(image));
        } else {
          resolve(image);
        }
      };
      image.onerror = () => reject(new Error(`tile texture failed to load: ${url}`));
      image.src = url;
    });
}

interface CacheEntry {
  source: TileTextureSource;
  /** Monotonic touch counter for LRU ordering without list splices. */
  touched: number;
}

/**
 * LRU-bounded async cache of decoded tile sources.
 *
 * `get` only touches (it never starts a load); `load` dedupes concurrent
 * requests for the same URL, and a failed load counts as a miss so callers
 * can fall back to the renderer's placeholder.
 */
export class TileTextureCache {
  private readonly maxEntries: number;
  private readonly loader: TileTextureLoader;
  private readonly onEvict?: (url: string) => void;
  private readonly entries = new Map<string, CacheEntry>();
  private readonly inFlight = new Map<string, Promise<TileTextureSource | null>>();
  private touchCounter = 0;
  private counters: TileTextureStats = {
    entries: 0,
    inFlight: 0,
    hits: 0,
    misses: 0,
    evictions: 0,
    loadFailures: 0,
  };

  constructor(options: TileTextureCacheOptions = {}) {
    this.maxEntries = Math.max(1, options.maxEntries ?? DEFAULT_MAX_ENTRIES);
    this.loader = options.loader ?? createImageLoader();
    this.onEvict = options.onEvict;
  }

  /** The cached source for a resolved tile's URL, or null (no load started). */
  get(url: string): TileTextureSource | null {
    const entry = this.entries.get(url);
    if (!entry) {
      this.counters.misses += 1;
      return null;
    }
    entry.touched = ++this.touchCounter;
    this.counters.hits += 1;
    return entry.source;
  }

  /** True when a load for this URL is already in flight. */
  isLoading(url: string): boolean {
    return this.inFlight.has(url);
  }

  /**
   * Load (or join) the texture for one URL. Resolves null on failure or
   * when the load raced a `clear()`; never rejects.
   */
  load(url: string): Promise<TileTextureSource | null> {
    const cached = this.get(url);
    if (cached) {
      return Promise.resolve(cached);
    }
    const pending = this.inFlight.get(url);
    if (pending) {
      return pending;
    }
    const request = this.loader(url)
      .then((source) => {
        this.store(url, source);
        return source;
      })
      .catch(() => {
        this.counters.loadFailures += 1;
        return null;
      })
      .finally(() => {
        this.inFlight.delete(url);
        this.counters.inFlight = this.inFlight.size;
      });
    this.inFlight.set(url, request);
    this.counters.inFlight = this.inFlight.size;
    return request;
  }

  private store(url: string, source: TileTextureSource): void {
    if (this.inFlight.has(url) === false && this.entries.has(url)) {
      return; // a concurrent store already won
    }
    this.entries.set(url, { source, touched: ++this.touchCounter });
    while (this.entries.size > this.maxEntries) {
      let oldestUrl: string | null = null;
      let oldestTouch = Number.POSITIVE_INFINITY;
      for (const [key, entry] of this.entries) {
        if (entry.touched < oldestTouch) {
          oldestTouch = entry.touched;
          oldestUrl = key;
        }
      }
      if (oldestUrl === null) {
        break;
      }
      this.entries.delete(oldestUrl);
      this.counters.evictions += 1;
      this.onEvict?.(oldestUrl);
    }
    this.counters.entries = this.entries.size;
  }

  /** The set of visible-tile URLs that are neither cached nor in flight. */
  pendingFor(tiles: readonly ResolvedTile[]): string[] {
    return tiles.filter((tile) => !this.entries.has(tile.assetUrl) && !this.inFlight.has(tile.assetUrl)).map((tile) => tile.assetUrl);
  }

  stats(): TileTextureStats {
    return { ...this.counters, entries: this.entries.size, inFlight: this.inFlight.size };
  }

  /** Drop everything; fires onEvict per entry so GL textures are freed. */
  clear(): void {
    for (const url of [...this.entries.keys()]) {
      this.entries.delete(url);
      this.onEvict?.(url);
    }
    this.counters.entries = 0;
  }
}
