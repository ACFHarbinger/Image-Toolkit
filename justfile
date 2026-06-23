# Image Toolkit - Justfile
# Convenience commands to run the application from project root

set shell := ["bash", "-c"]

red := '\033[0;31m'
green := '\033[0;32m'
yellow := '\033[0;33m'
blue := '\033[0;34m'
purple := '\033[0;35m'
cyan := '\033[0;36m'
bold := '\033[1m'
reset := '\033[0m'

# Default target - List all available recipes
default:
    @just --list

# --- Setup & Installation ---

# Sync dependencies
sync:
    @echo "🔄 Syncing dependencies..."
    uv sync --all-groups --all-extras

# Complete setup (install deps + types)
setup:
    @echo "🔧 Setting up Image Toolkit..."
    npm run setup
    uv sync --all-groups --all-extras
    @echo "✅ Setup complete!"
    @echo ""
    @echo "Next steps:"
    @echo "1. Setup database: just db-setup"
    @echo "2. Configure .env: cp frontend/src-tauri/.env.example frontend/src-tauri/.env"
    @echo "3. Run app: just dev"

# Install all dependencies
install:
    @echo "📦 Installing dependencies..."
    npm run install:all

# --- Building ---

# Build production application base
build-base:
    @echo "🏗️  Building production application base..."
    bash ./scripts/build_base.sh

# Build production application criptography JAR
build-jar:
    @echo "🏗️  Building production application criptography JAR..."
    ./gradlew build

# Build production application frontend
build-frontend:
    @echo "🏗️  Building production application frontend..."
    npm run build

# Build local OpenCV from source (bypasses system libopencv-dev requirement)
build-opencv:
    @echo "🔧 Building local OpenCV source..."
    cmake -B opencv/build opencv/ \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=OFF \
        -DBUILD_TESTS=OFF \
        -DBUILD_PERF_TESTS=OFF \
        -DBUILD_EXAMPLES=OFF \
        -DBUILD_opencv_apps=OFF \
        -DBUILD_opencv_python3=OFF \
        -DCMAKE_INSTALL_PREFIX=opencv/install \
        && cmake --build opencv/build -j$(nproc) \
        && cmake --install opencv/build
    @echo "✅ OpenCV built and installed to opencv/install."

# Build C++ batch extension (pybind11, OpenCV, Eigen3, OpenMP required)
# Install .so alongside base.so inside the Python animation package.
build-batch:
    @echo "🔧 Building C++ batch extension..."
    cmake -B build/batch batch/ \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_PREFIX_PATH="$(pwd)/opencv/install" \
        -DCMAKE_INSTALL_PREFIX="." \
        && cmake --build build/batch -j$(nproc) \
        && cmake --install build/batch
    @echo "✅ batch extension built and installed."

# Build everything: Rust base + Kotlin JAR + TypeScript frontend + C++ batch
build-all: build-base build-jar build-frontend build-batch

# --- Development ---

# Run Tauri app in development mode
dev:
    @echo "🚀 Starting Tauri development server..."
    npm run dev

# Run Rust type/compile checks
check:
    @echo "🔍 Running type checks..."
    npm run tauri:check

# setup + dev
quick-dev: setup dev

# --- Testing and Benchmarks ---

# Build + run native C++ batch tests via ctest (Catch2)
# Pure C++ — no Python required.
test-batch-cpp:
    @echo "🔧 Building C++ batch tests..."
    cmake -B build/batch batch/ \
        -DCMAKE_BUILD_TYPE=Debug \
        -DCMAKE_PREFIX_PATH="$(pwd)/opencv/install" \
        -DBATCH_BUILD_TESTS=ON \
        && cmake --build build/batch --target batch_tests -j$(nproc)
    @echo "🧪 Running native C++ batch tests..."
    ctest --test-dir build/batch -V --output-on-failure
    @echo "✅ Native C++ batch tests complete."

# Run Python parity tests (C++ vs Python reference implementations)
# and pybind11 import smoke tests.  Requires batch to be built first.
test-batch-py:
    @echo "🧪 Running Python batch parity + import tests..."
    source .venv/bin/activate \
    && pytest backend/test/animation/batch/ --skip-gpu -q --tb=short -m "not slow"
    @echo "✅ Python batch parity tests complete."

