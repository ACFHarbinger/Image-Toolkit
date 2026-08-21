export interface MetaNode {
  id: string;
  label: string;
  layer: "frontend" | "core" | "native";
  kind: string;
  cluster_id?: string;
  loc?: number;
  complexity?: number;
  latency_ms?: number;
  call_count?: number;
  error_count?: number;
  position: [number, number, number];
}

export interface MetaEdge {
  id: string;
  source_id: string;
  target_id: string;
  kind: string;
  volume?: number;
  latency_ms?: number;
}

export interface MetaGraphData {
  nodes: Record<string, MetaNode>;
  edges: Record<string, MetaEdge>;
}

export interface FlameNodeData {
  name: string;
  value: number;
  self_time_ms: number;
  category: string;
  meta_node_id?: string;
  start_ms: number;
  end_ms: number;
  children: FlameNodeData[];
}

export interface FlameGraphData {
  total_time_ms: number;
  tree: FlameNodeData;
}

export interface TimePointData {
  t_ms: number;
  val: number;
  tag?: string;
}

export interface TimeSeriesData {
  name: string;
  unit: string;
  alert_threshold?: number;
  min_val: number;
  max_val: number;
  avg_val: number;
  points: TimePointData[];
}

export interface StageState {
  stage_id: string;
  stage_name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  active_duration_ms: number;
}

export interface PipelineStageEvent {
  id: string;
  stage_name: string;
  start_ms: number;
  end_ms: number;
  status: string;
  metrics: Record<string, number>;
}

export interface PipelineSessionData {
  session: {
    session_id: string;
    pipeline_name: string;
    start_time_ms: number;
    end_time_ms: number;
    stages: PipelineStageEvent[];
  };
  evaluation: {
    timestamp_ms: number;
    relative_progress: number;
    stages: StageState[];
    active_stage_ids: string[];
    completed_stage_ids: string[];
  };
}

export interface CameraBookmark {
  id: string;
  label: string;
  position: [number, number, number];
  target: [number, number, number];
  fov?: number;
  pinned_node_id?: string;
  investigation_id?: string;
  created_at: string;
}

export interface WorldStateData {
  workspace: string;
  camera: CameraBookmark;
  nodes: Record<string, any>;
  bookmarks: CameraBookmark[];
  filters: {
    show_frontend: boolean;
    show_core: boolean;
    show_native: boolean;
    min_latency_ms: number;
    search_query: string;
  };
}

export interface WorkspaceInfo {
  name: string;
  root: string;
}
