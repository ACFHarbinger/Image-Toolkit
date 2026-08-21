import React from "react";
import { PipelineSessionData } from "../../types";

interface PipelineScrubberViewProps {
  pipelineSession: PipelineSessionData | null;
  currentTimeMs: number;
  maxTimeMs: number;
  isPlaying: boolean;
  onPlayToggle: () => void;
  onTimeChange: (timeMs: number) => void;
  onSelectEntity: (entity: any) => void;
}

export const PipelineScrubberView: React.FC<PipelineScrubberViewProps> = ({
  pipelineSession,
  currentTimeMs,
  maxTimeMs,
  isPlaying,
  onPlayToggle,
  onTimeChange,
  onSelectEntity,
}) => {
  if (!pipelineSession || !pipelineSession.session) {
    return (
      <div className="view-scrubber-container">
        <p style={{ color: "#9ca3af" }}>No active pipeline session.</p>
      </div>
    );
  }

  const stages = pipelineSession.session.stages;
  const evalData = pipelineSession.evaluation;
  const stageStatesMap: Record<string, any> = {};
  if (evalData && evalData.stages) {
    evalData.stages.forEach((s) => (stageStatesMap[s.stage_id] = s));
  }

  return (
    <div className="view-scrubber-container">
      <div className="pipeline-stages-flow">
        {stages.map((stage) => {
          const st = stageStatesMap[stage.id] || {
            status: "pending",
            progress: 0,
          };

          return (
            <div
              key={stage.id}
              className={`stage-card ${st.status}`}
              onClick={() =>
                onSelectEntity({
                  id: stage.id,
                  layer: "core",
                  kind: "pipeline_stage",
                  latency_ms: stage.end_ms - stage.start_ms,
                  call_count: 1,
                })
              }
            >
              <div className="stage-header">
                <span className="stage-name">{stage.stage_name}</span>
                <span className={`stage-status-tag tag-${st.status}`}>
                  {st.status} ({(st.progress * 100).toFixed(0)}%)
                </span>
              </div>
              <div className="stage-progress-bar">
                <div
                  className="stage-progress-fill"
                  style={{ width: `${st.progress * 100}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="transport-bar">
        <div className="transport-controls">
          <button
            onClick={onPlayToggle}
            className="primary"
            title={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? "⏸ Pause" : "▶ Play"}
          </button>
          <button
            onClick={() => onTimeChange(Math.max(0, currentTimeMs - 10))}
            title="Step Back 10ms"
          >
            ⏮ -10ms
          </button>
          <button
            onClick={() =>
              onTimeChange(Math.min(maxTimeMs, currentTimeMs + 10))
            }
            title="Step Forward 10ms"
          >
            ⏭ +10ms
          </button>
          <button onClick={() => onTimeChange(0)} title="Reset to start">
            ↺ Reset
          </button>
        </div>

        <input
          type="range"
          className="time-scrub-slider"
          min={0}
          max={maxTimeMs}
          step={5}
          value={currentTimeMs}
          onChange={(e) => onTimeChange(parseFloat(e.target.value))}
        />

        <div className="time-readout">
          {currentTimeMs.toFixed(1)} ms / {maxTimeMs.toFixed(1)} ms
        </div>
      </div>
    </div>
  );
};
