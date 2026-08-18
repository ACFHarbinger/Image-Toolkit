const { invoke } = window.__TAURI__ ? window.__TAURI__.core : { invoke: async () => ({}) };
const { open } = window.__TAURI__ && window.__TAURI__.dialog ? window.__TAURI__.dialog : { open: async () => null };

// Global App State
const state = {
  currentWorkspace: null,
  activeView: "view-galaxy",
  worldState: null,
  metaGraph: null,
  flameGraph: null,
  metricsTimeline: null,
  pipelineSession: null,
  selectedEntity: null,
  camera: {
    rotX: 0.35,
    rotY: -0.6,
    zoom: 1.0,
    targetY: 0,
  },
  scrubber: {
    playing: false,
    currentTimeMs: 0,
    maxTimeMs: 1100,
    playInterval: null,
  },
};

// DOM Elements
const picker = document.getElementById("picker");
const workspaceView = document.getElementById("workspace-view");
const lastWorkspaceSection = document.getElementById("last-workspace");
const continueBtn = document.getElementById("continue-btn");
const browseBtn = document.getElementById("browse-btn");
const switchBtn = document.getElementById("switch-btn");
const workspaceName = document.getElementById("workspace-name");
const sidecarStatus = document.getElementById("sidecar-status");
const sideDrawer = document.getElementById("side-drawer");
const toggleDrawerBtn = document.getElementById("toggle-drawer-btn");
const closeDrawerBtn = document.getElementById("close-drawer-btn");

// Canvas
const galaxyCanvas = document.getElementById("galaxy-canvas");
const ctxGalaxy = galaxyCanvas.getContext("2d");

/* -------------------------------------------------------------
   Workspace Initialization & Navigation
------------------------------------------------------------- */
async function init() {
  try {
    const last = await invoke("get_last_workspace");
    if (last && last.root) {
      lastWorkspaceSection.hidden = false;
      continueBtn.textContent = `${last.name} (${last.root})`;
      continueBtn.onclick = () => showWorkspace(last);
    }
  } catch (err) {
    console.warn("Could not load last workspace:", err);
  }

  setupEventListeners();
}

function showWorkspace(info) {
  state.currentWorkspace = info;
  workspaceName.textContent = `${info.name} — ${info.root}`;
  picker.hidden = true;
  workspaceView.hidden = false;
  loadWorkspaceData();
}

function showPicker() {
  if (state.scrubber.playing) stopPlayback();
  workspaceView.hidden = true;
  picker.hidden = false;
}

browseBtn.addEventListener("click", async () => {
  const dir = await open({ directory: true, multiple: false, title: "Choose a repository" });
  if (dir) {
    try {
      const info = await invoke("select_workspace", { path: dir });
      showWorkspace(info);
    } catch (err) {
      alert(`Failed to open workspace: ${err}`);
    }
  }
});

switchBtn.addEventListener("click", showPicker);

/* -------------------------------------------------------------
   Data Loading & Sidecar RPC
------------------------------------------------------------- */
async function loadWorkspaceData() {
  try {
    const [records, artifacts, graphRes, flameRes, metricsRes, scrubberRes, worldRes] = await Promise.all([
      invoke("list_records"),
      invoke("list_artifacts"),
      invoke("get_meta_graph"),
      invoke("get_flame_graph"),
      invoke("get_metrics_timeline"),
      invoke("get_pipeline_scrubber", { tMs: state.scrubber.currentTimeMs }),
      invoke("get_world_state"),
    ]);

    sidecarStatus.textContent = `Sidecar up • ${records.length} records • ${artifacts.length} artifacts`;

    state.metaGraph = graphRes.graph;
    state.flameGraph = flameRes;
    state.metricsTimeline = metricsRes;
    state.pipelineSession = scrubberRes;
    state.worldState = worldRes;

    renderCurrentView();
    renderBookmarksList();
  } catch (err) {
    sidecarStatus.textContent = `Sidecar error: ${err}`;
    console.error("Sidecar load error:", err);
  }
}

