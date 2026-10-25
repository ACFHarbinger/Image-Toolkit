import { describe, expect, test, vi } from "vitest";
import { TileTextureCache } from "./tileTextureCache";

function fakeSource(name: string) {
  return { fake: name } as unknown as TexImageSource;
}

function deferredLoader() {
  const calls: string[] = [];
  const resolvers = new Map<string, ((source: TexImageSource | null) => void)[]>();
  const loader = (url: string) =>
    new Promise<TexImageSource>((resolve, reject) => {
      calls.push(url);
      const entry = resolvers.get(url) ?? [];
      entry.push((source) => (source ? resolve(fakeSource(url)) : reject(new Error(url))));
      resolvers.set(url, entry);
    });
  const resolve = (url: string) => (resolvers.get(url) ?? []).forEach((fn) => fn(fakeSource(url)));
  const fail = (url: string) => (resolvers.get(url) ?? []).forEach((fn) => fn(null));
  return { loader, calls, resolve, fail };
}

describe("TileTextureCache", () => {
  test("loads once, dedupes concurrent requests for the same URL", async () => {
    const { loader, calls, resolve } = deferredLoader();
    const cache = new TileTextureCache({ loader });

    const first = cache.load("asset://t/a_L0_0_0.jpg");
    const second = cache.load("asset://t/a_L0_0_0.jpg");
    resolve("asset://t/a_L0_0_0.jpg");

    expect(await first).toBe(await second);
    expect(calls).toEqual(["asset://t/a_L0_0_0.jpg"]);
    expect(cache.stats().loadFailures).toBe(0);
    // A read after the load is a hit, not a new load.
    expect(cache.get("asset://t/a_L0_0_0.jpg")).not.toBeNull();
    expect(cache.stats().hits).toBe(1);
  });

  test("failed loads resolve null and stay retryable", async () => {
    const { loader, fail, resolve } = deferredLoader();
    const cache = new TileTextureCache({ loader });

    const failed = await new Promise((done) => {
      cache.load("asset://t/bad.jpg").then(done);
      fail("asset://t/bad.jpg");
    });
    expect(failed).toBeNull();
    expect(cache.stats().loadFailures).toBe(1);

    const retried = new Promise((done) => {
      cache.load("asset://t/bad.jpg").then(done);
      resolve("asset://t/bad.jpg");
    });
    expect(await retried).not.toBeNull();
  });

  test("LRU eviction beyond the budget fires onEvict in use order", async () => {
    const evicted: string[] = [];
    const { loader, resolve } = deferredLoader();
    const cache = new TileTextureCache({ loader, maxEntries: 2, onEvict: (url) => evicted.push(url) });

    const one = cache.load("asset://t/1.jpg");
    resolve("asset://t/1.jpg");
    await one;
    const two = cache.load("asset://t/2.jpg");
    resolve("asset://t/2.jpg");
    await two;
    // Touch 1 so 2 becomes the least recently used.
    cache.get("asset://t/1.jpg");
    const three = cache.load("asset://t/3.jpg");
    resolve("asset://t/3.jpg");
    await three;

    expect(evicted).toEqual(["asset://t/2.jpg"]);
    expect(cache.stats().entries).toBe(2);
    expect(cache.stats().evictions).toBe(1);
    expect(cache.get("asset://t/2.jpg")).toBeNull();
  });

  test("pendingFor reports only unresolved tile URLs", async () => {
    const { loader, resolve } = deferredLoader();
    const cache = new TileTextureCache({ loader });
    const tiles = [
      "asset://t/a.jpg",
      "asset://t/b.jpg",
      "asset://t/c.jpg",
    ].map((url) => ({ assetUrl: url, key: url, layerId: "L", level: 0, col: 0, row: 0, cachePath: url, docRect: { x: 0, y: 0, width: 1, height: 1 } }));

    const loadA = cache.load(tiles[0].assetUrl);
    resolve(tiles[0].assetUrl);
    await loadA;

    expect(cache.pendingFor(tiles)).toEqual(["asset://t/b.jpg", "asset://t/c.jpg"]);

    const loadB = cache.load(tiles[1].assetUrl);
    expect(cache.pendingFor(tiles)).toEqual(["asset://t/c.jpg"]);
    resolve(tiles[1].assetUrl);
    await loadB;
  });

  test("clear fires onEvict for every entry", async () => {
    const evicted: string[] = [];
    const { loader, resolve } = deferredLoader();
    const cache = new TileTextureCache({ loader, onEvict: (url) => evicted.push(url) });
    for (const url of ["asset://t/1.jpg", "asset://t/2.jpg"]) {
      const done = cache.load(url);
      resolve(url);
      await done;
    }
    cache.clear();
    expect(evicted.sort()).toEqual(["asset://t/1.jpg", "asset://t/2.jpg"]);
    expect(cache.stats().entries).toBe(0);
  });
});
