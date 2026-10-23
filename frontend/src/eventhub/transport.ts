// Transport seam between the EventHub and #875's shared bridge package.
//
// The bridge owns framing, handshake, schema validation and error envelopes;
// the hub only needs decoded event frames. This interface is the whole
// coupling — #875 implements it over the sidecar transport, #876 over the
// HostClient, tests over an in-memory source.

import type { EventHub } from "./hub";

export interface EventTransport {
  /** Register a listener for decoded event frames; returns an unsubscribe. */
  onEvent(listener: (frame: unknown) => void): () => void;
}

/** Pipe a transport's event frames into the hub. Returns a detach function. */
export function attachTransport(hub: EventHub, transport: EventTransport): () => void {
  return transport.onEvent((frame) => {
    hub.ingest(frame);
  });
}
