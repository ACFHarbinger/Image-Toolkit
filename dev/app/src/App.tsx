import React, { useEffect, useState } from "react";
import {
  CameraBookmark,
  FlameGraphData,
  MetaGraphData,
  PipelineSessionData,
  TimeSeriesData,
  WorkspaceInfo,
  WorldStateData,
} from "./types";
import { AppHeader } from "./components/AppHeader";
import { WorkspacePicker } from "./components/WorkspacePicker";
import { GalaxyView } from "./components/views/GalaxyView";
import { FlameGraphView } from "./components/views/FlameGraphView";
import { MetricsView } from "./components/views/MetricsView";
import { PipelineScrubberView } from "./components/views/PipelineScrubberView";
import { SideDrawerInspector } from "./components/inspector/SideDrawerInspector";

const invoke = async (cmd: string, args: any = {}): Promise<any> => {
  const w = window as any;
  if (w.__TAURI__ && w.__TAURI__.core) {
    return w.__TAURI__.core.invoke(cmd, args);
  }
  return {};
};

const openDialog = async (options: any = {}): Promise<any> => {
  const w = window as any;
  if (w.__TAURI__ && w.__TAURI__.dialog) {
    return w.__TAURI__.dialog.open(options);
  }
  return null;
};

export const App: React.FC = () => {
  const [workspace, setWorkspace] = useState<WorkspaceInfo | null>(null);
  const [lastWorkspace, setLastWorkspace] = useState<WorkspaceInfo | null>(
    null
  );
  const [activeView, setActiveView] = useState<string>("view-galaxy");
  const [sidecarStatus, setSidecarStatus] = useState<string>("Connecting...");
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(true);

  // Core Data
  const [metaGraph, setMetaGraph] = useState<MetaGraphData | null>(null);
  const [flameGraph, setFlameGraph] = useState<FlameGraphData | null>(null);
  const [metricsTimeline, setMetricsTimeline] = useState<{
    rss_memory?: TimeSeriesData;
    coherence_trend?: TimeSeriesData;
  } | null>(null);
  const [pipelineSession, setPipelineSession] =
    useState<PipelineSessionData | null>(null);
  const [worldState, setWorldState] = useState<WorldStateData | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<any>(null);

  // Scrubber State
  const [currentTimeMs, setCurrentTimeMs] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const maxTimeMs = 1100;

  useEffect(() => {
    invoke("get_last_workspace").then((last) => {
      if (last && last.root) {
        setLastWorkspace(last);
      }
    });
  }, []);

  const loadData = async () => {
    try {
      const [records, artifacts, gRes, fRes, mRes, pRes, wRes] =
        await Promise.all([
          invoke("list_records"),
          invoke("list_artifacts"),
          invoke("get_meta_graph"),
          invoke("get_flame_graph"),
          invoke("get_metrics_timeline"),
          invoke("get_pipeline_scrubber", { tMs: currentTimeMs }),
          invoke("get_world_state"),
        ]);

      setSidecarStatus(
        `Sidecar up • ${records?.length || 0} records • ${artifacts?.length || 0} artifacts`
      );
      setMetaGraph(gRes?.graph || null);
      setFlameGraph(fRes || null);
      setMetricsTimeline(mRes || null);
      setPipelineSession(pRes || null);
      setWorldState(wRes || null);
    } catch (err: any) {
      setSidecarStatus(`Sidecar error: ${err}`);
    }
  };

  const handleOpenWorkspace = (info: WorkspaceInfo) => {
    setWorkspace(info);
    loadData();
  };

  const handleBrowse = async () => {
    const dir = await openDialog({
      directory: true,
      multiple: false,
      title: "Choose a repository",
    });
    if (dir) {
      const info = await invoke("select_workspace", { path: dir });
      handleOpenWorkspace(info);
    }
  };

  const handleSelectEntity = (entity: any) => {
    setSelectedEntity(entity);
    setIsDrawerOpen(true);
  };

  const handleSaveBookmark = async (label: string) => {
    if (!worldState) return;
    const bm: CameraBookmark = {
      id: `bm-${Date.now().toString(16)}`,
      label: label || "Vantage Bookmark",
      position: [0.0, 40.0, 90.0],
      target: [0.0, 0.0, 0.0],
      pinned_node_id: selectedEntity?.id || undefined,
      created_at: new Date().toISOString(),
    };

    const nextState = {
      ...worldState,
      bookmarks: [...(worldState.bookmarks || []), bm],
    };
    setWorldState(nextState);
    await invoke("save_world_state", { worldState: nextState });
  };

  const handleSelectBookmark = (bm: CameraBookmark) => {
    if (bm.pinned_node_id && metaGraph && metaGraph.nodes[bm.pinned_node_id]) {
      handleSelectEntity(metaGraph.nodes[bm.pinned_node_id]);
    }
  };

  // Pipeline playback loop
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentTimeMs((prev) => {
        const next = prev + 15;
        return next > maxTimeMs ? 0 : next;
      });
    }, 40);
    return () => clearInterval(interval);
  }, [isPlaying]);

  useEffect(() => {
    if (workspace && activeView === "view-scrubber") {
      invoke("get_pipeline_scrubber", { tMs: currentTimeMs }).then((res) => {
        setPipelineSession(res);
      });
    }
  }, [currentTimeMs, activeView, workspace]);

  if (!workspace) {
    return (
      <WorkspacePicker
        lastWorkspace={lastWorkspace}
        onOpenWorkspace={handleOpenWorkspace}
        onBrowse={handleBrowse}
      />
    );
  }

  return (
    <div className="workspace-container">
      <AppHeader
        workspace={workspace}
        activeView={activeView}
        sidecarStatus={sidecarStatus}
        isDrawerOpen={isDrawerOpen}
        onViewChange={setActiveView}
        onToggleDrawer={() => setIsDrawerOpen((prev) => !prev)}
        onSwitchWorkspace={() => {
          setIsPlaying(false);
          setWorkspace(null);
        }}
      />

      <div className="main-layout">
        <div className="viewport-container">
          {activeView === "view-galaxy" && (
            <GalaxyView
              metaGraph={metaGraph}
              selectedEntity={selectedEntity}
              onSelectEntity={handleSelectEntity}
            />
          )}

          {activeView === "view-flame" && (
            <FlameGraphView
              flameGraph={flameGraph}
              metaGraph={metaGraph}
              onSelectEntity={handleSelectEntity}
            />
          )}

          {activeView === "view-metrics" && (
            <MetricsView metricsTimeline={metricsTimeline} />
          )}

          {activeView === "view-scrubber" && (
            <PipelineScrubberView
              pipelineSession={pipelineSession}
              currentTimeMs={currentTimeMs}
              maxTimeMs={maxTimeMs}
              isPlaying={isPlaying}
              onPlayToggle={() => setIsPlaying((prev) => !prev)}
              onTimeChange={setCurrentTimeMs}
              onSelectEntity={handleSelectEntity}
            />
          )}
        </div>

        <SideDrawerInspector
          isOpen={isDrawerOpen}
          selectedEntity={selectedEntity}
          worldState={worldState}
          onClose={() => setIsDrawerOpen(false)}
          onSaveBookmark={handleSaveBookmark}
          onSelectBookmark={handleSelectBookmark}
        />
      </div>
    </div>
  );
};
