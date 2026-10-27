import React, { useEffect, useRef, useState } from "react";
import { deskButtonClass, deskControlClass, DeskField, DeskForm } from "../../components/common/DeskForm";
import { ThumbnailGallery } from "../../components/common/ThumbnailGallery";

export interface SimilarityItem {
  readonly path: string;
  readonly width: number;
  readonly height: number;
  readonly ahash: string;
  readonly error: string;
}

export interface SimilarityPair {
  readonly left: string;
  readonly right: string;
  readonly distance: number;
}

export interface SimilarityClient {
  similarityCompare(params: { paths: string[]; threshold: number }): Promise<{
    items: SimilarityItem[];
    pairs: SimilarityPair[];
  }>;
  similarityScan?(params: { directory: string; threshold: number }): Promise<{
    items: SimilarityItem[];
    pairs: SimilarityPair[];
  }>;
  libraryPreviewFrame?(params: { path: string }): Promise<{ png_base64: string; error: string }>;
}

const COMPARE_PATH_CAP = 32;

function splitPaths(raw: string): string[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function unionPaths(left: readonly string[], right: readonly string[]): string[] {
  const seen = new Set<string>();
  const paths: string[] = [];
  for (const path of [...left, ...right]) {
    if (seen.has(path)) {
      continue;
    }
    seen.add(path);
    paths.push(path);
  }
  return paths;
}

function pathsInScan(raw: string, scan: readonly string[]): string[] {
  if (scan.length === 0) {
    return [];
  }
  const members = new Set(scan);
  return splitPaths(raw).filter((path) => members.has(path));
}

function distinctPaths(pairs: readonly SimilarityPair[]): string[] {
  const seen: Record<string, true> = {};
  const paths: string[] = [];
  for (const pair of pairs) {
    if (!seen[pair.left]) {
      seen[pair.left] = true;
      paths.push(pair.left);
    }
    if (!seen[pair.right]) {
      seen[pair.right] = true;
      paths.push(pair.right);
    }
  }
  return paths;
}

function pairRow(pair: SimilarityPair, frames: Readonly<Record<string, string>>): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const sides = [pair.left, pair.right];
  for (let index = 0; index < sides.length; index += 1) {
    const path = sides[index];
    const png = frames[path];
    if (png) {
      nodes.push(
        <img
          key={`${index}:${path}`}
          alt=""
          src={`data:image/png;base64,${png}`}
          className="h-12 w-12 shrink-0 rounded object-cover"
        />,
      );
    }
  }
  nodes.push(`${pair.left} ${pair.right} ${pair.distance}`);
  return nodes;
}

