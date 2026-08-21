import React, { useEffect, useRef, useState } from "react";
import { MetaGraphData, MetaNode } from "../../types";

interface GalaxyViewProps {
  metaGraph: MetaGraphData | null;
  selectedEntity: any;
  onSelectEntity: (entity: any) => void;
}

export const GalaxyView: React.FC<GalaxyViewProps> = ({
  metaGraph,
  selectedEntity,
  onSelectEntity,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [camera, setCamera] = useState({
    rotX: 0.35,
    rotY: -0.6,
    zoom: 1.0,
    targetY: 0,
  });

  const isDragging = useRef(false);
  const lastMousePos = useRef({ x: 0, y: 0 });
  const photonOffset = useRef(0);

  const resetCamera = () => {
    setCamera({ rotX: 0.35, rotY: -0.6, zoom: 1.0, targetY: 0 });
  };

  const focusLayer = (y: number) => {
    setCamera((prev) => ({ ...prev, targetY: y, rotX: 0.1 }));
  };

  const project3D = (
    x: number,
    y: number,
    z: number,
    width: number,
    height: number
  ) => {
    const cosY = Math.cos(camera.rotY);
    const sinY = Math.sin(camera.rotY);
    const cosX = Math.cos(camera.rotX);
    const sinX = Math.sin(camera.rotX);

    const x1 = x * cosY - z * sinY;
    const z1 = z * cosY + x * sinY;

    const adjY = y - camera.targetY;
    const y2 = adjY * cosX - z1 * sinX;
    const z2 = z1 * cosX + adjY * sinX;

    const fov = 400 * camera.zoom;
    const depth = z2 + 250;
    const scale = depth > 10 ? fov / depth : 1;

    const px = width / 2 + x1 * scale;
    const py = height / 2 - y2 * scale;

    return { px, py, scale, depth };
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "f" || e.key === "F") resetCamera();
      else if (e.key === "1") focusLayer(35);
      else if (e.key === "2") focusLayer(0);
      else if (e.key === "3") focusLayer(-35);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    let animationFrameId: number;

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas || !metaGraph) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const rect = canvas.parentElement?.getBoundingClientRect();
      if (rect) {
        if (
          canvas.width !== rect.width * window.devicePixelRatio ||
          canvas.height !== rect.height * window.devicePixelRatio
        ) {
          canvas.width = rect.width * window.devicePixelRatio;
          canvas.height = rect.height * window.devicePixelRatio;
          canvas.style.width = `${rect.width}px`;
          canvas.style.height = `${rect.height}px`;
        }
      }

      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Cosmic background planes
      ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
      ctx.lineWidth = 1;
      for (let gy = -40; gy <= 40; gy += 35) {
        const p1 = project3D(-160, gy, 0, w, h);
        const p2 = project3D(160, gy, 0, w, h);
        ctx.beginPath();
        ctx.moveTo(p1.px, p1.py);
        ctx.lineTo(p2.px, p2.py);
        ctx.stroke();
      }

      // Animated photon pulses along edges
      photonOffset.current = (photonOffset.current + 0.015) % 1.0;
      const nodes = metaGraph.nodes;
      const edges = metaGraph.edges;

      for (const e of Object.values(edges)) {
        const src = nodes[e.source_id];
        const tgt = nodes[e.target_id];
        if (!src || !tgt) continue;

        const pSrc = project3D(
          src.position[0],
          src.position[1],
          src.position[2],
          w,
          h
        );
        const pTgt = project3D(
          tgt.position[0],
          tgt.position[1],
          tgt.position[2],
          w,
          h
        );

        ctx.strokeStyle = "rgba(56, 189, 248, 0.25)";
        ctx.lineWidth = Math.max(1, 1.5 * pSrc.scale);
        ctx.beginPath();
        ctx.moveTo(pSrc.px, pSrc.py);
        ctx.lineTo(pTgt.px, pTgt.py);
        ctx.stroke();

        const pulseX =
          pSrc.px + (pTgt.px - pSrc.px) * photonOffset.current;
        const pulseY =
          pSrc.py + (pTgt.py - pSrc.py) * photonOffset.current;
        ctx.fillStyle = "#38bdf8";
        ctx.beginPath();
        ctx.arc(pulseX, pulseY, 3 * pSrc.scale, 0, Math.PI * 2);
        ctx.fill();
      }

      // Nodes
      for (const n of Object.values(nodes)) {
        const p = project3D(
          n.position[0],
          n.position[1],
          n.position[2],
          w,
          h
        );
        const isSelected = selectedEntity && selectedEntity.id === n.id;

        let color = "#10b981";
        if (n.layer === "frontend") color = "#06b6d4";
        else if (n.layer === "native") color = "#f59e0b";

        // Halo
        const r = Math.max(4, (isSelected ? 14 : 9) * p.scale);
        const grad = ctx.createRadialGradient(
          p.px,
          p.py,
          r * 0.2,
          p.px,
          p.py,
          r * 2.2
        );
        grad.addColorStop(0, color);
        grad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(p.px, p.py, r * 2.2, 0, Math.PI * 2);
        ctx.fill();

        // Core
        ctx.fillStyle = isSelected ? "#ffffff" : color;
        ctx.beginPath();
        ctx.arc(p.px, p.py, r, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = isSelected ? "#38bdf8" : "#e2e8f0";
        ctx.font = `${Math.max(10, Math.round(11 * p.scale))}px monospace`;
        ctx.textAlign = "center";
        ctx.fillText(n.label, p.px, p.py - r - 6);
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animationFrameId);
  }, [metaGraph, camera, selectedEntity]);

  const handleMouseDown = (e: React.MouseEvent) => {
    isDragging.current = true;
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastMousePos.current.x;
    const dy = e.clientY - lastMousePos.current.y;
    setCamera((prev) => ({
      ...prev,
      rotY: prev.rotY + dx * 0.006,
      rotX: prev.rotX + dy * 0.006,
    }));
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setCamera((prev) => ({
      ...prev,
      zoom: Math.max(0.3, Math.min(prev.zoom * (e.deltaY > 0 ? 0.9 : 1.1), 3.5)),
    }));
  };

  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas || !metaGraph) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = (e.clientX - rect.left) * window.devicePixelRatio;
    const clickY = (e.clientY - rect.top) * window.devicePixelRatio;

    for (const n of Object.values(metaGraph.nodes)) {
      const p = project3D(
        n.position[0],
        n.position[1],
        n.position[2],
        canvas.width,
        canvas.height
      );
      const dist = Math.hypot(clickX - p.px, clickY - p.py);
      if (dist < 20 * p.scale) {
        onSelectEntity(n);
        break;
      }
    }
  };

  return (
    <div className="view-surface active" style={{ position: "relative" }}>
      <div className="view-overlay-controls">
        <button onClick={resetCamera} title="Fit Camera Frame (F)">
          Fit Frame (F)
        </button>
        <button onClick={() => focusLayer(35)} title="Frontend Layer (+Y)">
          Frontend (1)
        </button>
        <button onClick={() => focusLayer(0)} title="Core Layer (Y=0)">
          Core (2)
        </button>
        <button onClick={() => focusLayer(-35)} title="Native Layer (-Y)">
          Native (3)
        </button>
      </div>

      <canvas
        ref={canvasRef}
        className="galaxy-canvas"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        onClick={handleClick}
      />

      <div className="hud-legend">
        <div className="legend-item">
          <span className="legend-dot dot-frontend"></span> +Y: Frontend / Host
        </div>
        <div className="legend-item">
          <span className="legend-dot dot-core"></span> Y=0: Python Core /
          Models
        </div>
        <div className="legend-item">
          <span className="legend-dot dot-native"></span> -Y: C++ Native / SIMD
        </div>
      </div>
    </div>
  );
};