/* -------------------------------------------------------------
   View Switching & Layout
------------------------------------------------------------- */
function setupEventListeners() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".view-surface").forEach((v) => v.classList.remove("active"));

      btn.classList.add("active");
      const targetView = btn.dataset.view;
      state.activeView = targetView;
      document.getElementById(targetView).classList.add("active");
      renderCurrentView();
    });
  });

  toggleDrawerBtn.onclick = () => sideDrawer.classList.toggle("collapsed");
  closeDrawerBtn.onclick = () => sideDrawer.classList.add("collapsed");

  // Keyboard Shortcuts (D54: F for frame, 1-3 for camera layer presets)
  window.addEventListener("keydown", (e) => {
    if (e.key === "f" || e.key === "F") {
      resetCamera();
    } else if (e.key === "1") {
      focusLayer(35); // Frontend (+Y)
    } else if (e.key === "2") {
      focusLayer(0); // Core (Y=0)
    } else if (e.key === "3") {
      focusLayer(-35); // Native (-Y)
    }
  });

  document.getElementById("btn-camera-reset").onclick = resetCamera;
  document.getElementById("btn-cam-frontend").onclick = () => focusLayer(35);
  document.getElementById("btn-cam-core").onclick = () => focusLayer(0);
  document.getElementById("btn-cam-native").onclick = () => focusLayer(-35);

  setupGalaxyInteraction();
  setupScrubberControls();
  setupInspector();
}

function renderCurrentView() {
  if (state.activeView === "view-galaxy") {
    resizeGalaxyCanvas();
    drawGalaxyFrame();
  } else if (state.activeView === "view-flame") {
    renderFlameGraph();
  } else if (state.activeView === "view-metrics") {
    renderMetricsCharts();
  } else if (state.activeView === "view-scrubber") {
    renderScrubberStages();
  }
}

/* -------------------------------------------------------------
   1. 3D Meta-Graph Galaxy Renderer (#415)
------------------------------------------------------------- */
function resizeGalaxyCanvas() {
  const rect = galaxyCanvas.parentElement.getBoundingClientRect();
  galaxyCanvas.width = rect.width * window.devicePixelRatio;
  galaxyCanvas.height = rect.height * window.devicePixelRatio;
  galaxyCanvas.style.width = `${rect.width}px`;
  galaxyCanvas.style.height = `${rect.height}px`;
}

function resetCamera() {
  state.camera.rotX = 0.35;
  state.camera.rotY = -0.6;
  state.camera.zoom = 1.0;
  state.camera.targetY = 0;
  drawGalaxyFrame();
}

function focusLayer(y) {
  state.camera.targetY = y;
  state.camera.rotX = 0.1;
  drawGalaxyFrame();
}

function project3D(x, y, z, width, height) {
  // Apply rotation
  const cosY = Math.cos(state.camera.rotY);
  const sinY = Math.sin(state.camera.rotY);
  const cosX = Math.cos(state.camera.rotX);
  const sinX = Math.sin(state.camera.rotX);

  const x1 = x * cosY - z * sinY;
  const z1 = z * cosY + x * sinY;

  const adjY = y - state.camera.targetY;
  const y2 = adjY * cosX - z1 * sinX;
  const z2 = z1 * cosX + adjY * sinX;

  const fov = 400 * state.camera.zoom;
  const depth = z2 + 250;
  const scale = depth > 10 ? fov / depth : 1;

  const px = width / 2 + x1 * scale;
  const py = height / 2 - y2 * scale;

  return { px, py, scale, depth };
}

