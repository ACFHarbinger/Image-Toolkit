import React from "react";
import { FlameGraphData, FlameNodeData, MetaGraphData } from "../../types";

interface FlameGraphViewProps {
  flameGraph: FlameGraphData | null;
  metaGraph: MetaGraphData | null;
  onSelectEntity: (entity: any) => void;
}

export const FlameGraphView: React.FC<FlameGraphViewProps> = ({
  flameGraph,
  metaGraph,
  onSelectEntity,
}) => {
  if (!flameGraph || !flameGraph.tree) {
    return (
      <div className="view-flame-container">
        <p style={{ color: "#9ca3af" }}>No telemetry flame data recorded yet.</p>
      </div>
    );
  }

  const totalTime = flameGraph.total_time_ms || 100.0;

  const renderFlameNode = (node: FlameNodeData, depth = 0): React.ReactNode => {
    const pct = ((node.value / totalTime) * 100).toFixed(1);

    const handleClick = () => {
      if (
        node.meta_node_id &&
        metaGraph &&
        metaGraph.nodes[node.meta_node_id]
      ) {
        onSelectEntity(metaGraph.nodes[node.meta_node_id]);
      } else {
        onSelectEntity({
          id: node.name,
          layer: "core",
          kind: node.category,
          latency_ms: node.value,
          call_count: 1,
        });
      }
    };

    return (
      <React.Fragment key={`${node.name}-${depth}-${node.start_ms}`}>
        <div className="flame-row">
          <div
            className={`flame-box cat-${node.category || "lifecycle"}`}
            style={{ width: `${Math.max(parseFloat(pct), 5)}%` }}
            title={`${node.name}\nDuration: ${node.value.toFixed(2)}ms\nSelf-Time: ${node.self_time_ms.toFixed(2)}ms\nCategory: ${node.category}`}
            onClick={handleClick}
          >
            {node.name} ({node.value.toFixed(1)}ms)
          </div>
        </div>
        {node.children &&
          node.children.map((child) => renderFlameNode(child, depth + 1))}
      </React.Fragment>
    );
  };

  return (
    <div className="view-flame-container">
      <div className="flame-container">
        <h3 style={{ marginBottom: "1rem", fontSize: "1rem" }}>
          Execution Call Stack Flame Tree (Total: {totalTime.toFixed(1)}ms)
        </h3>
        <div>{renderFlameNode(flameGraph.tree)}</div>
      </div>
    </div>
  );
};
