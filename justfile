# Image Toolkit - Root Justfile
# Entry point. All recipes delegate to sub-modules via `mod`.
# Invoke sub-module recipes directly with dot notation: just build.build-all
# Or use the root shorthands defined below.

set shell := ["bash", "-c"]
set unstable := true

red := '\033[0;31m'
green := '\033[0;32m'
yellow := '\033[0;33m'
blue := '\033[0;34m'
purple := '\033[0;35m'
cyan := '\033[0;36m'
bold := '\033[1m'
reset := '\033[0m'

# --- Default variables (can be overridden on the command line) ---

size := "50"
rank := "16"
dataset := "data"
model := "illustrious_xl"
trigger := "akane_nanao"
class_prompt := "1girl"

# --- Sub-module declarations ---

mod agent      "tools/agent/justfile"
mod benchmark  "tools/benchmark/justfile"
mod build      "tools/build/justfile"
mod ci         "tools/ci/justfile"
mod core       "tools/core/justfile"
mod database   "tools/database/justfile"
mod dev        "tools/dev/justfile"
mod gui        "tools/gui/justfile"
mod helper     "tools/helper/justfile"
mod model      "tools/model/justfile"
mod reducer    "tools/reducer/justfile"
mod repository "tools/repository/justfile"
mod test       "tools/test/justfile"
mod validation "tools/validation/justfile"
mod web        "tools/web/justfile"

# --- Default target ---

default: help

# --- Help ---

# Print available commands
help: helper::_print_header
    just helper::help

# --- Setup & Installation ---

# Sync uv dependencies
sync: helper::_print_header
    just dev::sync

# Complete setup (install deps + types)
setup: helper::_print_header
    just dev::setup

# Install all dependencies
install: helper::_print_header
    just dev::install

# --- Development ---

# Run Rust type/compile checks
check: helper::_print_header
    just dev::check

# setup + dev
quick-dev: helper::_print_header
    just dev::quick-dev

# --- Building ---

# Build C++ base extension (Phase 7: batch/ renamed to base/, Rust retired)
build-base: helper::_print_header
    just build::build-base

# Build production application cryptography JAR
build-jar: helper::_print_header
    just build::build-jar

# Build production application frontend
build-frontend: helper::_print_header
    just build::build-frontend

# Build browser extension for all targets (chrome, firefox, edge, brave)
build-extension: helper::_print_header
    just build::build-extension

# Build local OpenCV from source
build-opencv: helper::_print_header
    just build::build-opencv

# Build everything: C++ base + Kotlin JAR + TypeScript frontend
build-all: helper::_print_header
    just build::build-all

# --- Testing ---

# Build + run native C++ base tests via ctest (Catch2)
test-base-cpp: helper::_print_header
    just test::test-base-cpp

# Alias kept for backwards compatibility
test-batch-cpp: test-base-cpp

# Run Python parity tests (C++ vs Python reference implementations)
test-base-py: helper::_print_header
    just test::test-base-py

# Alias kept for backwards compatibility
test-batch-py: test-base-py

# Run speedup benchmarks (Python reference vs C++). Slow — opt-in only.
test-base-bench: helper::_print_header
    just test::test-base-bench

# Alias kept for backwards compatibility
test-batch-bench: test-base-bench

# Run all base tests: native C++ + Python parity
test-cpp: helper::_print_header
    just test::test-cpp

# --- Benchmarks ---

# Run benchmarks and save detailed reports
benchmark-save: helper::_print_header
    just benchmark::benchmark-save

# Launch benchmark analysis dashboard
benchmark-dashboard: helper::_print_header
    just benchmark::benchmark-dashboard

# Run the ASP benchmark on all datasets (asp_test01 … asp_test96)
asp-benchmark: helper::_print_header
    just benchmark::asp-benchmark

# Run ASP benchmark on specific named datasets
# Usage: just asp-benchmark-tests asp_test09 asp_test27 asp_test57
asp-benchmark-tests *tests: helper::_print_header
    just benchmark::asp-benchmark-tests {{tests}}

# Run ASP benchmark on a numeric range of datasets
# Usage: just asp-benchmark-range 1-10
asp-benchmark-range range: helper::_print_header
    just benchmark::asp-benchmark-range {{range}}

# Run ASP benchmark on the first N datasets
# Usage: just asp-benchmark-first 5
asp-benchmark-first n="5": helper::_print_header
    just benchmark::asp-benchmark-first {{n}}

# Run ASP benchmark only on datasets not yet processed (panorama.png absent)
asp-benchmark-resume: helper::_print_header
    just benchmark::asp-benchmark-resume

