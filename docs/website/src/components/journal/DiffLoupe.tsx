import React, { useState, useRef } from "react";
import { ZoomIn, Layers } from "lucide-react";
import "./DiffLoupe.css";

interface DiffLoupeProps {
  title?: string;
  caption?: string;
  leftLabel?: string;
  rightLabel?: string;
}

export default function DiffLoupe({
  title = "Interactive Seam & Flow Comparator",
  caption = "Hover and drag across the canvas to inspect microscopic pixel alignment, seam discontinuities, and optical flow vectors.",
  leftLabel = "Neural ASP (Composite)",
  rightLabel = "Classical SCANS (Stitched)",
}: DiffLoupeProps) {
  const [sliderPos, setSliderPos] = useState(50);
  const [zoomActive, setZoomActive] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 50, y: 50 });
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));
    setMousePos({ x, y });
  };

  const handleSliderDrag = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSliderPos(Number(e.target.value));
  };

  return (
    <div className="diff-loupe-card">
      <div className="diff-loupe-header">
        <div className="diff-loupe-title-group">
          <span className="diff-loupe-tag">Explorable Explanation</span>
          <h4 className="diff-loupe-title">{title}</h4>
        </div>
        <div className="diff-loupe-actions">
          <button
            className={`diff-mode-btn ${zoomActive ? "active" : ""}`}
            onClick={() => setZoomActive(!zoomActive)}
            title="Toggle Magnifier Loupe"
          >
            <ZoomIn size={14} />
            <span>2.5x Seam Loupe</span>
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className={`diff-loupe-viewport ${zoomActive ? "loupe-active" : ""}`}
        onMouseMove={handleMouseMove}
      >
        {/* Synthetic Layer Simulation: Left (Neural ASP) */}
        <div className="diff-layer diff-left" style={{ clipPath: `inset(0 ${100 - sliderPos}% 0 0)` }}>
          <div className="synthetic-cel-canvas asp-view">
            <div className="synth-bg-grid" />
            <div className="synth-gradient-pan neural" />
            <div className="synth-character-cel asp-cel">
              <div className="cel-hair" />
              <div className="cel-face" />
              <div className="cel-eye left" />
              <div className="cel-eye right" />
            </div>
            <div className="flow-vectors-overlay">
              <span className="flow-dot" style={{ top: "40%", left: "30%" }} />
              <span className="flow-dot" style={{ top: "60%", left: "55%" }} />
              <span className="flow-dot" style={{ top: "35%", left: "70%" }} />
            </div>
          </div>
          <span className="view-badge left">{leftLabel}</span>
        </div>

        {/* Synthetic Layer Simulation: Right (Classical SCANS) */}
        <div className="diff-layer diff-right">
          <div className="synthetic-cel-canvas scans-view">
            <div className="synth-bg-grid" />
            <div className="synth-gradient-pan scans" />
            <div className="synth-character-cel scans-cel torn">
              <div className="cel-hair torn-part" />
              <div className="cel-face torn-part" />
              <div className="cel-eye left" />
              <div className="cel-eye right ghosted" />
            </div>
            <div className="seam-line-indicator" style={{ top: "48%" }} />
          </div>
          <span className="view-badge right">{rightLabel}</span>
        </div>

        {/* Divider Slider Handle */}
        <div className="diff-slider-line" style={{ left: `${sliderPos}%` }}>
          <div className="diff-slider-knob">
            <Layers size={12} />
          </div>
        </div>

        {/* 2.5x Loupe Magnifier */}
        {zoomActive && (
          <div
            className="diff-magnifier"
            style={{
              left: `${mousePos.x}%`,
              top: `${mousePos.y}%`,
              transform: "translate(-50%, -50%)",
            }}
          >
            <div
              className="magnifier-content"
              style={{
                transform: `scale(2.5) translate(${-mousePos.x + 20}%, ${-mousePos.y + 20}%)`,
              }}
            >
              <div className="synthetic-cel-canvas asp-view">
                <div className="synth-character-cel asp-cel" />
              </div>
            </div>
            <div className="magnifier-reticle" />
          </div>
        )}
      </div>

      <div className="diff-loupe-footer">
        <div className="slider-control-row">
          <span className="slider-label">{leftLabel}</span>
          <input
            type="range"
            min="0"
            max="100"
            value={sliderPos}
            onChange={handleSliderDrag}
            className="diff-range-slider"
            aria-label="Split Position Slider"
          />
          <span className="slider-label">{rightLabel}</span>
        </div>
        <p className="diff-caption">{caption}</p>
      </div>
    </div>
  );
}