let animationPhotonOffset = 0;
function drawGalaxyFrame() {
  if (state.activeView !== "view-galaxy" || !state.metaGraph) return;

  const w = galaxyCanvas.width;
  const h = galaxyCanvas.height;
  ctxGalaxy.clearRect(0, 0, w, h);

  // Draw background cosmic grid
  ctxGalaxy.strokeStyle = "rgba(255, 255, 255, 0.03)";
  ctxGalaxy.lineWidth = 1;
  for (let gy = -40; gy <= 40; gy += 35) {
    const p1 = project3D(-150, gy, 0, w, h);
    const p2 = project3D(150, gy, 0, w, h);
    ctxGalaxy.beginPath();
    ctxGalaxy.moveTo(p1.px, p1.py);
    ctxGalaxy.lineTo(p2.px, p2.py);
    ctxGalaxy.stroke();
  }

  // Draw Edges with animated photon conduits
  animationPhotonOffset = (animationPhotonOffset + 0.02) % 1.0;
  const nodes = state.metaGraph.nodes;
  const edges = state.metaGraph.edges;

  for (const e of Object.values(edges)) {
    const src = nodes[e.source_id];
    const tgt = nodes[e.target_id];
    if (!src || !tgt) continue;

    const pSrc = project3D(src.position[0], src.position[1], src.position[2], w, h);
    const pTgt = project3D(tgt.position[0], tgt.position[1], tgt.position[2], w, h);

    // Flow conduit line
    ctxGalaxy.strokeStyle = "rgba(56, 189, 248, 0.25)";
    ctxGalaxy.lineWidth = Math.max(1, 1.5 * pSrc.scale);
    ctxGalaxy.beginPath();
    ctxGalaxy.moveTo(pSrc.px, pSrc.py);
    ctxGalaxy.lineTo(pTgt.px, pTgt.py);
    ctxGalaxy.stroke();

    // Flow photon pulse
    const pulseX = pSrc.px + (pTgt.px - pSrc.px) * animationPhotonOffset;
    const pulseY = pSrc.py + (pTgt.py - pSrc.py) * animationPhotonOffset;
    ctxGalaxy.fillStyle = "#38bdf8";
    ctxGalaxy.beginPath();
    ctxGalaxy.arc(pulseX, pulseY, 3 * pSrc.scale, 0, Math.PI * 2);
    ctxGalaxy.fill();
  }

  // Draw Nodes
  for (const n of Object.values(nodes)) {
    const p = project3D(n.position[0], n.position[1], n.position[2], w, h);
    const isSelected = state.selectedEntity && state.selectedEntity.id === n.id;

    // Color by layer: frontend=cyan, core=emerald, native=amber
    let color = "#10b981";
    if (n.layer === "frontend") color = "#06b6d4";
    else if (n.layer === "native") color = "#f59e0b";

    // Glow Halo
    const r = Math.max(4, (isSelected ? 14 : 9) * p.scale);
    const grad = ctxGalaxy.createRadialGradient(p.px, p.py, r * 0.2, p.px, p.py, r * 2.2);
    grad.addColorStop(0, color);
    grad.addColorStop(1, "rgba(0,0,0,0)");
    ctxGalaxy.fillStyle = grad;
    ctxGalaxy.beginPath();
    ctxGalaxy.arc(p.px, p.py, r * 2.2, 0, Math.PI * 2);
    ctxGalaxy.fill();

    // Node Core
    ctxGalaxy.fillStyle = isSelected ? "#ffffff" : color;
    ctxGalaxy.beginPath();
    ctxGalaxy.arc(p.px, p.py, r, 0, Math.PI * 2);
    ctxGalaxy.fill();

    // Node Label
    ctxGalaxy.fillStyle = isSelected ? "#38bdf8" : "#e2e8f0";
    ctxGalaxy.font = `${Math.max(10, Math.round(11 * p.scale))}px monospace`;
    ctxGalaxy.textAlign = "center";
    ctxGalaxy.fillText(n.label, p.px, p.py - r - 6);
  }
}

