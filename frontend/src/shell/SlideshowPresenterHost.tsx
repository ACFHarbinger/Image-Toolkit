import React, { useEffect, useState } from "react";
import { HostClient, RustTransport } from "../hostclient";
import { SlideshowPresenterWindow } from "./SlideshowPresenterWindow";

/** Owns the shell client for the slideshow presenter pop-out (#893). */
export function SlideshowPresenterHost(): React.ReactElement {
  const [client, setClient] = useState<HostClient | null>(null);

  useEffect(() => {
    const next = new HostClient(new RustTransport(), {
      clientName: "slideshow-presenter-window",
      clientVersion: "1.0.0",
    });
    setClient(next);
    void next.connect().catch(() => {});
    return () => {
      void next.close();
    };
  }, []);

  if (!client) {
    return (
      <div
        data-testid="slideshow-presenter-loading"
        className="flex min-h-screen items-center justify-center bg-gray-50 text-gray-500 dark:bg-gray-950 dark:text-gray-400"
      >
        <p>Connecting to Image-Toolkit bridge…</p>
      </div>
    );
  }

  return <SlideshowPresenterWindow hostClient={client} />;
}
