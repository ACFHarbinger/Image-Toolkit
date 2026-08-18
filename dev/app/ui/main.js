const { invoke } = window.__TAURI__.core;
const { open } = window.__TAURI__.dialog;

const picker = document.getElementById("picker");
const workspaceView = document.getElementById("workspace-view");
const lastWorkspaceSection = document.getElementById("last-workspace");
const continueBtn = document.getElementById("continue-btn");
const browseBtn = document.getElementById("browse-btn");
const switchBtn = document.getElementById("switch-btn");
const workspaceName = document.getElementById("workspace-name");
const errorEl = document.getElementById("error");
const sidecarStatus = document.getElementById("sidecar-status");

async function refreshSidecarStatus() {
  // #409 wiring: the sidecar always serves the checkout this app was built
  // from (SidecarCommand::for_repo_root at startup), not yet the picked
  // workspace above — see AGENT_BUS.md 2026-08-18 for the follow-up seam.
  try {
    const [records, artifacts] = await Promise.all([invoke("list_records"), invoke("list_artifacts")]);
    sidecarStatus.textContent = `Sidecar up — ${records.length} record(s), ${artifacts.length} artifact(s).`;
  } catch (err) {
    sidecarStatus.textContent = `Sidecar not ready: ${err}`;
  }
}

function showWorkspace(info) {
  workspaceName.textContent = `${info.name} — ${info.root}`;
  picker.hidden = true;
  workspaceView.hidden = false;
  refreshSidecarStatus();
}

function showPicker() {
  workspaceView.hidden = true;
  picker.hidden = false;
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

async function selectAndOpen(path) {
  try {
    const info = await invoke("select_workspace", { path });
    showWorkspace(info);
  } catch (err) {
    showError(String(err));
  }
}

async function init() {
  const last = await invoke("get_last_workspace");
  if (last) {
    lastWorkspaceSection.hidden = false;
    continueBtn.textContent = `${last.name} (${last.root})`;
    continueBtn.addEventListener("click", () => showWorkspace(last));
  }
}

browseBtn.addEventListener("click", async () => {
  const dir = await open({ directory: true, multiple: false, title: "Choose a repository" });
  if (dir) {
    await selectAndOpen(dir);
  }
});

// Lock #13: one-key switcher back to the picker (explicit selection already
// happened once — this is not auto-discovery of nested repos).
switchBtn.addEventListener("click", showPicker);

init();
