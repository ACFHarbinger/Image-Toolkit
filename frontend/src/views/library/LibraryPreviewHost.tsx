import React, { useEffect, useState } from "react";
import { HostClient, RustTransport } from "../../hostclient";
import { LibraryPreviewWindow } from "./LibraryPreviewWindow";

/** Owns the shell client for the library.preview pop-out. */
export function LibraryPreviewHost(): React.ReactElement {
  const [client, setClient] = useState<HostClient | null>(null);

  useEffect(() => {
    const next = new HostClient(new RustTransport(), {
      clientName: "library-preview-window",
      clientVersion: "1.0.0",
    });
    setClient(next);
    void next.connect().catch(() => {});
    return () => {
      void next.close();
    };
  }, []);

  if (!client) {
    return <p data-testid="library-preview-status">Connecting to the bridge…</p>;
  }
  return <LibraryPreviewWindow client={client} />;
}
