import { BarChart3, Box, Cpu, Layers, LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  box: Box,
  layers: Layers,
  chart: BarChart3,
  cpu: Cpu,
};

export function iconFor(name: string): LucideIcon {
  return ICONS[name] ?? Box;
}

/** Same marks the Qt rail uses, so both shells read as one catalog. */
export const CATEGORY_MARK: Record<string, string> = {
  "System Tools": "⚙️",
  "Library Database": "📚",
  "Web Integration": "🌐",
  "Deep Learning": "⚡",
  "Image Stitching": "✂️",
  Manga: "🎨",
  "Image Editor": "🖌️",
  "Developer / Diagnostics": "🛠️",
};
