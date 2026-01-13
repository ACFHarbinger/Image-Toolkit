#!/bin/bash
# Image Toolkit - Quick Run Script
# Run this from the project root to start the application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Image Toolkit - Tauri Edition       ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
echo ""

# Check if .env exists
if [ ! -f "frontend/src-tauri/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found!${NC}"
    echo ""
    echo "Creating .env from template..."
    cp frontend/src-tauri/.env.example frontend/src-tauri/.env
    echo -e "${GREEN}✓${NC} .env file created at frontend/src-tauri/.env"
    echo ""
    echo -e "${YELLOW}Please edit this file and update DATABASE_URL with your credentials!${NC}"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to exit..."
fi

# Check if node_modules exists
if [ ! -d "node_modules" ] || [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠️  Dependencies not installed${NC}"
    echo ""
    echo "Installing dependencies..."
    npm run install:all
    echo -e "${GREEN}✓${NC} Dependencies installed"
    echo ""
fi

# Check if @types/react-dom is installed
if [ ! -d "node_modules/@types/react-dom" ]; then
    echo "Installing TypeScript types..."
    npm install --save-dev @types/react-dom
    echo -e "${GREEN}✓${NC} Types installed"
    echo ""
fi

# Check PostgreSQL connection
echo -e "${BLUE}Checking database connection...${NC}"
if psql postgresql://toolkit_user:change_me_123@localhost:5432/image_toolkit -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Database connection successful"
else
    echo -e "${YELLOW}⚠️  Database connection failed${NC}"
    echo ""
    echo "Please ensure PostgreSQL is running and configured correctly."
    echo "Run 'make db-setup' to create the database, or see SETUP.md for help."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}Starting Tauri development server...${NC}"
echo ""
npm run dev
