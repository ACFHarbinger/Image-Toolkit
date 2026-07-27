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
  typeof browser !== "undefined"
    ? (browser as typeof chrome)
    : typeof chrome !== "undefined"
      ? chrome
      : (undefined as unknown as typeof chrome); // non-browser (test) context

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

/**
 * Promise wrapper for runtime.sendNativeMessage (§7.5B), uniform across
 * browsers. Firefox returns a Promise natively; Chromium is callback-based
 * and reports host-launch failures via `chrome.runtime.lastError` rather
 * than rejecting, so that path is normalized into a rejection here too.
 */
export function sendNativeMessage<T>(
  hostName: string,
  message: object,
): Promise<T> {
  return new Promise((resolve, reject) => {
    if (IS_FIREFOX) {
      (api.runtime.sendNativeMessage(hostName, message) as Promise<T>).then(
        resolve,
        reject,
      );
    } else {
      api.runtime.sendNativeMessage(hostName, message, (response) => {
        const err = api.runtime.lastError;
        if (err) {
          reject(new Error(err.message ?? "Native messaging host error."));
        } else {
          resolve(response as T);
        }
      });
    }
  });
}
