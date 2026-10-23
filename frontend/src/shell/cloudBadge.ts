export interface CloudJobsSummary {
  running: number;
  reserved_usd: number;
  available: boolean;
}

/** Header text. An unavailable projection is a dash, not a fake zero. */
export function formatCloudBadge(summary: CloudJobsSummary): string {
  if (!summary.available) {
    return "—";
  }
  return `${summary.running} · $${summary.reserved_usd.toFixed(2)}`;
}