# Run speedup benchmarks (Python reference vs C++).  Slow — opt-in only.
test-batch-bench:
    @echo "⏱️  Running batch speedup benchmarks (slow)..."
    source .venv/bin/activate \
    && pytest backend/test/animation/batch/test_batch_benchmarks.py -v -m slow
    @echo "✅ Batch benchmarks complete."

# Run all batch tests: native C++ + Python parity (excludes slow benchmarks)
test-cpp: test-batch-cpp test-batch-py

# Run tests
test:
    @echo "🧪 Running tests..."
    npm run test
    cd frontend/src-tauri && cargo test

# Run benchmarks
benchmark:
    @echo "🏃 Running benchmarks..."
    source .venv/bin/activate && python backend/benchmark/run_all.py
    cd base && cargo bench

# Run benchmarks and save detailed reports
benchmark-save:
    @echo "🏃 Running benchmarks with detailed reporting..."
    source .venv/bin/activate && python backend/benchmark/run_all.py --save --report
    @echo "✅ Benchmark reports saved to backend/benchmark/results/"

# Launch benchmark analysis dashboard
benchmark-dashboard:
    @echo "📊 Launching Benchmark Dashboard..."
    @echo "Dashboard will open at http://localhost:8501"
    source .venv/bin/activate && streamlit run backend/ui/benchmark_dashboard.py

# --- ASP (Anime Stitch Pipeline) Benchmark ---
# Run the ASP benchmark on all datasets (asp_test01 … asp_test96).
# Results written to backend/benchmark/results/anime_stitch_YYYYMMDD_HHMMSS.json

# and a markdown report to data/output/benchmark_report.md.
asp-benchmark:
    @echo "🎞️  Running ASP benchmark on all 96 datasets..."
    source .venv/bin/activate && python -m backend.benchmark.bench_anime_stitch
    @echo "✅ ASP benchmark complete. Results in backend/benchmark/results/"

# Run ASP benchmark on specific named datasets.

# Usage: just asp-benchmark-tests asp_test09 asp_test27 asp_test57
asp-benchmark-tests *tests:
    @echo "🎞️  Running ASP benchmark on: {{ tests }}"
    source .venv/bin/activate && python -m backend.benchmark.bench_anime_stitch --tests {{ tests }}

# Run ASP benchmark on a numeric range of datasets.
# Usage: just asp-benchmark-range 1-10

# Usage: just asp-benchmark-range 4,8,27,57
asp-benchmark-range range:
    @echo "🎞️  Running ASP benchmark on range: {{ range }}"
    source .venv/bin/activate && python -m backend.benchmark.bench_anime_stitch --range "{{ range }}"

# Run ASP benchmark on the first N datasets.

# Usage: just asp-benchmark-first 5
asp-benchmark-first n="5":
    @echo "🎞️  Running ASP benchmark on first {{ n }} datasets..."
    source .venv/bin/activate && python -m backend.benchmark.bench_anime_stitch --first {{ n }}

# Run ASP benchmark only on datasets not yet processed (panorama.png absent).
asp-benchmark-resume:
    @echo "🎞️  Resuming ASP benchmark (skipping already-processed datasets)..."
    source .venv/bin/activate && python -m backend.benchmark.bench_anime_stitch --skip-done

# Run ASP benchmark on the standard quality-verification test suite:
# test09 (canonical seam-tear case), test27 (full-body portrait, asp_better),

# test08 (high-motion, simple_better), test57 (comparable), test04 (gate fallback).
asp-benchmark-verify:
    @echo "🎞️  Running ASP quality-verification suite (5 tests)..."
    source .venv/bin/activate && python -m backend.benchmark.bench_anime_stitch \
        --tests asp_test04 asp_test08 asp_test09 asp_test27 asp_test57
    @echo "✅ Verification complete. Check .agent/cache/pipeline_analysis_report.md"

# Clean ASP benchmark output directories
asp-benchmark-clean:
    @echo "🧹 Cleaning ASP benchmark output directories..."
    rm -rf dump/asp_test*/output
    rm -rf dump/output
    @echo "✅ Cleanup complete!"

# --- Database ---

