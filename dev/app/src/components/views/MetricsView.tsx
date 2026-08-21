import React, { useEffect, useRef } from "react";
import { TimeSeriesData } from "../../types";

interface MetricsViewProps {
  metricsTimeline: {
    rss_memory?: TimeSeriesData;
    coherence_trend?: TimeSeriesData;
  } | null;
}

export const MetricsView: React.FC<MetricsViewProps> = ({ metricsTimeline }) => {
  const rssCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const cohCanvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!metricsTimeline) return;

    // 1. Draw RSS Memory Chart
    const rssCanvas = rssCanvasRef.current;
    if (rssCanvas && metricsTimeline.rss_memory) {
      const ctx = rssCanvas.getContext("2d");
      if (ctx) {
        const rect = rssCanvas.parentElement?.getBoundingClientRect();
        if (rect) {
          rssCanvas.width = rect.width * window.devicePixelRatio;
          rssCanvas.height = 200 * window.devicePixelRatio;
          rssCanvas.style.width = `${rect.width}px`;
          rssCanvas.style.height = `200px`;
        }

        const w = rssCanvas.width;
        const h = rssCanvas.height;
        ctx.clearRect(0, 0, w, h);

        const pts = metricsTimeline.rss_memory.points;

        // Draw 200MB alert line
        const alertY = h - (200.0 / 250.0) * h;
        ctx.strokeStyle = "rgba(244, 63, 94, 0.6)";
        ctx.setLineDash([6, 6]);
        ctx.beginPath();
        ctx.moveTo(0, alertY);
        ctx.lineTo(w, alertY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw memory line
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 3;
        ctx.beginPath();
        pts.forEach((p, idx) => {
          const x = (idx / Math.max(pts.length - 1, 1)) * w;
          const y = h - (p.val / 250.0) * h;
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }
    }

    // 2. Draw Coherence Score Chart
    const cohCanvas = cohCanvasRef.current;
    if (cohCanvas && metricsTimeline.coherence_trend) {
      const ctx = cohCanvas.getContext("2d");
      if (ctx) {
        const rect = cohCanvas.parentElement?.getBoundingClientRect();
        if (rect) {
          cohCanvas.width = rect.width * window.devicePixelRatio;
          cohCanvas.height = 200 * window.devicePixelRatio;
          cohCanvas.style.width = `${rect.width}px`;
          cohCanvas.style.height = `200px`;
        }

        const w = cohCanvas.width;
        const h = cohCanvas.height;
        ctx.clearRect(0, 0, w, h);

        const pts = metricsTimeline.coherence_trend.points;

        ctx.strokeStyle = "#10b981";
        ctx.lineWidth = 3;
        ctx.beginPath();
        pts.forEach((p, idx) => {
          const x = (idx / Math.max(pts.length - 1, 1)) * w;
          const y = h - (p.val / 5.0) * h;
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }
    }
  }, [metricsTimeline]);

  const latestRss =
    metricsTimeline?.rss_memory?.points.slice(-1)[0]?.val.toFixed(1) || "--";
  const latestCoh =
    metricsTimeline?.coherence_trend?.points.slice(-1)[0]?.val.toFixed(2) ||
    "--";

  return (
    <div className="view-metrics-container">
      <div className="metrics-grid">
        <div className="chart-card">
          <h3>
            <span>Process RSS Memory</span>
            <span style={{ color: "#38bdf8" }}>{latestRss} MB</span>
          </h3>
          <canvas ref={rssCanvasRef} className="chart-canvas" />
        </div>

        <div className="chart-card">
          <h3>
            <span>Pipeline Coherence Trend</span>
            <span style={{ color: "#10b981" }}>{latestCoh}</span>
          </h3>
          <canvas ref={cohCanvasRef} className="chart-canvas" />
        </div>
      </div>
    </div>
  );
};
