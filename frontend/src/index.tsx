import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { AppStoreProvider } from "./store/AppStoreProvider";
import { ErrorBoundary } from "./components/ErrorBoundary";
import reportWebVitals from "./reportWebVitals";

console.log("--- REACT BOOTSTRAP STARTING ---");

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Failed to find the root element");
}

const root = ReactDOM.createRoot(rootElement as HTMLElement);
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <AppStoreProvider>
        <App />
      </AppStoreProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);

reportWebVitals();
