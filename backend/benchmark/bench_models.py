"""
ML model inference benchmarks.

Measures inference time, memory usage, and model load/unload performance.
"""

import sys
import time
import torch
from pathlib import Path
from tempfile import NamedTemporaryFile
from PIL import Image
import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.siamese_network import SiameseModelLoader
from src.models.gan_wrapper import GanWrapper
from benchmark.utils import BenchmarkRunner, measure_memory


runner = BenchmarkRunner("ML Model Inference")


def create_test_image(size=(512, 512)):
    """Create a test RGB image."""
    img = Image.fromarray(np.random.randint(0, 255, (*size, 3), dtype=np.uint8))
    return img


@runner.benchmark("siamese_load_model", iterations=3)
@measure_memory
def bench_siamese_load():
    """Load Siamese ResNet-18 model."""
    loader = SiameseModelLoader()
    loader.load_model()
    loader.unload()


@runner.benchmark("siamese_embedding_single_cpu", iterations=10, warmup=1)
@measure_memory
def bench_siamese_embedding_cpu():
    """Generate embedding for single image (CPU)."""
    loader = SiameseModelLoader()
    loader.load_model()

    # Force CPU
    if loader._device.type == "cuda":
        loader._device = torch.device("cpu")
        loader._model.to(loader._device)

    # Create test image
    with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img = create_test_image()
        img.save(tmp.name)
        tmp_path = tmp.name

    # Benchmark
    embedding = loader.get_embedding(tmp_path)

    # Cleanup
    Path(tmp_path).unlink()
    loader.unload()

    return embedding.shape if embedding is not None else None


@runner.benchmark("siamese_embedding_batch_10_cpu", iterations=5)
@measure_memory
def bench_siamese_batch_10_cpu():
    """Generate embeddings for 10 images (CPU)."""
    loader = SiameseModelLoader()
    loader.load_model()

    # Force CPU
    if loader._device.type == "cuda":
        loader._device = torch.device("cpu")
        loader._model.to(loader._device)

    # Create 10 test images
    tmp_paths = []
    for i in range(10):
        with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            img = create_test_image()
            img.save(tmp.name)
            tmp_paths.append(tmp.name)

    # Benchmark
    embeddings = []
    for path in tmp_paths:
        emb = loader.get_embedding(path)
        if emb is not None:
            embeddings.append(emb)

    # Cleanup
    for path in tmp_paths:
        Path(path).unlink()
    loader.unload()

    return len(embeddings)


@runner.benchmark("siamese_embedding_single_gpu", iterations=10, warmup=1)
@measure_memory
def bench_siamese_embedding_gpu():
    """Generate embedding for single image (GPU if available)."""
    if not torch.cuda.is_available():
        print("Skipping GPU benchmark (CUDA not available)")
        return None

    loader = SiameseModelLoader()
    loader.load_model()

    # Create test image
    with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img = create_test_image()
        img.save(tmp.name)
        tmp_path = tmp.name

    # Benchmark
    embedding = loader.get_embedding(tmp_path)

    # Cleanup
    Path(tmp_path).unlink()
    loader.unload()

    return embedding.shape if embedding is not None else None


@runner.benchmark("gan_load_model", iterations=3)
@measure_memory
def bench_gan_load():
    """Load AnimeGAN2 model."""
    try:
        gan = GanWrapper()
        gan.unload()
    except Exception as e:
        print(f"GAN load failed: {e}")
        return None


@runner.benchmark("gan_generate_single", iterations=3)
@measure_memory
def bench_gan_generate():
    """Generate single anime-style image."""
    try:
        gan = GanWrapper(device="cpu")  # Force CPU for reproducibility

        # Create test input image
        with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_in:
            img = create_test_image()
            img.save(tmp_in.name)
            input_path = tmp_in.name

        with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_out:
            output_path = tmp_out.name

        # Benchmark
        gan.generate(input_path, output_path)

        # Cleanup
        Path(input_path).unlink()
        Path(output_path).unlink(missing_ok=True)
        gan.unload()

        return True
    except Exception as e:
        print(f"GAN generation failed: {e}")
        return None


@runner.benchmark("model_unload_time_siamese", iterations=5)
@measure_memory
def bench_siamese_unload():
    """Measure Siamese model unload time."""
    loader = SiameseModelLoader()
    loader.load_model()

    # Benchmark unload
    start = time.perf_counter()
    loader.unload()
    elapsed = time.perf_counter() - start

    return elapsed


@runner.benchmark("model_unload_time_gan", iterations=3)
@measure_memory
def bench_gan_unload():
    """Measure GAN model unload time."""
    try:
        gan = GanWrapper(device="cpu")

        # Benchmark unload
        start = time.perf_counter()
        gan.unload()
        elapsed = time.perf_counter() - start

        return elapsed
    except Exception as e:
        print(f"GAN unload failed: {e}")
        return None


@runner.benchmark("siamese_load_unload_cycle", iterations=10)
@measure_memory
def bench_siamese_load_unload_cycle():
    """Measure full load → inference → unload cycle."""
    loader = SiameseModelLoader()

    # Create test image once
    with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img = create_test_image()
        img.save(tmp.name)
        tmp_path = tmp.name

    # Cycle
    loader.load_model()
    embedding = loader.get_embedding(tmp_path)
    loader.unload()

    # Cleanup
    Path(tmp_path).unlink()

    return embedding.shape if embedding is not None else None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ML model benchmarks")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    parser.add_argument("--baseline", type=Path, help="Baseline file for regression check")
    parser.add_argument("--skip-gpu", action="store_true", help="Skip GPU benchmarks")
    args = parser.parse_args()

    # Skip GPU benchmarks if requested
    if args.skip_gpu or not torch.cuda.is_available():
        print("Skipping GPU benchmarks")
        # Remove GPU benchmarks from registered list
        runner._registered_benchmarks = [
            (name, func) for name, func in getattr(runner, "_registered_benchmarks", [])
            if "gpu" not in name
        ]

    runner.run()
    runner.print_results()

    if args.save:
        output_path = runner.save_json()
        print(f"Results saved to {output_path}")

    if args.baseline:
        passed = runner.check_regression(args.baseline)
        sys.exit(0 if passed else 1)
