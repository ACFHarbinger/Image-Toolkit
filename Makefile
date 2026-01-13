# Image Toolkit - Makefile
# Convenience commands to run the application from project root

.PHONY: help setup dev build clean test db-setup db-check install

# Default target
help:
	@echo "Image Toolkit - Available Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup        - Complete setup (install deps + types)"
	@echo "  make install      - Install all dependencies"
	@echo "  make db-setup     - Setup PostgreSQL database"
	@echo ""
	@echo "Development:"
	@echo "  make dev          - Run Tauri app in development mode"
	@echo "  make build        - Build production application"
	@echo "  make test         - Run tests"
	@echo "  make check        - Run Rust type/compile checks"
	@echo ""
	@echo "Database:"
	@echo "  make db-check     - Check database connection"
	@echo "  make db-migrate   - Run database migrations"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make format       - Format code (Rust + TypeScript)"
	@echo ""

# Setup and installation
setup:
	@echo "🔧 Setting up Image Toolkit..."
	npm run setup
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Setup database: make db-setup"
	@echo "2. Configure .env: cp frontend/src-tauri/.env.example frontend/src-tauri/.env"
	@echo "3. Run app: make dev"

install:
	@echo "📦 Installing dependencies..."
	npm run install:all

# Development
dev:
	@echo "🚀 Starting Tauri development server..."
	npm run dev

build:
	@echo "🏗️  Building production application..."
	npm run build

test:
	@echo "🧪 Running tests..."
	npm run test
	cd frontend/src-tauri && cargo test

check:
	@echo "🔍 Running type checks..."
	npm run tauri:check

# Database operations
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

db-check:
	@echo "🔍 Checking database connection..."
	@psql postgresql://toolkit_user:change_me_123@localhost:5432/image_toolkit -c "SELECT version();" || echo "❌ Connection failed"

db-migrate:
	@echo "🔄 Running database migrations..."
	cd frontend/src-tauri && sqlx migrate run

# Maintenance
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf frontend/dist
	rm -rf frontend/build
	rm -rf frontend/src-tauri/target
	rm -rf node_modules
	rm -rf frontend/node_modules
	@echo "✅ Clean complete!"

format:
	@echo "✨ Formatting code..."
	cd frontend/src-tauri && cargo fmt
	cd frontend && npm run format || echo "⚠️  No format script found"
	@echo "✅ Formatting complete!"

# Quick starts
quick-dev: setup dev

# Python backend (legacy)
python-dev:
	@echo "🐍 Starting Python/PySide6 app..."
	source .venv/bin/activate && python main.py
