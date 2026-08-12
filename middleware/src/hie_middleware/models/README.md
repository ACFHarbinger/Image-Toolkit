# HIE Middleware Models (`middleware/models/`)

The `models` package encapsulates Deep Learning and Neural Network adapters used by the Hybrid Image Editor (HIE).

## Capabilities

- **Alpha Matting (`models/matting.py`):** Integrates state-of-the-art neural matting networks such as BiRefNet and FastSAM for instant sub-pixel trimap and alpha mask generation around complex subjects (hair, fur, glass, transparency).
- **Super-Resolution (`models/superres.py`):** Wraps Real-ESRGAN and spatial upscaling models to provide non-destructive upscaling nodes in layer graphs.
- **Inpainting & Outpainting (`models/inpainting.py`):** Stroke-guided and prompt-driven generative fill for object removal, background synthesis, and canvas boundary extension.

## Guidelines & Performance Constraints

1. Model weight files must remain outside version control (stored in remote artifact storage or local cache directories). Weights should be loaded dynamically with checksum verification.
2. Inference execution must run asynchronously off the main UI thread (e.g., using `QThread` workers or asyncio tasks) to prevent UI freezing during model invocation.
3. Support ONNX Runtime and PyTorch backends with automatic CUDA / ROCm / MPS / CPU fallback.
