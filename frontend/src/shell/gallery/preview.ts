/** Animated preview is a separate request from the still grid. */
export function requestAnimatedPreview(signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return Promise.reject(new DOMException("animated preview cancelled", "AbortError"));
  }
  return new Promise((resolve, reject) => {
    const onAbort = () => {
      signal.removeEventListener("abort", onAbort);
      reject(new DOMException("animated preview cancelled", "AbortError"));
    };
    signal.addEventListener("abort", onAbort);
  });
}
