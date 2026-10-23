import { invoke } from "@tauri-apps/api/core";

export function popOut(role: string): Promise<void> {
  return invoke("window_popout", { role });
}

export function hideAllWindows(): Promise<void> {
  return invoke("window_hide_all");
}

export function restoreWindows(): Promise<void> {
  return invoke("window_restore");
}

export function focusWindow(role: string): Promise<void> {
  return invoke("window_focus", { role });
}