/** Average-hash pairs for caller paths (#904). This view does not delete files. */
export function SimilarityView({ hostClient }: { readonly hostClient: SimilarityClient }): React.ReactElement {
  const [rawPaths, setRawPaths] = useState("");
  const [directory, setDirectory] = useState("");
  const [threshold, setThreshold] = useState(8);
  const [pairs, setPairs] = useState<SimilarityPair[]>([]);
  const [items, setItems] = useState<SimilarityItem[]>([]);
  const [frames, setFrames] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [truncated, setTruncated] = useState(false);
  const [leftScan, setLeftScan] = useState<string[]>([]);
  const [rightScan, setRightScan] = useState<string[]>([]);
  const leftScanRef = useRef<string[]>([]);
  const rightScanRef = useRef<string[]>([]);

  useEffect(() => {
    const load = hostClient.libraryPreviewFrame;
    if (!load) {
      return undefined;
    }
    let active = true;
    const paths = distinctPaths(pairs);
    void (async () => {
      const next: Record<string, string> = {};
      for (const path of paths) {
        if (!active) {
          return;
        }
        try {
          const frame = await load.call(hostClient, { path });
          if (!active) {
            return;
          }
          if (frame.png_base64 !== "" && frame.error === "") {
            next[path] = frame.png_base64;
          }
        } catch {
          if (!active) {
            return;
          }
        }
      }
      // A newer compare or unmount flips `active` before this result is applied.
      if (active) {
        setFrames(next);
      }
    })();
    return () => {
      active = false;
    };
  }, [hostClient, pairs]);

  function rememberScan(side: "left" | "right", paths: string[]): void {
    if (side === "left") {
      leftScanRef.current = paths;
      setLeftScan(paths);
    } else {
      rightScanRef.current = paths;
      setRightScan(paths);
    }
    const union = unionPaths(leftScanRef.current, rightScanRef.current);
    setRawPaths(union.slice(0, COMPARE_PATH_CAP).join("\n"));
    setTruncated(union.length > COMPARE_PATH_CAP);
  }

  function applySideSelection(scan: readonly string[], next: readonly string[], side: "left" | "right"): void {
    const members = new Set(scan);
    const rest = splitPaths(rawPaths).filter((path) => !members.has(path));
    const merged = side === "left" ? unionPaths(next, rest) : unionPaths(rest, next);
    setRawPaths(merged.join("\n"));
  }

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      const result = await hostClient.similarityCompare({ paths: splitPaths(rawPaths), threshold });
      setFrames({});
      setItems(result.items);
      setPairs(result.pairs);
      const failed = result.items.find((item) => item.error);
      if (failed) {
        setError(failed.error);
      }
    } catch (exc) {
      setFrames({});
      setItems([]);
      setPairs([]);
      setError(exc instanceof Error ? exc.message : "compare failed");
    }
  }

  async function onScan(): Promise<void> {
    const scan = hostClient.similarityScan;
    if (!scan) {
      return;
    }
    setError("");
    try {
      const result = await scan.call(hostClient, { directory, threshold });
      setFrames({});
      setItems(result.items);
      setPairs(result.pairs);
      const failed = result.items.find((item) => item.error);
      if (failed) {
        setError(failed.error);
      }
    } catch (exc) {
      setFrames({});
      setItems([]);
      setPairs([]);
      setError(exc instanceof Error ? exc.message : "scan failed");
    }
  }

  return (
    <DeskForm
      testId="similarity-view"
      title="Similarity"
      description="Average-hash pairs. This page does not delete files."
      onSubmit={onSubmit}
    >
      <DeskField label="Directory">
        <input className={deskControlClass} value={directory} onChange={(event) => setDirectory(event.target.value)} />
      </DeskField>
      <button type="button" className={deskButtonClass} onClick={() => void onScan()}>
        Scan directory
      </button>
      <ThumbnailGallery
        multiple
        directoryLabel="Left directory"
        selected={pathsInScan(rawPaths, leftScan)}
        onSelectedChange={(paths) => applySideSelection(leftScan, paths, "left")}
        onScanned={(paths) => rememberScan("left", paths)}
      />
      <ThumbnailGallery
        multiple
        directoryLabel="Right directory"
        selected={pathsInScan(rawPaths, rightScan)}
        onSelectedChange={(paths) => applySideSelection(rightScan, paths, "right")}
        onScanned={(paths) => rememberScan("right", paths)}
      />
      <DeskField label="Images">
        <textarea
          className={deskControlClass}
          rows={4}
          value={rawPaths}
          onChange={(event) => {
            setRawPaths(event.target.value);
            setTruncated(false);
          }}
        />
      </DeskField>
      {truncated ? <p className="text-xs text-it-muted-text">The list was truncated to 32 images.</p> : null}
      <DeskField label="Threshold">
        <input
          className={deskControlClass}
          type="number"
          min={0}
          max={64}
          value={threshold}
          onChange={(event) => setThreshold(Number(event.target.value))}
        />
      </DeskField>
      <button type="submit" className={deskButtonClass}>Compare</button>
      {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
      <ul className="space-y-1 text-sm">
        {pairs.map((pair) => (
          <li key={`${pair.left}:${pair.right}`} className="flex items-center gap-2">{pairRow(pair, frames)}</li>
        ))}
      </ul>
      <ul className="space-y-1 text-sm">
        {items.map((item, index) => (
          <li key={`${item.path}:${index}`}>
            {item.path} {item.width}x{item.height} {item.ahash}
          </li>
        ))}
      </ul>
    </DeskForm>
  );
}
