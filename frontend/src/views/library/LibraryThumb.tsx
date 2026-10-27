import { useEffect, useState, type ReactElement } from "react";

interface PreviewFrame {
  readonly png_base64: string;
  readonly error: string;
}

interface FrameClient {
  libraryPreviewFrame?(params: { path: string }): Promise<PreviewFrame>;
}

/** Still from library_preview.frame. Call the client method so `this` stays bound. */
export function LibraryThumb({
  path,
  hostClient,
}: {
  readonly path: string;
  readonly hostClient: FrameClient;
}): ReactElement | null {
  const [src, setSrc] = useState("");
  useEffect(() => {
    const load = hostClient.libraryPreviewFrame;
    if (typeof load !== "function") {
      return undefined;
    }
    let cancelled = false;
    setSrc("");
    void load.call(hostClient, { path }).then(
      (frame) => {
        if (cancelled) {
          return;
        }
        if (frame.error || !frame.png_base64) {
          setSrc("");
          return;
        }
        setSrc(`data:image/png;base64,${frame.png_base64}`);
      },
      () => {
        if (!cancelled) {
          setSrc("");
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [path, hostClient]);
  if (!src) {
    return null;
  }
  return <img src={src} alt="" className="h-12 w-12 shrink-0 rounded object-cover" />;
}
