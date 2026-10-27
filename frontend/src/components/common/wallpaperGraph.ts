/** Move one slideshow path from one monitor's graph onto another. */
export function moveQueuePath(
  queues: Record<string, string[]>,
  path: string,
  fromId: string,
  toId: string,
): Record<string, string[]> {
  if (!path || fromId === toId) {
    return queues;
  }
  const source = queues[fromId] ?? [];
  if (!source.includes(path)) {
    return queues;
  }
  const destination = queues[toId] ?? [];
  return {
    ...queues,
    [fromId]: source.filter((item) => item !== path),
    [toId]: destination.includes(path) ? destination : [...destination, path],
  };
}

export function graphPayload(monitorId: string, path: string): string {
  return `${monitorId}\n${path}`;
}

export function readGraphPayload(raw: string): { monitorId: string; path: string } | null {
  const splitAt = raw.indexOf("\n");
  if (splitAt <= 0) {
    return null;
  }
  const monitorId = raw.slice(0, splitAt);
  const path = raw.slice(splitAt + 1);
  if (!monitorId || !path) {
    return null;
  }
  return { monitorId, path };
}