# Run ASP benchmark on the standard quality-verification test suite
asp-benchmark-verify: helper::_print_header
    just benchmark::asp-benchmark-verify

# Clean ASP benchmark output directories
asp-benchmark-clean: helper::_print_header
    just benchmark::asp-benchmark-clean

# --- Database ---

# Setup PostgreSQL database with pgvector extension
db-setup: helper::_print_header
    just database::db-setup

# Check database connection
db-check: helper::_print_header
    just database::db-check

# Run database migrations
db-migrate: helper::_print_header
    just database::db-migrate

# Apply the anime training DB schema migration (one-time)
lora-db-migrate: helper::_print_header
    just database::lora-db-migrate

# --- Maintenance ---

# Clean build artifacts and caches
clean: helper::_print_header
    just reducer::clean

# Clean ASP benchmark output directories
clean-outputs: helper::_print_header
    just reducer::clean-outputs

# --- CI / Linting ---

# Format code (Rust + TypeScript)
format: helper::_print_header
    just ci::format

# Pyrefly type checking for backend
pyrefly-backend: helper::_print_header
    just ci::pyrefly-backend

# Pyrefly type checking for GUI
pyrefly-gui: helper::_print_header
    just ci::pyrefly-gui

# --- Web / Crawler ---

# Run the Selenium WebDriver (chromedriver) required for crawlers
web-driver: helper::_print_header
    just web::web-driver

# Run the image crawler via CLI
# Usage: just crawl "https://example.com/gallery" 20 "./downloads"
crawl query limit="10" output="./downloads": helper::_print_header
    just web::crawl '{{query}}' '{{limit}}' '{{output}}'

# --- LoRA Fine-Tuning ---

# One-time: download WD-EVA02 tagger model + tags CSV (~355 MB)
lora-setup-tagger: helper::_print_header
    just model::lora-setup-tagger

# Caption all images in a directory with WD14 tags + optional Florence-2
# Usage: just lora-tag data/my_character my_char_xyz
lora-tag images=dataset trigger=trigger florence2="true": helper::_print_header
    just model::lora-tag '{{images}}' '{{trigger}}' '{{florence2}}'

# Train a character LoRA on RTX 3090 Ti (24 GB)
# Usage: just lora-train data/my_character my_char_xyz
lora-train images=dataset trigger=trigger model=model size=size rank=rank: helper::_print_header
    just model::lora-train '{{images}}' '{{trigger}}' '{{model}}' '{{size}}' '{{rank}}'

# Train a character LoRA on RTX 4080 Laptop (16 GB)
# Usage: just lora-train-4080 data/my_character my_char_xyz
lora-train-4080 images=dataset trigger=trigger model=model size=size rank=rank: helper::_print_header
    just model::lora-train-4080 '{{images}}' '{{trigger}}' '{{model}}' '{{size}}' '{{rank}}'

# Train a LyCORIS LoCon LoRA (captures character + tied art style)
# Usage: just lora-locon data/my_character my_char_xyz
lora-locon images=dataset trigger=trigger model=model size=size: helper::_print_header
    just model::lora-locon '{{images}}' '{{trigger}}' '{{model}}' '{{size}}'

# Train NoobAI-XL V-Prediction LoRA
# Usage: just lora-train-vpred data/my_character my_char_xyz
lora-train-vpred images=dataset trigger=trigger model=model size=size rank=rank: helper::_print_header
    just model::lora-train-vpred '{{images}}' '{{trigger}}' '{{model}}' '{{size}}' '{{rank}}'

# DreamBooth fine-tune with prior preservation (requires 24 GB)
# Usage: just lora-dreambooth data/my_character my_char_xyz
lora-dreambooth images=dataset trigger=trigger model=model class_prompt=class_prompt: helper::_print_header
    just model::lora-dreambooth '{{images}}' '{{trigger}}' '{{model}}' '{{class_prompt}}'

# Full SDXL checkpoint fine-tune with DeepSpeed ZeRO-2 (3090 Ti, ~12k steps)
# Usage: just lora-full-ft data/my_character my_char_xyz
lora-full-ft images=dataset trigger=trigger model=model: helper::_print_header
    just model::lora-full-ft '{{images}}' '{{trigger}}' '{{model}}'

# Run the complete pipeline: tag → deduplicate → train (3090 Ti profile)
# Usage: just lora-pipeline data/my_character my_char_xyz
lora-pipeline images=dataset trigger=trigger model=model size=size: helper::_print_header
    just model::lora-pipeline '{{images}}' '{{trigger}}' '{{model}}' '{{size}}'

# Analyse a trained LoRA checkpoint: SVD effective rank + weight delta heatmap
# Usage: just lora-analyze outputs/my_char_lora/checkpoint-epoch0010
lora-analyze checkpoint="outputs": helper::_print_header
    just model::lora-analyze '{{checkpoint}}'