let isDraggingGalaxy = false;
let lastMousePos = { x: 0, y: 0 };
function setupGalaxyInteraction() {
  galaxyCanvas.addEventListener("mousedown", (e) => {
    isDraggingGalaxy = true;
    lastMousePos = { x: e.clientX, y: e.clientY };
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDraggingGalaxy) return;
    const dx = e.clientX - lastMousePos.x;
    const dy = e.clientY - lastMousePos.y;
    state.camera.rotY += dx * 0.006;
    state.camera.rotX += dy * 0.006;
    lastMousePos = { x: e.clientX, y: e.clientY };
    drawGalaxyFrame();
  });

  window.addEventListener("mouseup", () => {
    isDraggingGalaxy = false;
  });

  galaxyCanvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    state.camera.zoom *= e.deltaY > 0 ? 0.9 : 1.1;
    state.camera.zoom = Math.max(0.3, Math.min(state.camera.zoom, 3.5));
    drawGalaxyFrame();
  });

  galaxyCanvas.addEventListener("click", (e) => {
    const rect = galaxyCanvas.getBoundingClientRect();
    const clickX = (e.clientX - rect.left) * window.devicePixelRatio;
    const clickY = (e.clientY - rect.top) * window.devicePixelRatio;

    if (!state.metaGraph) return;
    const w = galaxyCanvas.width;
    const h = galaxyCanvas.height;

    for (const n of Object.values(state.metaGraph.nodes)) {
      const p = project3D(n.position[0], n.position[1], n.position[2], w, h);
      const dist = Math.hypot(clickX - p.px, clickY - p.py);
      if (dist < 20 * p.scale) {
        selectEntity(n);
        break;
      }
    }
  });

  // Continuous animation loop for photon pulses
  setInterval(() => {
    if (state.activeView === "view-galaxy") {
      drawGalaxyFrame();
    }
  }, 30);
}

/* -------------------------------------------------------------
   2. 2D Flame Graph Renderer (#416)
------------------------------------------------------------- */
function renderFlameGraph() {
  const container = document.getElementById("flame-tree-root");
  container.innerHTML = "";
  if (!state.flameGraph || !state.flameGraph.tree) return;

  const totalTime = state.flameGraph.total_time_ms || 100.0;

  function buildFlameHtml(node, depth = 0) {
    const pct = ((node.value / totalTime) * 100).toFixed(1);
    const box = document.createElement("div");
    box.className = `flame-box cat-${node.category || "lifecycle"}`;
    box.style.width = `${Math.max(pct, 5)}%`;
    box.textContent = `${node.name} (${node.value.toFixed(1)}ms)`;
    box.title = `${node.name}\nDuration: ${node.value.toFixed(2)}ms\nSelf-Time: ${node.self_time_ms.toFixed(2)}ms\nCategory: ${node.category}`;

    box.onclick = () => {
      // Cross-view linking to 3D node (#417)
      if (node.meta_node_id && state.metaGraph && state.metaGraph.nodes[node.meta_node_id]) {
        selectEntity(state.metaGraph.nodes[node.meta_node_id]);
      } else {
        selectEntity({ id: node.name, layer: "core", kind: node.category, latency_ms: node.value, call_count: 1 });
      }
    };

    const row = document.createElement("div");
    row.className = "flame-row";
    row.appendChild(box);
    container.appendChild(row);

    if (node.children) {
      for (const child of node.children) {
        buildFlameHtml(child, depth + 1);
      }
    }
  }

  buildFlameHtml(state.flameGraph.tree);
}

