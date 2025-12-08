import React, { useState, useRef } from 'react';

interface MarqueeScrollAreaProps {
  children: React.ReactNode;
  // Signal equivalent: (selectedPaths: Set<string>, isCtrlPressed: boolean) => void
  onSelectionChanged?: (selectedPaths: Set<string>, isCtrlPressed: boolean) => void;
}

export const MarqueeScrollArea: React.FC<MarqueeScrollAreaProps> = ({
  children,
  onSelectionChanged,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectionBox, setSelectionBox] = useState<{ startX: number; startY: number; currX: number; currY: number } | null>(null);
  const [lastSelected, setLastSelected] = useState<Set<string>>(new Set());

  const calculateSelection = (box: { startX: number; startY: number; currX: number; currY: number }, isCtrl: boolean) => {
    if (!containerRef.current) return;

    const rectLeft = Math.min(box.startX, box.currX);
    const rectTop = Math.min(box.startY, box.currY);
    const rectWidth = Math.abs(box.currX - box.startX);
    const rectHeight = Math.abs(box.currY - box.startY);

    // This rect is relative to the container's top-left (including scroll)
    const selectionRect = {
      left: rectLeft,
      top: rectTop,
      right: rectLeft + rectWidth,
      bottom: rectTop + rectHeight,
    };

    const containerRect = containerRef.current.getBoundingClientRect();
    const currentSelected = new Set<string>();

    // Find all selectable children (ClickableLabels)
    const selectables = containerRef.current.querySelectorAll('[data-selectable="true"]');

    selectables.forEach((el) => {
      const itemRect = el.getBoundingClientRect();
      const path = el.getAttribute('data-path');

      if (!path) return;

      // Calculate relative position of item within the container
      // We compare against the container's scroll position
      const relativeItem = {
        left: itemRect.left - containerRect.left + containerRef.current!.scrollLeft,
        top: itemRect.top - containerRect.top + containerRef.current!.scrollTop,
        width: itemRect.width,
        height: itemRect.height,
      };

      // Check Intersection
      const isIntersceting = !(
        relativeItem.left > selectionRect.right ||
        relativeItem.left + relativeItem.width < selectionRect.left ||
        relativeItem.top > selectionRect.bottom ||
        relativeItem.top + relativeItem.height < selectionRect.top
      );

      if (isIntersceting) {
        currentSelected.add(path);
      }
    });

    // Optimization: Simple deep compare to avoid spamming the parent
    if (currentSelected.size !== lastSelected.size || ![...currentSelected].every(p => lastSelected.has(p))) {
        setLastSelected(currentSelected);
        onSelectionChanged?.(currentSelected, isCtrl);
    }
  };

  const handlePointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return; // Only Left Click

    // Check if we clicked on a selectable item directly (prevent marquee start)
    let target = e.target as HTMLElement;
    while (target && target !== containerRef.current) {
        if (target.getAttribute('data-selectable') === 'true') {
            return; 
        }
        target = target.parentElement as HTMLElement;
    }

    const rect = containerRef.current!.getBoundingClientRect();
    const startX = e.clientX - rect.left + containerRef.current!.scrollLeft;
    const startY = e.clientY - rect.top + containerRef.current!.scrollTop;

    setSelectionBox({
        startX, startY, currX: startX, currY: startY
    });
    setLastSelected(new Set());
    
    // Capture pointer to handle drags outside the div
    (e.target as Element).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!selectionBox) return;

    const rect = containerRef.current!.getBoundingClientRect();
    const currX = e.clientX - rect.left + containerRef.current!.scrollLeft;
    const currY = e.clientY - rect.top + containerRef.current!.scrollTop;

    const newBox = { ...selectionBox, currX, currY };
    setSelectionBox(newBox);
    calculateSelection(newBox, e.ctrlKey || e.metaKey);
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (selectionBox) {
        setSelectionBox(null);
        setLastSelected(new Set());
        (e.target as Element).releasePointerCapture(e.pointerId);
    }
  };

  // Render Rubber Band
  const renderRubberBand = () => {
    if (!selectionBox) return null;
    const left = Math.min(selectionBox.startX, selectionBox.currX);
    const top = Math.min(selectionBox.startY, selectionBox.currY);
    const width = Math.abs(selectionBox.currX - selectionBox.startX);
    const height = Math.abs(selectionBox.currY - selectionBox.startY);

    return (
        <div style={{
            position: 'absolute',
            left: `${left}px`,
            top: `${top}px`,
            width: `${width}px`,
            height: `${height}px`,
            backgroundColor: 'rgba(88, 101, 242, 0.3)', // Discord blurple-ish
            border: '1px solid #5865f2',
            pointerEvents: 'none', // Let events pass through to scroll area
            zIndex: 100
        }} />
    );
  };

  return (
    <div
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{
        width: '100%',
        height: '100%',
        minHeight: '400px', // Fallback height
        overflow: 'auto',
        border: '1px solid #4f545c',
        backgroundColor: '#2c2f33',
        borderRadius: '8px',
        position: 'relative',
        touchAction: 'none' // Important for Pointer Events
      }}
    >
      {renderRubberBand()}
      <div style={{ position: 'relative', width: '100%', height: '100%' }}>
        {children}
      </div>
    </div>
  );
};