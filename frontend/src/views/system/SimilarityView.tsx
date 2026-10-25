import React, { useState } from "react";

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
}

function splitPaths(raw: string): string[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

/** Average-hash pairs for caller paths (#904). This view does not delete files. */
export function SimilarityView({ hostClient }: { readonly hostClient: SimilarityClient }): React.ReactElement {
  const [rawPaths, setRawPaths] = useState("");
  const [threshold, setThreshold] = useState(8);
  const [pairs, setPairs] = useState<SimilarityPair[]>([]);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      const result = await hostClient.similarityCompare({ paths: splitPaths(rawPaths), threshold });
      setPairs(result.pairs);
      const failed = result.items.find((item) => item.error);
      if (failed) {
        setError(failed.error);
      }
    } catch (exc) {
      setPairs([]);
      setError(exc instanceof Error ? exc.message : "compare failed");
    }
  }

  return (
    <form data-testid="similarity-view" onSubmit={onSubmit}>
      <label>
        Images
        <textarea value={rawPaths} onChange={(event) => setRawPaths(event.target.value)} />
      </label>
      <label>
        Threshold
        <input
          type="number"
          min={0}
          max={64}
          value={threshold}
          onChange={(event) => setThreshold(Number(event.target.value))}
        />
      </label>
      <button type="submit">Compare</button>
      {error ? <p role="alert">{error}</p> : null}
      <ul>
        {pairs.map((pair) => (
          <li key={`${pair.left}:${pair.right}`}>
            {pair.left} {pair.right} {pair.distance}
          </li>
        ))}
      </ul>
    </form>
  );
}