/* -------------------------------------------------------------
   3. 2D Metrics & RSS Progression (#416)
------------------------------------------------------------- */
function renderMetricsCharts() {
  if (!state.metricsTimeline) return;

  // Render RSS Memory Chart
  const canvasRss = document.getElementById("chart-rss");
  const ctxRss = canvasRss.getContext("2d");
  const rssData = state.metricsTimeline.rss_memory;

  if (rssData) {
    canvasRss.width = canvasRss.parentElement.clientWidth * window.devicePixelRatio;
    canvasRss.height = 200 * window.devicePixelRatio;

    const w = canvasRss.width;
    const h = canvasRss.height;
    ctxRss.clearRect(0, 0, w, h);

    const pts = rssData.points;
    document.getElementById("mem-current-val").textContent = `${pts[pts.length - 1]?.val.toFixed(1) || "--"} MB`;

    // Draw 200MB alert line
    const alertY = h - (200.0 / 250.0) * h;
    ctxRss.strokeStyle = "rgba(244, 63, 94, 0.6)";
    ctxRss.setLineDash([6, 6]);
    ctxRss.beginPath();
    ctxRss.moveTo(0, alertY);
    ctxRss.lineTo(w, alertY);
    ctxRss.stroke();
    ctxRss.setLineDash([]);

    // Draw memory line
    ctxRss.strokeStyle = "#38bdf8";
    ctxRss.lineWidth = 3;
    ctxRss.beginPath();
    pts.forEach((p, idx) => {
      const x = (idx / (pts.length - 1)) * w;
      const y = h - (p.val / 250.0) * h;
      if (idx === 0) ctxRss.moveTo(x, y);
      else ctxRss.lineTo(x, y);
    });
    ctxRss.stroke();
  }

  // Render Coherence Score Trend
  const canvasCoh = document.getElementById("chart-coherence");
  const ctxCoh = canvasCoh.getContext("2d");
  const cohData = state.metricsTimeline.coherence_trend;

  if (cohData) {
    canvasCoh.width = canvasCoh.parentElement.clientWidth * window.devicePixelRatio;
    canvasCoh.height = 200 * window.devicePixelRatio;

    const w = canvasCoh.width;
    const h = canvasCoh.height;
    ctxCoh.clearRect(0, 0, w, h);

    const pts = cohData.points;
    document.getElementById("coherence-current-val").textContent = pts[pts.length - 1]?.val.toFixed(2) || "--";

    ctxCoh.strokeStyle = "#10b981";
    ctxCoh.lineWidth = 3;
    ctxCoh.beginPath();
    pts.forEach((p, idx) => {
      const x = (idx / (pts.length - 1)) * w;
      const y = h - (p.val / 5.0) * h;
      if (idx === 0) ctxCoh.moveTo(x, y);
      else ctxCoh.lineTo(x, y);
    });
    ctxCoh.stroke();
  }
}

/* -------------------------------------------------------------
   4. 4D Pipeline Execution Scrubber (#418)
------------------------------------------------------------- */
function setupScrubberControls() {
  const playBtn = document.getElementById("btn-scrub-play");
  const slider = document.getElementById("scrubber-slider");
  const readout = document.getElementById("scrub-time-readout");

  playBtn.onclick = () => {
    if (state.scrubber.playing) stopPlayback();
    else startPlayback();
  };

  document.getElementById("btn-scrub-step-back").onclick = () => {
    updateScrubberTime(Math.max(0, state.scrubber.currentTimeMs - 10));
  };
  document.getElementById("btn-scrub-step-fwd").onclick = () => {
    updateScrubberTime(Math.min(state.scrubber.maxTimeMs, state.scrubber.currentTimeMs + 10));
  };
  document.getElementById("btn-scrub-reset").onclick = () => {
    updateScrubberTime(0);
  };

  slider.oninput = (e) => {
    updateScrubberTime(parseFloat(e.target.value));
  };
}

function startPlayback() {
  state.scrubber.playing = true;
  document.getElementById("btn-scrub-play").textContent = "⏸ Pause";
  state.scrubber.playInterval = setInterval(() => {
    let nextTime = state.scrubber.currentTimeMs + 15;
    if (nextTime > state.scrubber.maxTimeMs) nextTime = 0;
    updateScrubberTime(nextTime);
  }, 40);
}

function stopPlayback() {
  state.scrubber.playing = false;
  document.getElementById("btn-scrub-play").textContent = "▶ Play";
  clearInterval(state.scrubber.playInterval);
}

