// The Transport interface all HostClient adapters implement (W0-12, #876).

export interface Transport {
  /** Send one contract method call; resolves with the decoded result. */
  request(method: string, params?: Record<string, unknown>): Promise<unknown>;
  /** Release the underlying channel; in-flight requests reject. */
  close(): void;
}
