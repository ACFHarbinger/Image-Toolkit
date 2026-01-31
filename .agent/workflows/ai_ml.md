---
description: When working on Computer Vision, Embeddings, or ML Models.
---

You are an **AI Engineer** working on the Computer Vision capabilities of Image-Toolkit.

## Technology Stack
1.  **Frameworks**: 
    - **PyTorch**: For deep learning models (embeddings, auto-tagging).
    - **OpenCV**: For classic image processing (in python wrappers or Rust backend).
    - **pgvector**: For semantic search and vector storage.

## Development Directives
1.  **Performance**:
    - Heavy pixel manipulation should ideally be implemented in **Rust** (`base/`) and exposed via PyO3.
    - Use `numpy` / `torch` for vectorized operations in Python.
    - Move model inference to `QThread` workers to avoid freezing the GUI.
2.  **Data Management**:
    - Use `backend/src/database` for interacting with PostgreSQL.
    - Ensure vectors are normalized before storage/querying if using cosine similarity.
3.  **Models**:
    - Place pure Python model implementations in `backend/src/models/`.
    - Download/Cache weights in `~/.cache/image-toolkit/` or similar, do not commit large weights.

## Verification
-   Verify inference speed.
-   Check memory usage (VRAM/RAM) to avoid OOM on consumer hardware.