import React, { useState } from "react";
import { WorkspaceInfo } from "../types";

interface WorkspacePickerProps {
  lastWorkspace: WorkspaceInfo | null;
  onOpenWorkspace: (info: WorkspaceInfo) => void;
  onBrowse: () => Promise<void>;
}

export const WorkspacePicker: React.FC<WorkspacePickerProps> = ({
  lastWorkspace,
  onOpenWorkspace,
  onBrowse,
}) => {
  const [error, setError] = useState<string | null>(null);

  const handleBrowseClick = async () => {
    try {
      setError(null);
      await onBrowse();
    } catch (err: any) {
      setError(err?.message || String(err));
    }
  };

  return (
    <main className="picker-container">
      <h1>Development Tool</h1>
      <p className="sub">
        Select a workspace repository to monitor. Single repository per
        workspace (D60).
      </p>

      {lastWorkspace && (
        <section>
          <h2>Continue where you left off</h2>
          <button
            className="primary"
            onClick={() => onOpenWorkspace(lastWorkspace)}
          >
            {lastWorkspace.name} ({lastWorkspace.root})
          </button>
        </section>
      )}

      <section>
        <h2>Open a workspace</h2>
        <button onClick={handleBrowseClick}>Choose repository folder&hellip;</button>
        {error && <p className="error-msg">{error}</p>}
      </section>
    </main>
  );
};
