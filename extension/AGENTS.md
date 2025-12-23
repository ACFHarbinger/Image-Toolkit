# Browser Extension Instructions (`extension/`)

## Overview
A lightweight browser extension (Manifest V3) that integrates with the external browser to facilitate seamless image saving and communication with the Image-Toolkit backend.

## Structure
* **`manifest.json`**: Configuration source. Must be V3 compliant.
* **`background.js`**: Service worker script. Handles context menus and messaging.
* **`options.html/js`**: User configuration for backend connectivity headers or saving preferences.

## Capabilities
*   **Context Menus**: Adds "Save Image to Image-Toolkit" options.
*   **Communication**: Should communicate with the local backend (usually `localhost:8000`) via `fetch` or Native Messaging if strictly required.

## Coding Standards
1.  **Manifest V3**:
    *   Use `chrome.scripting` instead of executing scripts directly.
    *   Persistent background pages are replaced by service workers; manage state accordingly.
2.  **Security**:
    *   Sanitize all inputs from the web page.
    *   Respect CORS policies when talking to the local API.
3.  **Cross-Browser**:
    *   Ensure compatibility with Chrome, Firefox (Gecko), and Edge.
