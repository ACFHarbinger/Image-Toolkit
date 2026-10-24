import React from "react";

/** Setup surface opened from the header gear or a shift-click. Settings stay on their own row. */
export function CloudComputeSurface({ onClose }: { onClose: () => void }): React.ReactElement {
  return (
    <section data-testid="cloud-compute-surface" className="flex flex-col gap-3 p-6">
      <h2 className="text-xl font-semibold">Cloud Compute</h2>
      <p>Provider account setup stays on this surface.</p>
      <button type="button" onClick={onClose}>
        Back
      </button>
    </section>
  );
}
