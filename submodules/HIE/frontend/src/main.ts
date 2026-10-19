import "./style.css";
import { getHieHost } from "./host";

type Tool = "localized_tone" | "adjust_exposure" | "crop";

interface Proposal {
  tool: Tool;
  label: string;
  confidence: number;
}

const root = document.querySelector<HTMLElement>("#app");
if (!root) throw new Error("HIE frontend mount point is missing");

const tools: Array<{ id: Tool; label: string; detail: string }> = [
  { id: "localized_tone", label: "Brush assistant", detail: "Localized retouching" },
  { id: "adjust_exposure", label: "Tone agent", detail: "Global exposure & contrast" },
  { id: "crop", label: "Composition", detail: "Crop balance optimizer" },
];

let selectedTool: Tool = "localized_tone";
let proposal: Proposal | null = null;

root.innerHTML = `
  <div class="shell">
    <header class="topbar">
      <div class="brand"><span class="status-dot"></span><span>HIE</span><small>HYBRID IMAGE EDITOR</small></div>
      <div class="top-actions"><button class="ghost" id="open">Open media</button><button class="primary" id="export">Export</button></div>
    </header>
    <main class="workspace">
      <aside class="rail">
        <button class="rail-button active" aria-label="Canvas">✦</button>
        <button class="rail-button" aria-label="Layers">▱</button>
        <button class="rail-button" aria-label="History">↶</button>
        <div class="rail-spacer"></div><button class="rail-button" aria-label="Settings">⚙</button>
      </aside>
      <section class="canvas-column">
        <div class="crumb">UNTITLED / <span>FRAME 01</span><b id="save-state">READY</b></div>
        <div class="canvas-wrap"><canvas id="canvas" width="920" height="560"></canvas><div class="canvas-empty">Drop an image or video sequence here<br><small>Images are represented as one-frame sequences</small></div></div>
        <div class="timeline"><span>01 / 01</span><div class="timeline-track"><i></i></div><span>00:00:00</span></div>
      </section>
      <aside class="inspector">
        <div class="panel-heading"><span>ASSISTANCE</span><span class="availability">● LOCAL</span></div>
        <p class="panel-intro">Preview an intelligent edit, then accept it into document history.</p>
        <div id="tools"></div>
        <button class="wide-button" id="preview">Preview suggestion <span>↗</span></button>
        <div id="proposal" class="proposal hidden"></div>
        <div class="panel-heading layers-heading"><span>LAYER STACK</span><button class="icon-button">＋</button></div>
        <div class="layer selected"><span class="layer-thumb"></span><span>Source sequence</span><em>100%</em></div>
        <div class="layer"><span class="layer-thumb checker"></span><span>Adjustment group</span><em>—</em></div>
      </aside>
    </main>
    <footer><span>HYBRID-IMAGE-EDITOR</span><span id="message">Ready for a document</span><a href="https://github.com/ACFHarbinger/Image-Toolkit">Open Image-Toolkit ↗</a></footer>
  </div>`;

const message = document.querySelector<HTMLElement>("#message")!;
const saveState = document.querySelector<HTMLElement>("#save-state")!;
const proposalBox = document.querySelector<HTMLElement>("#proposal")!;
const host = getHieHost();

function renderTools(): void {
  document.querySelector<HTMLElement>("#tools")!.innerHTML = tools.map((tool) => `
    <button class="tool ${tool.id === selectedTool ? "selected" : ""}" data-tool="${tool.id}">
      <span class="tool-icon">${tool.id === "localized_tone" ? "◌" : tool.id === "adjust_exposure" ? "☼" : "⌗"}</span>
      <span><strong>${tool.label}</strong><small>${tool.detail}</small></span><span class="chevron">›</span>
    </button>`).join("");
  document.querySelectorAll<HTMLButtonElement>("[data-tool]").forEach((button) => button.onclick = () => {
    selectedTool = button.dataset.tool as Tool;
    proposal = null;
    proposalBox.classList.add("hidden");
    renderTools();
    message.textContent = "Tool selected — ready to preview";
  });
}

function preview(): void {
  const selected = tools.find((tool) => tool.id === selectedTool)!;
  proposal = { tool: selectedTool, label: selected.label, confidence: 0 };
  proposalBox.innerHTML = `<div><strong>Preview ready</strong><small>${selected.detail} · inspectable proposal</small></div><button id="accept">Accept</button>`;
  proposalBox.classList.remove("hidden");
  message.textContent = `${selected.label} proposal ready — accept to record`;
  document.querySelector<HTMLButtonElement>("#accept")!.onclick = accept;
}

function accept(): void {
  if (!proposal) return;
  proposalBox.classList.add("hidden");
  saveState.textContent = "HISTORY UPDATED";
  message.textContent = `${proposal.label} accepted into document history`;
  proposal = null;
  window.setTimeout(() => { saveState.textContent = "READY"; }, 1800);
}

document.querySelector<HTMLButtonElement>("#preview")!.onclick = preview;
document.querySelector<HTMLButtonElement>("#open")!.onclick = async () => {
  await host.openMedia();
  const text = "Media open requested from host";
  message.textContent = text;
  host.notify(text);
};
document.querySelector<HTMLButtonElement>("#export")!.onclick = async () => {
  await host.exportDocument();
  const text = "Export requested from host";
  message.textContent = text;
  host.notify(text);
};
renderTools();