async function updateScrubberTime(tMs) {
  state.scrubber.currentTimeMs = tMs;
  document.getElementById("scrubber-slider").value = tMs;
  document.getElementById("scrub-time-readout").textContent = `${tMs.toFixed(1)} ms / ${state.scrubber.maxTimeMs} ms`;

  try {
    const res = await invoke("get_pipeline_scrubber", { tMs });
    state.pipelineSession = res;
    renderScrubberStages();
  } catch (err) {
    console.error("Scrubber update error:", err);
  }
}

function renderScrubberStages() {
  const container = document.getElementById("pipeline-stages-container");
  if (!state.pipelineSession || !state.pipelineSession.session) return;

  container.innerHTML = "";
  const stages = state.pipelineSession.session.stages;
  const evalData = state.pipelineSession.evaluation;
  const stageStatesMap = {};
  evalData.stages.forEach((s) => (stageStatesMap[s.stage_id] = s));

  stages.forEach((stage) => {
    const st = stageStatesMap[stage.id] || { status: "pending", progress: 0 };
    const card = document.createElement("div");
    card.className = `stage-card ${st.status}`;

    card.innerHTML = `
      <div class="stage-header">
        <span class="stage-name">${stage.stage_name}</span>
        <span class="stage-status-tag tag-${st.status}">${st.status} (${(st.progress * 100).toFixed(0)}%)</span>
      </div>
      <div class="stage-progress-bar">
        <div class="stage-progress-fill" style="width: ${st.progress * 100}%"></div>
      </div>
    `;

    card.onclick = () => {
      selectEntity({ id: stage.id, layer: "core", kind: "pipeline_stage", latency_ms: stage.end_ms - stage.start_ms });
    };

    container.appendChild(card);
  });
}

/* -------------------------------------------------------------
   5. Side-Drawer Inspector & Investigation Bookmarks (#417 / #419)
------------------------------------------------------------- */
function setupInspector() {
  document.getElementById("btn-save-bookmark").onclick = async () => {
    const noteText = document.getElementById("investigation-note-input").value;
    if (!state.worldState) return;

    const bm = {
      id: `bm-${Date.now().toString(16)}`,
      label: noteText ? noteText.slice(0, 30) : "Vantage Bookmark",
      position: [0.0, 40.0, 90.0],
      target: [0.0, state.camera.targetY, 0.0],
      pinned_node_id: state.selectedEntity?.id || null,
      created_at: new Date().toISOString(),
    };

    state.worldState.bookmarks.push(bm);
    await invoke("save_world_state", { worldState: state.worldState });
    renderBookmarksList();
    document.getElementById("investigation-note-input").value = "";
  };
}

function selectEntity(entity) {
  state.selectedEntity = entity;
  sideDrawer.classList.remove("collapsed");

  document.getElementById("inspect-id").textContent = entity.id || entity.name || "--";
  document.getElementById("inspect-layer").textContent = entity.layer || "--";
  document.getElementById("inspect-subsystem").textContent = entity.cluster_id || entity.kind || "--";
  document.getElementById("inspect-latency").textContent = entity.latency_ms ? `${entity.latency_ms.toFixed(1)} ms` : "--";
  document.getElementById("inspect-calls").textContent = entity.call_count ? `${entity.call_count} ops` : "--";

  if (state.activeView === "view-galaxy") {
    drawGalaxyFrame();
  }
}

function renderBookmarksList() {
  const container = document.getElementById("bookmark-list-container");
  container.innerHTML = "";
  if (!state.worldState || !state.worldState.bookmarks) return;

  state.worldState.bookmarks.forEach((bm) => {
    const pill = document.createElement("div");
    pill.className = "bookmark-pill";
    pill.innerHTML = `<span>📌 ${bm.label}</span><span style="color: #64748b;">${bm.pinned_node_id || "Vantage"}</span>`;
    pill.onclick = () => {
      if (bm.pinned_node_id && state.metaGraph && state.metaGraph.nodes[bm.pinned_node_id]) {
        selectEntity(state.metaGraph.nodes[bm.pinned_node_id]);
      }
    };
    container.appendChild(pill);
  });
}

// Kickoff
init();
