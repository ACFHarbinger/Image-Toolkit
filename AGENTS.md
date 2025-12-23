# AGENTS.md - Instructions for Coding Assistant LLMs

## 1. Project Overview & Mission
**Image-Toolkit** is an integrated image database and editing framework that bridges high-performance computer vision (PyTorch, OpenCV) with robust web automation (Selenium) and cross-platform accessibility. 
The project mission is to provide a unified environment for managing massive image libraries, performing semantic vector searches, and automating stylized content generation.

## 2. Technical Stack & Environmental Governance
* **Runtime**: Python 3.11+ managed via `uv` (preferred), `conda`, or standard `venv`.
* **Primary Frameworks**:
    * **GUI**: PySide6 (Qt for Python) for the desktop interface.
    * **Database**: PostgreSQL with the `pgvector` extension for semantic and vector similarity search.
    * **Computer Vision/ML**: PyTorch (AnimeGAN2, Siamese Networks, LoRA) and OpenCV (Structural Similarity, Feature Matching).
    * **Web Automation**: Selenium WebDriver (supporting Brave, Firefox, Chrome, and Edge).
    * **Mobile/External**: Kotlin (Android), Swift (iOS), and React (Web/Frontend).
* **Quality Control**: Compliance with `pytest` for all Python functionality and Maven (`mvn test`) for Java components.

## 3. Core Architectural Boundaries
Maintain strict separation of concerns across these primary modules:
* **Backend Logic (`backend/src/`)**:
    * **`core/`**: Critical engines for database interaction, file conversion, vault security, and system-level operations (e.g., wallpaper management).
    * **`models/`**: Neural architecture implementations, including GAN wrappers, diffusion models, and siamese networks for similarity indexing.
    * **`web/`**: Automated crawlers for image boards and cloud synchronization agents (Google Drive, Dropbox, OneDrive).
* **GUI Layer (`gui/src/`)**:
    * **`tabs/`**: Module-specific UI views (Convert, Search, Database, Model Training/Generation).
    * **`helpers/`**: Threaded workers (e.g., `DuplicateScanWorker`, `ConversionWorker`) that ensure non-blocking UI during heavy I/O or ML tasks.
    * **`windows/`**: Management for main, login, preview, and log windows.

## 4. Key CLI Entry Points (Operational Playbook)
Always reference these commands when proposing code changes:
| Action | Command |
| :--- | :--- |
| **Sync Environment** | `uv sync` |
| **Launch Desktop App** | `python main.py` |
| **Single Conversion** | `python main.py convert --output_format png --input_path <path_to_img>` |
| **Batch Conversion** | `python main.py convert --output_format png --input_path <dir> --input_formats webp` |
| **Build Desktop App** | `pyinstaller --clean app.spec` |
| **Run Tests** | `pytest` |

## 5. External Access and Browser Usage Rules
The agent is authorized to use the following external tools to assist in development:
* **Web Search and Documentation**: Use Google Search to retrieve the latest documentation for **PySide6**, **pgvector** SQL syntax, **OpenCV** descriptor best practices, and **PyTorch Hub** model updates.
* **Web Automation Debugging**: If a crawler fails in `backend/src/web/crawler.py`, search for relevant WebDriver version conflicts or browser-specific headless mode flags (e.g., for Brave or Firefox-ESR).

## 6. Domain-Specific Coding Standards
### Database & Vector Integrity
* **Schema Consistency**: Any modification to `image_database.py` must ensure the `images` table remains compatible with `vector(128)` embeddings and the `hnsw` index.
* **Transaction Safety**: Use transaction blocks (commit/rollback) when renaming groups or subgroups to maintain relational integrity between the `groups` and `images` tables.

### GUI Threading & Responsiveness
* **Worker Inheritance**: All heavy computations (scanning, training, converting) must inherit from `QObject` or `QRunnable` and be managed by a `QThread` or `QThreadPool` to avoid freezing the main Qt thread.
* **Signal Communication**: Use PySide signals (`finished`, `error`, `status`) to communicate progress from workers to the UI layer.

### Security & Privacy
* **Vault Protection**: Never propose changes that bypass the `VaultManager` or expose raw keys. All sensitive credentials must remain encrypted within the `.vault` files managed by the Kotlin/Java cryptography module.

## 7. AI Review & Severity Protocol
Categorize your feedback and edits using these severity levels:
* **CRITICAL**: Breaking `image_database.py` schema; bypassing `VaultManager` security; exposing PostgreSQL credentials.
* **HIGH**: Memory leaks in `gan_wrapper.py` training loops; threading deadlocks in `DuplicateScanWorker`.
* **MEDIUM**: Inefficient SQL queries in `search_images`; non-compliant Selenium selectors in `danbooru_crawler.py`.
* **LOW**: UI margin/padding inconsistencies in Qt stylesheets; documentation typos in README.

## 8. Known Constraints & "No-Go" Areas
* **PostgreSQL Dependency**: Do not suggest SQLite alternatives; the project strictly requires `pgvector` for its primary search functionality.
* **Legacy Desktop Support**: For wallpaper settings on Linux, ensure compatibility with `qdbus-qt6` for KDE Plasma environments.
* **Headless Limitations**: Note that Safari does not support headless mode in the `WebCrawler` agent.

## 9. Usage Note
Reference this file during project-wide analysis. When refactoring components, ensure they align with the `backend/src/core` vs. `backend/src/models` separation and the multi-threaded worker patterns defined here.