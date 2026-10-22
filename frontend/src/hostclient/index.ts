// HostClient package public surface (W0-12, #876).

export { HostClientError } from "./errors";
export { HostClient, type Transports } from "./hostclient";
export { HttpTransport, type HttpTransportOptions } from "./http";
export { OPERATION_MANIFEST, type OperationRow, type TransportKind } from "./manifest";
export { RustTransport, type InvokeFn } from "./rust";
export { SidecarTransport, type SidecarTransportOptions, type StdioChannel } from "./sidecar";
export type { Transport } from "./transport";
export { BRIDGE_PROTOCOL_NAME, BRIDGE_PROTOCOL_VERSION } from "./types";
