import React, { useState } from "react";
import { Play, Pause, RotateCcw, ShieldAlert, CheckCircle2 } from "lucide-react";
import "./HoldTimelineSlider.css";

interface HoldTimelineSliderProps {
  title?: string;
  caption?: string;
}

export default function HoldTimelineSlider({
  title = "Interactive Cel-Pose Timeline & Hold Selection",
  caption = "Scrub through animated camera frames to observe how hold block detection isolates clean foreground cels without ghosting.",
}: HoldTimelineSliderProps) {
  const [currentFrame, setCurrentFrame] = useState(3);
  const [selectedHold, setSelectedHold] = useState<number>(1);
  const [isPlaying, setIsPlaying] = useState(false);

  const frames = [
    { id: 1, hold: 1, label: "Frame 01 (Hold 1 - Anticipation)", isKey: true, celPose: "pose-a" },
    { id: 2, hold: 1, label: "Frame 02 (Hold 1 - Anticipation)", isKey: false, celPose: "pose-a" },
    { id: 3, hold: 1, label: "Frame 03 (Hold 1 - Selected Key)", isKey: true, celPose: "pose-a" },
    { id: 4, hold: 2, label: "Frame 04 (Hold 2 - In-between)", isKey: false, celPose: "pose-b" },
    { id: 5, hold: 2, label: "Frame 05 (Hold 2 - Extreme)", isKey: true, celPose: "pose-b" },
    { id: 6, hold: 3, label: "Frame 06 (Hold 3 - Settle)", isKey: false, celPose: "pose-c" },
    { id: 7, hold: 3, label: "Frame 07 (Hold 3 - Settle)", isKey: true, celPose: "pose-c" },
  ];

  const activeFrame = frames[currentFrame - 1];

  return (
    <div className="hold-timeline-card">
      <div className="hold-timeline-header">
        <div>
          <span className="hold-timeline-tag">Explorable Explanation</span>
          <h4 className="hold-timeline-title">{title}</h4>
        </div>
        <div className="hold-badge-group">
          <span className={`hold-chip ${activeFrame.hold === selectedHold ? "active" : "inactive"}`}>
            {activeFrame.hold === selectedHold ? (
              <>
                <CheckCircle2 size={13} />
                <span>Optimal Hold Selected</span>
              </>
            ) : (
              <>
                <ShieldAlert size={13} />
                <span>Pose Drift Risk</span>
              </>
            )}
          </span>
        </div>
      </div>

      <div className="hold-timeline-preview">
        <div className="canvas-frame-preview">
          <div className="camera-viewport-box">
            <span className="viewport-label">Camera Frame {activeFrame.id}</span>
            <div className={`animated-cel ${activeFrame.celPose}`}>
              <div className="cel-head" />
              <div className="cel-torso" />
              <div className="cel-arm" />
            </div>
          </div>
          <div className="composite-accumulator-box">
            <span className="viewport-label">Composite Accumulator</span>
            <div className="accumulated-canvas">
              <div className="bg-pan-plate" style={{ transform: `translateY(-${(currentFrame - 1) * 20}px)` }} />
              {activeFrame.hold === selectedHold ? (
                <div className="isolated-clean-cel">
                  <div className="cel-head" />
                  <div className="cel-torso" />
                  <div className="cel-arm" />
                </div>
              ) : (
                <div className="ghosted-multi-pose">
                  <div className="ghost-layer pose-a" />
                  <div className="ghost-layer pose-b" />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="hold-timeline-controls">
        <div className="timeline-track">
          {frames.map((f) => (
            <button
              key={f.id}
              className={`timeline-frame-node ${f.id === currentFrame ? "active" : ""} ${f.hold === selectedHold ? "in-hold" : ""}`}
              onClick={() => setCurrentFrame(f.id)}
            >
              <span className="frame-num">F{f.id}</span>
              <span className="frame-type">{f.isKey ? "Key" : "Hold"}</span>
            </button>
          ))}
        </div>

        <div className="hold-selector-bar">
          <span className="selector-title">Target Hold Partition:</span>
          <div className="hold-buttons">
            {[1, 2, 3].map((h) => (
              <button
                key={h}
                className={`hold-btn ${selectedHold === h ? "selected" : ""}`}
                onClick={() => setSelectedHold(h)}
              >
                Hold Group #{h}
              </button>
            ))}
          </div>
        </div>

        <p className="hold-caption">{caption}</p>
      </div>
    </div>
  );
}
