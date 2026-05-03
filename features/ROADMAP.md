# Image-Toolkit Advanced Roadmap

## Overview

This roadmap defines the future evolution of the Image-Toolkit ecosystem. Embracing a **Dual-Interface Strategy**, the application is divided into two highly specialized domains:
1.  **PySide6 (Desktop App):** A heavyweight, native environment built for local resource manipulation, deep OS integration, and interactive machine learning pipelines.
2.  **Tauri / React (Web App):** A lightweight, accessible, and network-ready interface designed for database management, remote task execution, and cross-device syncing.

---

## 1. PySide6 Desktop Application (The Pro Environment)

The desktop application remains the powerhouse for tasks requiring heavy GUI interaction, deep OS coupling, and local ML inference monitoring.

### A. Advanced ML UI & Interactive Pipelines
*   **Dynamic ComfyUI Dashboard:** Build a native PySide6 dynamic form generator that parses `workflow_api.json` templates (such as the 7-stage Illustrious XL pipeline) and automatically generates UI sliders and node-selection widgets mapped to `parameters.json`. This abstracts the complex ComfyUI web interface from the user while retaining full pipeline power.
*   **Panorama Stitch UI (`StitchTab`):** Create a dedicated tab utilizing `QGraphicsView` to interact directly with `stitch_net.py` and `loftr_wrapper.py`. Users will be able to visually review keypoint matches, manually drag alignment anchors, and preview the "Master-Cel" masking boundaries before rendering high-res panoramas.
*   **Interactive Background Removal:** Integrate `birefnet_wrapper.py` into the `ConvertTab` with interactive brush-stroke refinements for precision masking.

### B. OS Integration & Media Handling
*   **System Wallpaper Daemon Upgrades:** Expand the D-Bus/qdbus-qt6 (Linux) and Windows COM interactions in `WallpaperTab` to support true multi-monitor video wallpapers with seamless looping, leveraging mpv/libmpv directly inside the PyQt window.
*   **Hardware-Accelerated Frame Extraction:** Replace `cv2.VideoCapture` in the `VideoExtractionWorker` with hardware-accelerated bindings (FFmpeg API via Rust/Python wrappers) for zero-copy frame dumping.

---

## 2. Tauri / React Web App (The Cross-Platform Hub)

The React-based application (packaged in Tauri for desktop deployment or served via Django for browser access) acts as the modern interface for library management, semantic searching, and remote execution.

### A. Real-Time Network Architecture
*   **Django Channels / WebSockets:** Upgrade the `tasks/urls.py` REST API to include WebSocket endpoints. This allows the React application to display live progress bars, ETAs, and stdout streams for long-running Celery tasks (e.g., GAN training, video extraction, batch conversion).
*   **Virtualized Media Galleries:** Implement `react-window` or `@tanstack/react-virtual` to handle infinite scrolling of database queries without DOM bloat, fetching paginated image vectors directly from the Django backend.

### B. LAN Streaming & Mobile Synergy
*   **Remote Web Access Mode:** Expose the Django API and React Web App over the local network via mDNS/Bonjour. This allows mobile applications (Android Kotlin / iOS Swift) to connect, search the `pgvector` database, and initiate downloads or syncs without external cloud dependencies.
*   **Web-First Task Dispatch:** Expand the Django Celery tasks to fully encompass the deep ML models (Stitching, Birefnet, SD3) so the React app can trigger complex, compute-heavy pipelines asynchronously on the host machine while the user monitors progress from a browser or mobile device.

---

## 3. Core Engine & AI Enhancements (Rust / Python Base)

The invisible engine driving both interfaces requires aggressive optimization and new AI capabilities to support scaling beyond 1,000,000 assets.

### A. Next-Generation AI Tagging & Search
*   **Vision-Language Model (VLM) Auto-Tagging:** Integrate lightweight, locally hosted VLMs (such as LLaVA 1.5 8B or Moondream2) directly into the image ingestion pipeline. Images will be automatically captioned and tagged with human-readable descriptions alongside the existing CLIP embeddings.
*   **Smart Semantic Albums:** Implement dynamic virtual albums that map natural language queries (e.g., *"Cyberpunk cityscapes at night with rain"*) into live `pgvector` HNSW index searches, automatically populating galleries without any manual keyword tagging.

### B. Database Performance & Indexing
*   **HNSW Index Upgrade:** Transition `pgvector` columns from exact KNN/IVFFlat to HNSW (Hierarchical Navigable Small World). This will reduce similarity search latency from seconds to milliseconds on massive datasets.
*   **Asynchronous Bulk I/O:** Refactor `image_database.py` ingestion to use `execute_values` or `COPY FROM` for bulk record insertion, dramatically accelerating directory scanning times.

### C. Completion of RAM Reduction Roadmaps
*   **Tier 4 & 5 Execution:**
    *   *Rust Streaming:* Modify `base/src/core/image_merger.rs` and `image_converter.rs` to stream `DynamicImage` buffers incrementally rather than loading entire multi-gigabyte collections into memory prior to processing.
    *   *PyTorch Sequential Offloading:* Enforce strict `enable_sequential_cpu_offload()` for SD3 and multi-stage ComfyUI pipelines when the system detects < 8GB of available VRAM.

---

## 4. Quality of Life & Utilities

*   **Non-Destructive Edit Recipes:** Implement an edit-history JSON format. Instead of overwriting image pixels on color-grade or crop, the UI saves a lightweight recipe. The final image is only baked out on explicit export.
*   **Intelligent Duplicate Grouping:** Enhance the Rust duplicate scanner to present a side-by-side visual diff (highlighting pixel differences) in the React application, allowing users to safely resolve near-duplicate collisions (e.g., varying compressions or watermarks).
