import React from "react";
import { Settings } from "lucide-react";

interface CloudJobsControlProps {
  badge: string;
  onOpenJobs: () => void;
  onOpenCompute: () => void;
}

/** One header control. Click opens Cloud Jobs. The gear, or shift-click, opens Cloud Compute. */
export function CloudJobsControl({
  badge,
  onOpenJobs,
  onOpenCompute,
}: CloudJobsControlProps): React.ReactElement {
  return (
    <div className="flex items-center">
      <button
        type="button"
        aria-label="Cloud Jobs"
        className="flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-violet-600"
        onClick={(event) => {
          if (event.shiftKey) {
            onOpenCompute();
            return;
          }
          onOpenJobs();
        }}
      >
        <span aria-hidden="true">☁️</span>
        <span data-testid="cloud-jobs-badge">{badge}</span>
      </button>
      <button
        type="button"
        aria-label="Cloud Compute"
        title="Cloud Compute"
        className="rounded-lg p-2 hover:bg-violet-600"
        onClick={onOpenCompute}
      >
        <Settings size={16} />
      </button>
    </div>
  );
}
