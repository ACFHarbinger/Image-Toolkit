# Image Toolkit - Justfile
# Convenience commands to run the application from project root

set shell := ["bash", "-c"]

# Default target - List all available recipes
default:
    @just --list

# --- Setup & Installation ---

# Sync dependencies
sync:
    @echo "🔄 Syncing dependencies..."
    uv sync --all-groups --all-extras
    npm run install:all

# Complete setup (install deps + types)
setup:
    @echo "🔧 Setting up Image Toolkit..."
    npm run setup
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

# --- Development ---

# Run Tauri app in development mode
dev:
    @echo "🚀 Starting Tauri development server..."
    npm run dev

# Build production application
build:
    @echo "🏗️  Building production application..."
    bash ./scripts/build_base.sh
    ./gradlew build
    npm run build

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

# Run Rust type/compile checks
check:
    @echo "🔍 Running type checks..."
    npm run tauri:check

# setup + dev
quick-dev: setup dev

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
    rm -rf frontend/dist
    rm -rf frontend/build
    rm -rf frontend/src-tauri/target
    rm -rf node_modules
    rm -rf frontend/node_modules
    @echo "✅ Clean complete!"

# Format code (Rust + TypeScript)
format:
    @echo "✨ Formatting code..."
    cd frontend/src-tauri && cargo fmt
    cd frontend && npm run format || echo "⚠️  No format script found"
    @echo "✅ Formatting complete!"

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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=train \
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

# Embed an image icon as metadata into a safetensors file
# Usage: just embed-icon path/to/model.safetensors path/to/icon.png
embed-icon model_path image_path:
    @echo "Embedding icon into {{ model_path }}..."
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=embed_metadata \
        +data=embed_metadata \
        data.embed_metadata.model_path="{{ model_path }}" \
        data.embed_metadata.image_path="{{ image_path }}"

# Start ComfyUI headlessly (without the main desktop app)
comfyui args="":
    @echo "🎨 Starting ComfyUI server..."
    source .venv/bin/activate && python -m backend.src.controller.dispatcher command=comfyui {{ args }}

# Stop any running ComfyUI instances
comfyui-stop:
    @echo "🛑 Stopping ComfyUI server..."
    -pkill -f "ComfyUI/main.py"

# Start the Desktop GUI Application
gui args="":
    @echo "🐍 Starting Image-Toolkit Desktop App..."
    source .venv/bin/activate && python main.py gui {{ args }}

# Start the Desktop GUI with ComfyUI-Manager integration enabled
gui-manager:
    @echo "🛠️ Starting Image-Toolkit with Manager integration..."
    source .venv/bin/activate && python main.py gui --enable-manager

# --- Legacy/Helper ---

# Legacy alias for 'gui'
python args="":
    source .venv/bin/activate && python main.py {{ args }}
