/**
 * Single browser-API adapter (§7.2).
 *
 * Firefox exposes the Promise-based `browser` namespace; Chromium exposes the
 * callback-based `chrome` namespace (Promise-based since MV3 for most APIs).
 * All extension code imports from here instead of touching either global.
 */

// Firefox's `browser` global is structurally compatible with `chrome` for the
// subset of APIs this extension uses.
declare const browser: typeof chrome | undefined;

export const api: typeof chrome =
  typeof browser !== "undefined" ? browser : chrome;

export const IS_FIREFOX = typeof browser !== "undefined";

/** Promise wrapper for storage.local.get, uniform across browsers. */
export function storageGet<T extends object>(
  keys: string[] | string,
): Promise<Partial<T>> {
  return new Promise((resolve) => {
    if (IS_FIREFOX) {
      (api.storage.local.get(keys) as Promise<Partial<T>>).then(resolve);
    } else {
      api.storage.local.get(keys, (items) => resolve(items as Partial<T>));
    }
  });
}

/** Promise wrapper for storage.local.set, uniform across browsers. */
export function storageSet(items: Record<string, unknown>): Promise<void> {
  return new Promise((resolve) => {
    if (IS_FIREFOX) {
      (api.storage.local.set(items) as Promise<void>).then(() => resolve());
    } else {
      api.storage.local.set(items, () => resolve());
    }
  });
}
