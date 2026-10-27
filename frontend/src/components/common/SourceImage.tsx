import { useEffect, useRef, useState, type ImgHTMLAttributes } from "react";
import { invoke } from "@tauri-apps/api/core";

interface Frame {
  png_base64: string;
  width: number;
  height: number;
  error: string;
}

/** Source files stay outside the asset scope; Python returns bounded preview pixels. */
export function SourceImage({ path, onDimensions, ...props }: Omit<ImgHTMLAttributes<HTMLImageElement>, "src"> & {
  path: string;
  onDimensions?: (width: number, height: number) => void;
}) {
  const [frame, setFrame] = useState<{ path: string; src: string } | null>(null);
  const dimensions = useRef(onDimensions);
  dimensions.current = onDimensions;
  useEffect(() => {
    let active = true;
    void invoke<Frame>("media_subtab", { action: "preview", params: { path } }).then((result) => {
      if (!active || result.error || !result.png_base64) return;
      setFrame({ path, src: `data:image/png;base64,${result.png_base64}` });
      dimensions.current?.(result.width, result.height);
    }, () => undefined);
    return () => { active = false; };
  }, [path]);
  return frame?.path === path ? <img {...props} src={frame.src} /> : null;
}
