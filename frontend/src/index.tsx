import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { AppStoreProvider } from "./store/AppStoreProvider";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { CloudJobsPopout } from "./shell/CloudJobsPopout";
import { windowRole } from "./shell/windowRole";

console.log("--- REACT BOOTSTRAP STARTING ---");

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Failed to find the root element");
}

const root = ReactDOM.createRoot(rootElement as HTMLElement);
const role = windowRole();
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      {role === "cloud.jobs" ? (
        <CloudJobsPopout />
      ) : (
        <AppStoreProvider>
          <App />
        </AppStoreProvider>
      )}
    </ErrorBoundary>
  </React.StrictMode>,
);
