/** Framework-neutral island helpers with no UI-runtime imports. */

export function logIslandMount(framework: string, elementId?: string): void {
  console.log(`[Island Architecture] Mounted ${framework} island${elementId ? ` at #${elementId}` : ""}.`);
}

export function logIslandUnmount(framework: string, elementId?: string): void {
  console.log(`[Island Architecture] Unmounted ${framework} island${elementId ? ` at #${elementId}` : ""}.`);
}

export function generateIslandId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).substring(2, 9)}`;
}
