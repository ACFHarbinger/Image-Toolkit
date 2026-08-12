const root = document.querySelector<HTMLElement>("#app");

if (!root) throw new Error("HIE frontend mount point is missing");

root.innerHTML = `
  <h1>Hybrid Image Editor</h1>
  <p>Frontend shell ready for Image-Toolkit embedding or standalone Tauri hosting.</p>
  <button type="button" aria-label="Open an image">Open image</button>
`;