# Launch TensorBoard to monitor active or completed training runs
lora-tensorboard dir="runs": helper::_print_header
    just model::lora-tensorboard '{{dir}}'

# Embed an image icon as metadata into a safetensors file
# Usage: just embed-icon path/to/model.safetensors path/to/icon.png
embed-icon model_path image_path: helper::_print_header
    just model::embed-icon '{{model_path}}' '{{image_path}}'

# --- External Repositories ---

# Start ComfyUI headlessly (without the main desktop app)
comfyui args="": helper::_print_header
    just repository::comfyui '{{args}}'

# Stop any running ComfyUI instances
comfyui-stop: helper::_print_header
    just repository::comfyui-stop

# --- Desktop GUI ---

# Start the Desktop GUI with ComfyUI-Manager integration enabled
gui-manager: helper::_print_header
    just gui::gui-manager

# --- Core Image Processing ---

# Run the 'Perfect Stitch' pipeline on the default data directory
perfect-stitch images="/home/pkhunter/Downloads/data/new/" output="/home/pkhunter/Downloads/data/new/stitched_panorama.png": helper::_print_header
    just core::perfect-stitch '{{images}}' '{{output}}'

# Batch convert images in a directory
# Usage: just convert-batch ./input_dir png
convert-batch input format="png" output="": helper::_print_header
    just core::convert-batch '{{input}}' '{{format}}' '{{output}}'

# Merge images into a strip or grid
# Usage: just merge-images "./img1.png ./img2.png" ./output.png vertical
merge-images inputs output direction="horizontal": helper::_print_header
    just core::merge-images '{{inputs}}' '{{output}}' '{{direction}}'

# Start the background slideshow daemon
slideshow: helper::_print_header
    just core::slideshow

# --- Validation ---

# Count lines of code and comments
count-loc group_by="0": helper::_print_header
    just validation::count-loc '{{group_by}}'

# Tree view of lines of code and comments
tree-loc: helper::_print_header
    just validation::tree-loc

# Check docstring coverage
check-docs: helper::_print_header
    just validation::check-docs

# Check Google style docstrings
check-google-docs: helper::_print_header
    just validation::check-google-docs

# Check for multiple classes in one file
check-multi-classes: helper::_print_header
    just validation::check-multi-classes

# Find all relative imports
check-relative-imports exclude_same_package="": helper::_print_header
    just validation::check-relative-imports '{{exclude_same_package}}'

# Check for nested imports
check-nested-imports: helper::_print_header
    just validation::check-nested-imports

# Check for nested imports with a per-package summary table
check-nested-imports-stats: helper::_print_header
    just validation::check-nested-imports-stats

# Detect circular import chains using Tarjan's SCC algorithm
check-circular-imports html="": helper::_print_header
    just validation::check-circular-imports '{{html}}'

# Check that all concrete classes fully implement their ABC/Protocol interface contracts
check-interface-compliance: helper::_print_header
    just validation::check-interface-compliance

# Measure type annotation coverage per file
check-type-coverage sort="coverage" limit="40": helper::_print_header
    just validation::check-type-coverage '{{sort}}' '{{limit}}'

# Generate interactive module-level import graph (opens in browser)
module-graph html="module_graph.html" depth="10": helper::_print_header
    just validation::module-graph '{{html}}' '{{depth}}'

# Create a graph with exported and imported dependencies
dependency-graph target_file="backend/src/utils/decorators.py" target_name="log_call": helper::_print_header
    just validation::dependency-graph '{{target_file}}' '{{target_name}}'

# Check for embedded languages in the Python source code
check-embedded-languages: helper::_print_header
    just validation::check-embedded-languages

# Check for unused imports in the Python source code
check-unused-imports: helper::_print_header
    just validation::check-unused-imports

# Check uppercase constant declarations across backend and gui directories
check-constants: helper::_print_header
    just validation::check-constants

# --- Helpers ---

# Commit staged changes with Gemini as co-author
commit message: helper::_print_header
    just helper::commit '{{message}}'

# Legacy alias for 'gui' — run Python/PySide6 app directly
python args="": helper::_print_header
    just helper::python {{args}}

# Loop the Claude Code agent on a stateful context
loop-agent prompt="Continue upgrading the ASP, while continuing to update the ASP-related markdown files like the changelog and roadmaps. After analysing the relevant files, but before beginning the implementation, always ask questions to clarify assumptions or missing requirements, and to select which options to purse from the specific roadmaps.": helper::_print_header
    just agent::loop-agent '{{prompt}}'
