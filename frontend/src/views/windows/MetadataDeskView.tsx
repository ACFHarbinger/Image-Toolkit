import React, { useState } from "react";
import { ThumbnailGallery } from "../../components/common/ThumbnailGallery";
import { deskButtonClass, deskControlClass, DeskField, DeskForm } from "../../components/common/DeskForm";

export interface MetadataDescribeResult {
  readonly found: boolean;
  readonly path: string;
  readonly name: string;
  readonly size: number;
  readonly suffix: string;
  readonly reason: string;
}

export interface MetadataClient {
  metadataDescribe(params: { path: string }): Promise<MetadataDescribeResult>;
}

/** Name and size of a caller file (#919). library.db is not opened. */
export function MetadataDeskView({ hostClient }: { readonly hostClient: MetadataClient }): React.ReactElement {
  const [path, setPath] = useState("");
  const [result, setResult] = useState<MetadataDescribeResult | null>(null);
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      setResult(await hostClient.metadataDescribe({ path }));
    } catch (exc) {
      setResult(null);
      setError(exc instanceof Error ? exc.message : "metadata failed");
    }
  }

  return (
    <DeskForm testId="metadata-desk" title="File Metadata" description="Name and size of a file. The library database is not opened." onSubmit={onSubmit}>
      <ThumbnailGallery
        multiple={false}
        directoryLabel="Image directory"
        selected={path ? [path] : []}
        onSelectedChange={(paths) => setPath(paths[0] ?? "")}
      />
      <DeskField label="Path">
        <input className={deskControlClass} value={path} onChange={(event) => setPath(event.target.value)} />
      </DeskField>
      <button type="submit" className={deskButtonClass}>Describe</button>
      {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
      {result ? <p className="text-sm">{result.reason}</p> : null}
      {result?.found ? (
        <p className="text-sm">
          {result.name} {result.size} {result.suffix}
        </p>
      ) : null}
    </DeskForm>
  );
}
