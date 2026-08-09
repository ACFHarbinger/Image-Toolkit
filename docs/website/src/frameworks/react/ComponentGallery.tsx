import React, { useState } from "react";
import Modal from "../../../../../frontend/src/components/common/Modal";
import ToggleButtonGroup from "../../../../../frontend/src/components/common/ToggleButtonGroup";
import CollapsibleSection from "../../../../../frontend/src/components/common/CollapsibleSection";
import FormRow from "../../../../../frontend/src/components/common/FormRow";
import { ClickableLabel } from "../../../../../frontend/src/components/common/ClickableLabel";

/**
 * Live catalogue of Image-Toolkit's *real* desktop-app components, imported
 * directly from frontend/src/components/common/ (no copy, no port) — the
 * same components are documented (with hand-written argTypes) by Storybook,
 * see ../../../stories/. This file is the island that actually mounts them
 * inside the docs site; Storybook mounts them in isolation for review.
 */
const FORMATS = ["png", "webp", "jpg", "avif"];

export function ComponentGallery() {
  const [selected, setSelected] = useState<Set<string>>(new Set(["png", "webp"]));
  const [modalOpen, setModalOpen] = useState(false);
  const [labelSelected, setLabelSelected] = useState(false);

  function toggleFormat(item: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(item) ? next.delete(item) : next.add(item);
      return next;
    });
  }

  return (
    <div className="component-gallery">
      <CollapsibleSection title="convert --output_format (ToggleButtonGroup)" startOpen>
        <FormRow label="Output formats">
          <ToggleButtonGroup items={FORMATS} selectedItems={selected} onToggle={toggleFormat} />
        </FormRow>
        <FormRow label="Thumbnail (ClickableLabel)">
          <ClickableLabel
            path="wallpaper_001.webp"
            isSelected={labelSelected}
            onPathClicked={() => setLabelSelected((v) => !v)}
          />
        </FormRow>
        <FormRow label="Modal preview">
          <button type="button" className="gallery-btn" onClick={() => setModalOpen(true)}>
            Open success Modal
          </button>
        </FormRow>
      </CollapsibleSection>

      <Modal
        isVisible={modalOpen}
        type="success"
        content={`Conversion queued for: ${Array.from(selected).join(", ") || "(none selected)"}`}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}

export default ComponentGallery;
