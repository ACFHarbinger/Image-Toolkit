# Frontend Module Instructions (`frontend/`)

## Overview
The Frontend is a hybrid Web/Desktop interface built with **React 19**, **TypeScript**, and **Electron**.

## Structure
* **`src/components/`**: Reusable React UI components (Atomic design).
* **`src/hooks/`**: Custom hooks for business logic and state.
* **`src/tabs/`**: Layouts mirroring the GUI tabs.
* **`public/`**: Static assets and Electron integration (`electron.js`, `preload.js`).

## Commands
| Action | Command |
| :--- | :--- |
| **Dev Mode** | `npm run dev` (React + Electron) |
| **Build Desktop** | `npm run electron-build` |
| **Test** | `npm test` |

## Coding Standards
1.  **State Management**:
    *   Prefer Functional Components and Hooks (`useState`, `useEffect`).
    *   Avoid complex class-based components.
2.  **Electron integration**:
    *   Use `preload.js` and `contextBridge` for secure IPC.
    *   Do not enable `nodeIntegration` in the renderer process.
3.  **Styling**:
    *   Use CSS modules or standard CSS (`App.css`) consistently.
