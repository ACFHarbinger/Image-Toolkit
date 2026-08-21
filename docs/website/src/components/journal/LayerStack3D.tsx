import React, { useState } from "react";
import { Orbit, Layers, Sparkles } from "lucide-react";
import "./LayerStack3D.css";

interface LayerStack3DProps {
  title?: string;
  caption?: string;
}

export default function LayerStack3D({
  title = "Interactive 2.5D Cel / Background Layer Stack",
  caption = "Drag to orbit the exploded compositing stack: Background Plate, SAM-2 Alpha Matte, Character Cel, and Unified Composite.",
}: LayerStack3DProps) {
  const [pitch, setPitch] = useState(25);
  const [yaw, setYaw] = useState(-30);
  const [exploded, setExploded] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    setYaw((y) => Math.max(-60, Math.min(60, y + dx * 0.4)));
    setPitch((p) => Math.max(0, Math.min(60, p - dy * 0.4)));
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div className="layer-stack-card">
      <div className="layer-stack-header">
        <div>
          <span className="layer-stack-tag">Explorable Explanation</span>
          <h4 className="layer-stack-title">{title}</h4>
        </div>
        <div className="layer-stack-actions">
          <button
            className={`stack-toggle-btn ${exploded ? "active" : ""}`}
            onClick={() => setExploded(!exploded)}
          >
            <Layers size={14} />
            <span>{exploded ? "Collapse Stack" : "Explode Layers"}</span>
          </button>
        </div>
      </div>

      <div
        className="layer-stack-viewport"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <div className="orbit-hint">
          <Orbit size={13} />
          <span>Click &amp; Drag to Orbit</span>
        </div>

        <div
          className="stage-3d-scene"
          style={{
            transform: `rotateX(${pitch}deg) rotateY(${yaw}deg)`,
          }}
        >
          {/* Layer 1: Background Canvas Plate */}
          <div
            className="layer-plane bg-plane"
            style={{
              transform: exploded ? "translateZ(-80px)" : "translateZ(0px)",
            }}
          >
            <div className="plane-label">1. Synthesized Background Plate (Temporal Median)</div>
            <div className="plane-artwork bg-art" />
          </div>

          {/* Layer 2: Binary SAM-2 Isolation Mask */}
          <div
            className="layer-plane mask-plane"
            style={{
              transform: exploded ? "translateZ(-10px)" : "translateZ(5px)",
            }}
          >
            <div className="plane-label">2. Semantic Alpha Cutout Matte</div>
            <div className="plane-artwork mask-art">
              <div className="mask-silhouette" />
            </div>
          </div>

          {/* Layer 3: Foreground Character Cel */}
          <div
            className="layer-plane cel-plane"
            style={{
              transform: exploded ? "translateZ(60px)" : "translateZ(10px)",
            }}
          >
            <div className="plane-label">3. Registered Foreground Cel</div>
            <div className="plane-artwork cel-art">
              <div className="cel-colored" />
            </div>
          </div>

          {/* Layer 4: Final Composite */}
          <div
            className="layer-plane composite-plane"
            style={{
              transform: exploded ? "translateZ(130px)" : "translateZ(15px)",
            }}
          >
            <div className="plane-label">4. Seam-Blended Panorama Composite</div>
            <div className="plane-artwork composite-art" />
          </div>
        </div>
      </div>

      <div className="layer-stack-footer">
        <div className="stack-status-chips">
          <span className="chip cyan">Pitch: {Math.round(pitch)}&deg;</span>
          <span className="chip emerald">Yaw: {Math.round(yaw)}&deg;</span>
          <span className="chip purple">Perspective: 2.5D Parallax</span>
        </div>
        <p className="layer-stack-caption">{caption}</p>
      </div>
    </div>
  );
}
