# Image Toolkit - Justfile
# Convenience commands to run the application from project root

set shell := ["bash", "-c"]

# Default target - List all available recipes
default:
    @just --list

# --- Setup & Installation ---

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
    npm run build

# Run tests
test:
    @echo "🧪 Running tests..."
    npm run test
    cd frontend/src-tauri && cargo test

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

# --- Legacy/Helper ---

# Starting Python/PySide6 app
python:
    @echo "🐍 Starting Python/PySide6 app..."
    source .venv/bin/activate && python main.py