# Setup PostgreSQL database
db-setup:
    @echo "🗄️  Setting up PostgreSQL database..."
    @sudo -u postgres psql -c "CREATE DATABASE image_toolkit;" || true
    @sudo -u postgres psql -c "CREATE USER toolkit_user WITH PASSWORD 'change_me_123';" || true
    @sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE image_toolkit TO toolkit_user;" || true
    @sudo -u postgres psql -d image_toolkit -c "CREATE EXTENSION IF NOT EXISTS vector;"
    @sudo -u postgres psql -c "ALTER DATABASE image_toolkit OWNER TO toolkit_user;"
    @echo "✅ Database setup complete!"
    @echo ""
    @echo "⚠️  Remember to:"
    @echo "1. Change the default password in your .env file"
    @echo "2. Update DATABASE_URL in frontend/src-tauri/.env"

# Check database connection
db-check:
    @echo "🔍 Checking database connection..."
    @psql postgresql://toolkit_user:change_me_123@localhost:5432/image_toolkit -c "SELECT version();" || echo "❌ Connection failed"

# Run database migrations
db-migrate:
    @echo "🔄 Running database migrations..."
    cd frontend/src-tauri && sqlx migrate run

# --- Maintenance ---

# Clean build artifacts
clean:
    @echo "🧹 Cleaning build artifacts..."
    find . -type d -name ".import_linter_cache" -exec rm -rf {} +
    find . -type d -name ".pytest_cache" -exec rm -rf {} +
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name ".ruff_cache" -exec rm -rf {} +
    find . -type d -name ".mypy_cache" -exec rm -rf {} +
    find . -type d -name ".hypothesis" -exec rm -rf {} +
    find . -type f -name "coverage.json" -exec rm {} +
    find . -type f -name "coverage.xml" -exec rm {} +
    find . -type f -name ".coverage" -exec rm {} +
    find . -type f -name ".gradle" -exec rm {} +
    rm -f hs_err_pid*.log
    rm -rf backend/benchmark/output/*
    rm -rf frontend/dist/
    rm -rf frontend/build/
    rm -rf frontend/node_modules/
    rm -rf frontend/src-tauri/target/
    rm -rf frontend/src-tauri/gen/schemas/
    rm -rf tmp/
    rm -rf target/
    rm -rf images/
    rm -rf build/batch/
    rm -rf node_modules/
    # Remove all empty directories recursively
    find . -type d -empty -delete
    @echo "✅ Clean complete!"

# Format code (Rust + TypeScript)
format:
    @echo "✨ Formatting code..."
    cd frontend/src-tauri && cargo fmt
    cd frontend && npm run format || echo "⚠️  No format script found"
    @echo "✅ Formatting complete!"

# Pyrefly type checking for backend
pyrefly-backend:
    @printf "{{ cyan }}╔════════════════════════════════════════════════════════════╗{{ reset }}\n"
    @printf "{{ cyan }}║{{ reset }} {{ bold }}%-58s{{ reset }}   {{ cyan }}║{{ reset }}\n" "🔍 STARTING PYREFLY TYPE CHECKING"
    @printf "{{ cyan }}╠════════════════════════════════════════════════════════════╣{{ reset }}\n"
    @printf "{{ cyan }}║{{ reset }} {{ yellow }}%-15s{{ reset }} {{ purple }}%-42s{{ reset }} {{ cyan }}║{{ reset }}\n" "Target:" "Backend"
    @printf "{{ cyan }}╚════════════════════════════════════════════════════════════╝{{ reset }}\n"
    uv run pyrefly check backend/src --output-format min-text --min-severity warn

# Pyrefly type checking for GUI
pyrefly-gui:
    @printf "{{ cyan }}╔════════════════════════════════════════════════════════════╗{{ reset }}\n"
    @printf "{{ cyan }}║{{ reset }} {{ bold }}%-58s{{ reset }}   {{ cyan }}║{{ reset }}\n" "🔍 STARTING PYREFLY TYPE CHECKING"
    @printf "{{ cyan }}╠════════════════════════════════════════════════════════════╣{{ reset }}\n"
    @printf "{{ cyan }}║{{ reset }} {{ yellow }}%-15s{{ reset }} {{ purple }}%-42s{{ reset }} {{ cyan }}║{{ reset }}\n" "Target:" "GUI"
    @printf "{{ cyan }}╚════════════════════════════════════════════════════════════╝{{ reset }}\n"
    uv run pyrefly check gui/src --output-format min-text --min-severity warn

# --- Web Driver & Crawler ---

# Run the Selenium WebDriver (chromedriver) required for crawlers
web-driver:
    @echo "🌐 Starting Managed Selenium WebDriver..."
    @source .venv/bin/activate && python scripts/manage_webdriver.py start

# Run the image crawler via CLI

# Usage: just crawl "https://example.com/gallery" 20 "./downloads"
crawl query limit="10" output="./downloads":
    source .venv/bin/activate && python main.py web crawl -q "{{ query }}" -l {{ limit }} -o "{{ output }}"

# --- Anime LoRA Fine-Tuning ---

size := "50"
rank := "16"
dataset := "data"
model := "illustrious_xl"
trigger := "akane_nanao"
class_prompt := "1girl"

# One-time: download WD-EVA02 tagger model + tags CSV (~355 MB) to models/wd14/
lora-setup-tagger:
    @echo "Downloading WD-EVA02 large tagger v3..."
    @mkdir -p models/wd14
    source .venv/bin/activate && python scripts/lora_setup_tagger.py
    @echo "Tagger ready at models/wd14/"

# One-time: apply the anime training DB schema migration
lora-db-migrate:
    @echo "Applying anime training schema..."
    @source .venv/bin/activate && python scripts/apply_migration.py \
        "${DATABASE_URL:-postgresql://toolkit_user:change_me_123@localhost:5432/image_toolkit}" \
        backend/src/database/sql/0007_anime_training.sql
    @echo "Migration applied."

# Caption all images in a directory with WD14 tags + optional Florence-2.
# Writes a .txt sidecar next to each image. Skip images that already have one.
# Usage: just lora-tag data/my_character my_char_xyz

# Usage: just lora-tag data/my_character my_char_xyz florence2=true
lora-tag images=dataset trigger=trigger florence2="true":
    @echo "Captioning images in {{ images }} with trigger '{{ trigger }}'..."
    @test -f models/wd14/model.onnx || (echo "WD14 tagger not found. Run: just lora-setup-tagger" && exit 1)
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.captioning.wd14_onnx=models/wd14/model.onnx \
        data.captioning.wd14_tags_csv=models/wd14/selected_tags.csv \
        data.captioning.use_florence2="{{ florence2 }}" \
        pipeline.run_extraction=false \
        pipeline.run_qa=false \
        pipeline.run_captioning=true \
        pipeline.run_dedup=false \
        pipeline.run_training=false
    @echo "Captioning done. Inspect .txt files in {{ images }}/ before training."

# Train a character LoRA on RTX 3090 Ti (24 GB).
# Default: Illustrious XL + Prodigy + rank 16, batch 4, 12 epochs.
# Usage: just lora-train data/my_character my_char_xyz

# Usage: just lora-train data/my_character my_char_xyz model=noobai_vpred size=80 rank=32
lora-train images=dataset trigger=trigger model=model size=size rank=rank:
    @echo "Training LoRA: trigger='{{ trigger }}' model={{ model }} rank={{ rank }} size={{ size }}"
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        model="{{ model }}" \
        training=lora_3090ti \
        optimizer=prodigy \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.target_dataset_size="{{ size }}" \
        training.rank="{{ rank }}" \
        run_name="{{ trigger }}_{{ model }}" \
        output_dir="outputs/{{ trigger }}_{{ model }}"
    @echo "Training complete. Checkpoints in outputs/{{ trigger }}_{{ model }}/"

# Train a character LoRA on RTX 4080 Laptop (16 GB).
# Uses gradient checkpointing + cached TE outputs to stay within 16 GB.

# Usage: just lora-train-4080 data/my_character my_char_xyz
lora-train-4080 images=dataset trigger=trigger model=model size=size rank=rank:
    @echo "Training LoRA (4080 profile): trigger='{{ trigger }}' model={{ model }}"
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        model="{{ model }}" \
        training=lora_4080 \
        optimizer=adamw8bit \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.target_dataset_size="{{ size }}" \
        training.rank="{{ rank }}" \
        run_name="{{ trigger }}_{{ model }}_4080" \
        output_dir="outputs/{{ trigger }}_{{ model }}_4080"
    @echo "Training complete. Checkpoints in outputs/{{ trigger }}_{{ model }}_4080/"

# Train a LyCORIS LoCon LoRA (captures character + tied art style).
# Use when the character has a distinctive unique artstyle.

# Usage: just lora-locon data/my_character my_char_xyz
lora-locon images=dataset trigger=trigger model=model size=size:
    @echo "Training LyCORIS LoCon: trigger='{{ trigger }}' model={{ model }}"
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        model="{{ model }}" \
        training=lycoris_locon \
        optimizer=adamw8bit \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.target_dataset_size="{{ size }}" \
        run_name="{{ trigger }}_locon" \
        output_dir="outputs/{{ trigger }}_locon"
    @echo "Training complete. Checkpoints in outputs/{{ trigger }}_locon/"

# Train NoobAI-XL V-Prediction LoRA (best raw anime character knowledge).
# Automatically sets v_prediction + zero_terminal_snr + snr_gamma=1.0.

# Usage: just lora-train-vpred data/my_character my_char_xyz
lora-train-vpred images=dataset trigger=trigger model=model size=size rank=rank:
    @echo "Training NoobAI V-Pred LoRA: trigger='{{ trigger }}'"
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        model=noobai_vpred \
        training=lora_3090ti \
        optimizer=prodigy \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.target_dataset_size="{{ size }}" \
        training.rank="{{ rank }}" \
        run_name="{{ trigger }}_noobai_vpred" \
        output_dir="outputs/{{ trigger }}_noobai_vpred"
    @echo "Training complete. Checkpoints in outputs/{{ trigger }}_noobai_vpred/"

# DreamBooth fine-tune with prior preservation (requires 24 GB).
# Generates 200 class images first, then trains full UNet + LoRA adapters.

# Usage: just lora-dreambooth data/my_character my_char_xyz
lora-dreambooth images=dataset trigger=trigger model=model class_prompt=class_prompt:
    @echo "DreamBooth: trigger='{{ trigger }}' class='{{ class_prompt }}'"
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        model="{{ model }}" \
        training=dreambooth \
        optimizer=adamw8bit \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.target_dataset_size=50 \
        training.class_prompt="{{ class_prompt }}" \
        run_name="{{ trigger }}_dreambooth" \
        output_dir="outputs/{{ trigger }}_dreambooth"
    @echo "DreamBooth complete. Checkpoints in outputs/{{ trigger }}_dreambooth/"

# Full SDXL checkpoint fine-tune with DeepSpeed ZeRO-2 (3090 Ti, ~12k steps).
# EMA enabled. Freezes VAE and text encoders by default.

# Usage: just lora-full-ft data/my_character my_char_xyz
lora-full-ft images=dataset trigger=trigger model=model:
    @echo "Full fine-tune: model={{ model }} trigger='{{ trigger }}'"
    @echo "This will take several hours. Ensure accelerate config has DeepSpeed ZeRO-2."
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        model="{{ model }}" \
        training=full_ft \
        optimizer=adamw8bit \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.target_dataset_size=200 \
        run_name="{{ trigger }}_full_ft" \
        output_dir="outputs/{{ trigger }}_full_ft"
    @echo "Full fine-tune complete. Checkpoints in outputs/{{ trigger }}_full_ft/"

# Run the complete pipeline: tag → deduplicate → train (3090 Ti profile).
# Convenience wrapper for first-time use.

# Usage: just lora-pipeline data/my_character my_char_xyz
lora-pipeline images=dataset trigger=trigger model=model size=size:
    @echo "=== Full pipeline: {{ trigger }} on {{ model }} ==="
    @test -f models/wd14/model.onnx || (echo "Run 'just lora-setup-tagger' first" && exit 1)
    source .venv/bin/activate && python -m backend.dispatcher command=train \
        model="{{ model }}" \
        training=lora_3090ti \
        optimizer=prodigy \
        data.images_dir="{{ images }}" \
        data.trigger_word="{{ trigger }}" \
        data.target_dataset_size="{{ size }}" \
        data.captioning.wd14_onnx=models/wd14/model.onnx \
        data.captioning.wd14_tags_csv=models/wd14/selected_tags.csv \
        pipeline.run_extraction=false \
        pipeline.run_qa=true \
        pipeline.run_captioning=true \
        pipeline.run_dedup=true \
        run_name="{{ trigger }}_{{ model }}" \
        output_dir="outputs/{{ trigger }}_{{ model }}"
    @echo "=== Pipeline complete. See outputs/{{ trigger }}_{{ model }}/ ==="

# Analyse a trained LoRA checkpoint: SVD effective rank + weight delta heatmap.
# Prints a table of under/over-utilised layers to guide rank tuning.

# Usage: just lora-analyze outputs/my_char_lora/checkpoint-epoch0010
lora-analyze checkpoint="outputs":
    @echo "Analysing LoRA weights in {{ checkpoint }}..."
    source .venv/bin/activate && python scripts/lora_analyze.py "{{ checkpoint }}"

# Launch TensorBoard to monitor active or completed training runs.
lora-tensorboard dir="runs":
    @echo "Starting TensorBoard at http://localhost:6006 (Ctrl+C to stop)"
    source .venv/bin/activate && tensorboard --logdir {{ dir }} --port 6006

# --- ComfyUI ---

# Start ComfyUI headlessly (without the main desktop app)
comfyui args="":
    @echo "🎨 Starting ComfyUI server..."
    source .venv/bin/activate && python -m backend.dispatcher command=comfyui {{ args }}

# Stop any running ComfyUI instances
comfyui-stop:
    @echo "🛑 Stopping ComfyUI server..."
    -pkill -f "ComfyUI/main.py"

# --- Desktop GUI ---

# Start the Desktop GUI Application
gui args="":
    @echo "🐍 Starting Image-Toolkit Desktop App..."
    source .venv/bin/activate && python main.py gui {{ args }}

# Start the Desktop GUI with ComfyUI-Manager integration enabled
gui-manager:
    @echo "🛠️ Starting Image-Toolkit with Manager integration..."
    source .venv/bin/activate && python main.py gui --enable-manager

# --- Core Operations ---

# Run the 'Perfect Stitch' pipeline on the default data directory
perfect-stitch images="/home/pkhunter/Downloads/data/new/" output="/home/pkhunter/Downloads/data/new/stitched_panorama.png":
    @echo "🎞️ Starting Perfect Stitch on {{ images }}..."
    source .venv/bin/activate && python main.py core stitch -i "{{ images }}" -o "{{ output }}"

# Batch convert images in a directory

# Usage: just convert-batch ./input_dir png
convert-batch input format="png" output="":
    @echo "🖼️ Batch converting images in {{ input }} to {{ format }}..."
    source .venv/bin/activate && python main.py core convert -i "{{ input }}" -f {{ format }} {{ if output != "" { "-o " + output } else { "" } }}

# Merge images into a strip or grid

# Usage: just merge-images "./img1.png ./img2.png" ./output.png vertical
merge-images inputs output direction="horizontal":
    @echo "🧩 Merging images {{ direction }}ly..."
    source .venv/bin/activate && python main.py core merge -i {{ inputs }} -o "{{ output }}" -d {{ direction }}

# Start the background slideshow daemon
slideshow:
    @echo "🖼️ Starting slideshow daemon..."
    source .venv/bin/activate && python main.py slideshow

# --- AI Assistant ---

# Loops the Claude Code agent on a stateful context with live-streaming reasoning steps
loop-agent prompt="Continue upgrading the ASP, while continuing to update the ASP-related markdown files like the changelog and roadmaps. After analysing the relevant files, but before beginning the implementation, always ask questions to clarify assumptions or missing requirements, and to select which options to purse from the specific roadmaps.":
    #!/usr/bin/env bash
    set -euo pipefail

    # Setup an explicit, warm session instructions cache file
    FEED_FILE="/tmp/claude_agent_feed.txt"
    rm -f "$FEED_FILE"
    touch "$FEED_FILE"

    echo "=== Initializing Stateful Agent Memory Context ==="

    # We populate the initial task parameters into our warm text feed
    echo "{{ prompt }}" > "$FEED_FILE"

    # Start an active, persistent state cycle
    while true; do
        # 1. Read what current objective is pending in our state feed
        CURRENT_TASK=$(cat "$FEED_FILE")

        echo -e "\n[Loop Monitor] Injecting iterative task context down stream..."

        # 2. Invoke the agent in verbose non-interactive stream mode.
        # --verbose strips away text buffers and prints the thoughts letter-by-letter as they happen.
        # This prevents the terminal spinner from swallowing the reasoning chains.
        claude --dangerously-skip-permissions --verbose -p "$CURRENT_TASK"

        echo -e "\n[Loop Monitor] Iteration complete. Re-seeding context step..."

        # 3. Maintain warm memory context across loops by appending instructions to check its own work.
        # This keeps the agent localized within the exact same task state.
        echo "Review the updates you just made to the ASP files, changelog, and roadmaps in the previous step. Continue optimizing the files and extending features based on your current state." > "$FEED_FILE"

        # Short cooldown pause before parsing the next sequential state change
        sleep 5
    done

# --- Codebase Validation ---

# Count lines of code and comments (use --group-by-dir N to aggregate by directory depth)
count-loc group_by="0":
    uv run python backend/src/utils/validation/count_loc.py backend/src --group-by-dir {{ group_by }}

# Tree view of lines of code and comments
tree-loc:
    uv run python backend/src/utils/validation/tree_loc.py backend/src

# Check docstring coverage
check-docs:
    uv run python backend/src/utils/docs/check_docstrings.py backend/src
    uv run python backend/src/utils/docs/check_docstrings.py gui/src

# Check Google style docstrings
check-google-docs:
    uv run python backend/src/utils/docs/check_google_style.py backend/src

# Check for multiple classes in one file
check-multi-classes:
    uv run python backend/src/utils/validation/check_multi_classes.py backend/src

# Find all relative imports (from .module import ...) with optional stats or exclude_same_package=true
check-relative-imports exclude_same_package="":
    uv run python backend/src/utils/validation/check_relative_imports.py backend/src \
        --stats \
        {{ if exclude_same_package != "" { "--exclude-same-package" } else { "" } }}

# Check for nested imports (add --stats for a per-package summary table)
check-nested-imports:
    uv run python backend/src/utils/validation/check_nested_imports.py backend/src --ignore_factories

# Check for nested imports with a per-package summary table
check-nested-imports-stats:
    uv run python backend/src/utils/validation/check_nested_imports.py backend/src --ignore_factories --stats

# Detect circular import chains using Tarjan's SCC algorithm
check-circular-imports html="":
    uv run python backend/src/utils/validation/check_circular_imports.py backend/src \
        {{ if html != "" { "--html " + html } else { "" } }}

# Check that all concrete classes fully implement their ABC/Protocol interface contracts
check-interface-compliance:
    uv run python backend/src/utils/validation/check_interface_compliance.py backend/src

# Measure type annotation coverage per file (worst-coverage files shown first)
check-type-coverage sort="coverage" limit="40":
    uv run python backend/src/utils/validation/check_type_coverage.py backend/src \
        --sort {{ sort }} --limit {{ limit }}

# Generate interactive module-level import graph (opens in browser)
# Scans from repo root so backend/gui layers are correctly distinguished.
# Use depth=N to collapse to top-N package levels; set html= to change output path.
module-graph html="module_graph.html" depth="10":
    uv run python backend/src/utils/validation/visualize_module_graph.py ./backend/src \
        --exclude .venv venv node_modules \
        --html {{ html }} --depth {{ depth }}

# Create a graph with exported and imported dependencies (function, classes, etc.)
dependency-graph target_file="backend/src/utils/decorators.py" target_name="log_call":
    uv run python backend/src/utils/validation/trace_dependencies.py backend/src {{ target_file }} {{ target_name }}

# Check for embedded languages in the Python source code
check-embedded-languages:
    uv run python backend/src/utils/validation/check_embedded_languages.py backend/src

# Check for unused imports in the Python source code
check-unused-imports:
    uv run python backend/src/utils/validation/check_unused_imports.py backend/src --ignore_factories

# Check uppercase constant declarations across backend and gui directories
check-constants:
    uv run python backend/src/utils/validation/constant_checker.py

# --- Legacy/Helper ---

# Embed an image icon as metadata into a safetensors file
# Usage: just embed-icon path/to/model.safetensors path/to/icon.png
embed-icon model_path image_path:
    @echo "Embedding icon into {{ model_path }}..."
    source .venv/bin/activate && python -m backend.dispatcher command=embed_metadata \
        data=embed_metadata \
        data.embed_metadata.model_path="'{{ model_path }}'" \
        data.embed_metadata.image_path="'{{ image_path }}'"

# Legacy alias for 'gui'
python args="":
    source .venv/bin/activate && python main.py {{ args }}
