# Image-Toolkit

A powerful image database and editing toolkit with semantic search, batch processing, and AI-powered features.

## 🚀 Quick Start

### Prerequisites Check

```bash
# Check if you have the required tools
rustc --version  # Should be 1.70+
node --version   # Should be 18+
psql --version   # Should be 14+
python3 --version # Should be 3.11+
```

### 5-Minute Setup

**Step 1: Database Setup (2 minutes)**

```bash
# Install pgvector (if not already installed)
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make && sudo make install

# Create database
sudo -u postgres psql << 'EOF'
CREATE DATABASE image_toolkit;
CREATE USER toolkit_user WITH PASSWORD 'change_me_123';
GRANT ALL PRIVILEGES ON DATABASE image_toolkit TO toolkit_user;
\c image_toolkit
CREATE EXTENSION vector;
ALTER DATABASE image_toolkit OWNER TO toolkit_user;
EOF
```

**Step 2: Configure Environment (1 minute)**

```bash
cd frontend/src-tauri

# Create .env file
cat > .env << 'EOF'
DATABASE_URL=postgresql://toolkit_user:change_me_123@localhost:5432/image_toolkit
RUST_LOG=info
EOF
```

**Step 3: Install Dependencies (1 minute)**

```bash
# From project root
npm run setup
```

**Step 4: Run the Application (1 minute)**

**Option 1: Quick Run Script (Recommended)**
```bash
./run.sh
```

**Option 2: Using npm**
```bash
npm run dev
```

**Option 3: Using Make**
```bash
make dev
```

**Option 4: From frontend directory**
```bash
cd frontend
npm run tauri dev
```

**First time?** This will take a few minutes to compile Rust dependencies.

**Step 5: Create Your Account**

1. Application launches → Login dialog appears
2. Click **"Create New Account"**
3. Enter account name (e.g., "MyAccount")
4. Set a master password
5. Click **"Create Account"**

**You're done!** ✅

After login, you should see:
- ✅ Green "DB Connected" in the header
- Navigation tabs on the left
- Convert tab open by default

---

## ✨ Features

### Core Capabilities
- 🖼️ **Image Database** - PostgreSQL with pgvector for semantic search
- 🔍 **Advanced Search** - Filter by tags, groups, formats, and visual similarity
- 🔄 **Batch Processing** - Convert, merge, and manipulate images in bulk
- 🖥️ **Wallpaper Manager** - KDE/GNOME wallpaper automation with slideshow
- 🎬 **Video Tools** - Extract frames and clips from videos
- 🌐 **Web Integration** - Image crawlers, reverse search, cloud sync
- 🤖 **AI Models** - Training, inference, and generation pipelines

### Tech Stack
- **Frontend:** [React](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/) + [Tauri](https://tauri.app/)
- **Backend:** [Rust](https://www.rust-lang.org/) (PyO3) + [Python](https://www.python.org/)
- **Database:** [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector)
- **Legacy GUI:** [PySide6](https://doc.qt.io/qtforpython-6/)
- **Mobile:** [Kotlin](https://kotlinlang.org/) (Android) + [Swift](https://www.swift.org/) (iOS)

---

## 📦 Installation & Setup

### System Requirements

#### All Platforms
- **Rust** (1.70+)
- **Node.js** (18+) and npm
- **PostgreSQL** (14+) with pgvector extension
- **Python** (3.11+) for backend modules

#### Linux
```bash
sudo apt update
sudo apt install -y build-essential curl wget libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev binutils qdbus-qt6 qt6-base-dev-tools
```

#### macOS
```bash
# Install Xcode Command Line Tools
xcode-select --install
```

#### Windows
- Install [Visual Studio C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- Install [WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)

### Install Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

Verify installation:
```bash
rustc --version
cargo --version
```

### Install Node.js Dependencies

**From project root (recommended):**
```bash
npm run setup
# This installs all dependencies including TypeScript types
```

**Or manually:**
```bash
npm install
cd frontend
npm install
cd ..
npm install --save-dev @types/react-dom
```

### Setup PostgreSQL with pgvector

#### Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt install postgresql postgresql-contrib
```

**macOS (Homebrew):**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Windows:**
Download and install from [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)

#### Install pgvector Extension

**From Source:**
```bash
cd /tmp
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

**macOS (Homebrew):**
```bash
brew install pgvector
```

#### Create Database and Enable Extension

```bash
# Start PostgreSQL service (if not running)
sudo systemctl start postgresql  # Linux
# or
brew services start postgresql@14  # macOS

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE image_toolkit;
CREATE USER toolkit_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE image_toolkit TO toolkit_user;
\c image_toolkit
CREATE EXTENSION IF NOT EXISTS vector;
ALTER DATABASE image_toolkit OWNER TO toolkit_user;
EOF
```

### Configure Environment Variables

```bash
# Copy example environment file
cd frontend/src-tauri
cp .env.example .env

# Edit .env and update with your database credentials
nano .env
```

Update `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql://toolkit_user:your_secure_password@localhost:5432/image_toolkit
RUST_LOG=info
```

### Setup Python Environment (for backend modules)

#### UV
To use the [UV Python package and project manager](https://github.com/astral-sh/uv) to setup the virtual environment:
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create environment
uv init --python 3.11 --name image-toolkit

# Install dependencies
uv add -r env/requirements.txt
uv add --dev env/dev_requirements.txt

# Or just sync
uv sync
```

Afterwards, initialize the virtual environment:
```bash
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate.bat  # Windows CMD
# or
.venv\Scripts\Activate.ps1  # Windows PS
```

#### Anaconda Environment
To setup using [Anaconda distribution](https://www.anaconda.com/):
```bash
conda env create --file env/environment.yml -y --name img_db
conda activate img_db
```

To list installed packages:
```bash
conda list
```

To deactivate/delete:
```bash
conda deactivate
conda remove -n img_db --all -y
```

#### Virtual Environment
Using Pip and Python's venv module:
```bash
python3 -m venv env/.img_db
source env/.img_db/bin/activate
pip install -r env/requirements.txt
```

List packages:
```bash
pip list
```

Deactivate/delete:
```bash
deactivate
rm -rf env/.img_db
```

### Setup C++ Dependencies

```bash
sudo apt install libgtest-dev libopencv-dev libxext-dev libxt-dev libxrender-dev libpqxx-dev libgumbo-dev nlohmann-json3-dev libcxxopts-dev
```

---

## 🛠️ Running the Application

### Development Mode

**From project root (any of these methods):**

**Option 1: Quick Run Script (Recommended)**
```bash
./run.sh
```
This script will:
- Check for .env file (create from template if missing)
- Verify dependencies are installed
- Test database connection
- Start the development server

**Option 2: Using npm**
```bash
npm run dev
```

**Option 3: Using Make**
```bash
make dev
```

**Option 4: From frontend directory (traditional)**
```bash
cd frontend
npm run tauri dev
```

All methods will:
1. Start the React development server
2. Compile the Rust backend
3. Launch the application window
4. Enable hot-reload for frontend changes

### Production Build

**From project root:**
```bash
npm run build
# or
make build
```

**From frontend directory:**
```bash
cd frontend
npm run tauri build
```

The compiled application will be in:
- **Linux:** `frontend/src-tauri/target/release/bundle/`
- **macOS:** `frontend/src-tauri/target/release/bundle/macos/`
- **Windows:** `frontend/src-tauri/target/release/bundle/msi/`

### Legacy PySide6 GUI

```bash
source .venv/bin/activate
python main.py
# or: make python-dev
```

---

## 📝 CLI Commands Reference

All commands can be run from the **project root directory**.

### Quick Commands

| Command | Description |
|---------|-------------|
| `./run.sh` | **Quickest way to start** - Checks setup and runs dev server |
| `npm run dev` | Run Tauri in development mode |
| `npm run build` | Build production application |
| `make dev` | Same as `npm run dev` |
| `make help` | Show all available Make commands |

### Setup & Installation

**Complete Setup:**
```bash
npm run setup
```
- Installs all dependencies (root + frontend workspace)
- Installs TypeScript types
- One command to get everything ready

**Individual Steps:**
```bash
npm run install:all        # Install all dependencies
npm install                 # Install root dependencies only
npm install --workspace=frontend   # Install frontend dependencies only
```

**Using Make:**
```bash
make setup      # Complete setup
make install    # Install dependencies only
```

### Development Commands

**Start Development Server:**
```bash
# Any of these work:
./run.sh        # Recommended - checks everything first
npm run dev
make dev

# Traditional way (from frontend dir):
cd frontend && npm run tauri dev
```

**Build for Production:**
```bash
npm run build
# or
make build

# Output will be in:
# Linux:   frontend/src-tauri/target/release/bundle/
# macOS:   frontend/src-tauri/target/release/bundle/macos/
# Windows: frontend/src-tauri/target/release/bundle/msi/
```

**Type Checking:**
```bash
npm run tauri:check
# or
make check
```

### Testing

**Run All Tests:**
```bash
npm test
# or
make test
```

**Frontend Tests Only:**
```bash
npm run test-frontend
```

**Rust Tests Only:**
```bash
cd frontend/src-tauri && cargo test
```

**Python Tests:**
```bash
pytest
```

### Database Commands

**Setup Database (PostgreSQL + pgvector):**
```bash
make db-setup
```
This creates:
- Database: `image_toolkit`
- User: `toolkit_user`
- Password: `change_me_123` (change this!)
- Enables pgvector extension

**Check Database Connection:**
```bash
make db-check
```

**Run Migrations:**
```bash
make db-migrate
```

**Manual Database Connection:**
```bash
psql postgresql://toolkit_user:password@localhost:5432/image_toolkit
```

### Maintenance

**Clean Build Artifacts:**
```bash
make clean
```
Removes:
- `frontend/dist`
- `frontend/build`
- `frontend/src-tauri/target`
- `node_modules`

**Format Code:**
```bash
make format
```
Formats both Rust and TypeScript code.

### npm Scripts Reference

All scripts from `package.json`:

| Script | Command | Description |
|--------|---------|-------------|
| `setup` | `npm run setup` | Complete setup with deps + types |
| `dev` | `npm run dev` | Start development server |
| `build` | `npm run build` | Build production app |
| `test` | `npm run test` | Run all tests |
| `install:all` | `npm run install:all` | Install all dependencies |
| `tauri:dev` | `npm run tauri:dev` | Run Tauri dev server |
| `tauri:build` | `npm run tauri:build` | Build Tauri app |
| `tauri:check` | `npm run tauri:check` | Type check Rust code |
| `test-frontend` | `npm run test-frontend` | Run frontend tests |

### Make Commands Reference

Run `make help` for a full list. Common commands:

| Command | Description |
|---------|-------------|
| `make setup` | Complete setup |
| `make dev` | Start dev server |
| `make build` | Build production |
| `make test` | Run all tests |
| `make db-setup` | Setup PostgreSQL |
| `make db-check` | Test DB connection |
| `make clean` | Clean build artifacts |
| `make format` | Format code |
| `make python-dev` | Run Python/PySide6 GUI |

---

## 💻 Usage

Before you start the program, you must initialize the PostgreSQL Database by running one of the following commands:
- On the Linux CLI: `sudo systemctl start postgresql`
- On the Windows CMD: `net start postgresql-x64-18`
- On the macOS Terminal: `brew services start postgresql`

Afterwards, you can stop the Database by running one of the following commands:
- On the Linux CLI: `sudo systemctl stop postgresql`
- On the Windows CMD: `net stop postgresql-x64-18`
- On the macOS Terminal: `brew services stop postgresql`

After installing PostgreSQL, you can use the `psql -U postgres -d img_db` command to connect to the database (and `exit` to leave it).

**Note:** You also need to install pgvector from the [official GitHub](https://github.com/pgvector/pgvector) in order to access full database functionality.

### Convert Image Format

You can either convert a single image at a time:
```bash
python main.py convert --output_format png --input_path <path_to_img> --output_path <path_new_img>
```

or batch convert all images in a directory that match one (or more) image formats:
```bash
python main.py convert --output_format png --input_path <path_to_dir> --input_formats webp avif --output_path <path_new_dir>
```

**Note:** If no `--output_path` argument is given, the new image will have the same name (or the images will be generated in the same directory, in the case of batch conversion), just with a different file extension.

### First Time Application Setup

#### Create Your Account

When you first launch the application:
1. You'll see the login dialog
2. Click "Create New Account"
3. Enter your desired account name
4. Set a master password (this encrypts your vault)
5. Click "Create Account"

**Important:** The master password cannot be recovered if lost!

#### Verify Database Connection

After logging in, check the header bar:
- ✅ **Green "DB Connected"** - Everything is working
- ❌ **Red "DB Offline"** - Check your PostgreSQL setup and `.env` configuration

#### Configure Settings

Click the ⚙️ Settings button to:
- Choose your theme (Light/Dark/System)
- Create system preference profiles
- Change your master password

### Application Features

- **Add Images:** Use the "Scan" tab to import images into the database
- **Search Images:** Use the "Search" tab with filters (tags, groups, formats)
- **Convert Images:** Use the "Convert" tab for batch format conversion
- **Set Wallpaper:** Use the "Wallpaper" tab for desktop wallpaper management

---

## 🔨 Build

### Tauri Application

Production build:
```bash
npm run build
# or from frontend:
cd frontend && npm run tauri build
```

Platform-specific builds:

**Linux AppImage:**
```bash
npm run build
# Output: frontend/src-tauri/target/release/bundle/appimage/
```

**macOS DMG:**
```bash
npm run build
# Output: frontend/src-tauri/target/release/bundle/macos/
```

**Windows MSI:**
```bash
npm run build
# Output: frontend/src-tauri/target/release/bundle/msi/
```

### Python Application

To build the desktop app part of the project:
```bash
pyinstaller --clean app.spec
```

### Core and Web (C++)

To build the core and web parts of the project:
```bash
mkdir build
cd build
cmake ..
cmake --build . --clean-first
make
```

### Mobile

**Android:**
```bash
cd app
./gradlew assembleDebug
```

**iOS:**
```bash
cd app
xcodebuild -project ImageToolkit.xcodeproj -scheme ImageToolkit build
```

---

## 🧪 Testing

### Frontend Tests
```bash
cd frontend
npm test
```

### Backend Tests
```bash
cd frontend/src-tauri
cargo test
```

### Python Tests
```bash
pytest
```

### Java Tests
To test the Java portion of the project:
```bash
mvn test
```

### Integration Tests
```bash
# Start app in test mode
DATABASE_URL=postgresql://localhost/test_db cargo run
```

---

## 🐛 Troubleshooting

### Common Issues

#### "DB Offline" in header

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection manually
psql postgresql://toolkit_user:change_me_123@localhost:5432/image_toolkit
```

#### Database Connection Failed

**Error:** `Failed to connect to PostgreSQL database`

**Solutions:**
1. Verify PostgreSQL is running:
   ```bash
   sudo systemctl status postgresql  # Linux
   brew services list  # macOS
   ```

2. Check your `.env` file has correct credentials

3. Test connection manually:
   ```bash
   psql postgresql://toolkit_user:password@localhost:5432/image_toolkit
   ```

4. Ensure pgvector extension is installed:
   ```sql
   \c image_toolkit
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

#### Build fails with OpenSSL errors

```bash
# Linux
sudo apt install libssl-dev pkg-config

# macOS
brew install openssl@3
```

#### TypeScript Build Errors

**Error:** `Cannot find module 'react-dom/client'`

**Solution:**
```bash
cd frontend
npm install --save-dev @types/react-dom
```

#### Rust Compilation Errors

**Error:** `failed to run custom build command for 'openssl-sys'`

**Solution (Linux):**
```bash
sudo apt install libssl-dev pkg-config
```

**Solution (macOS):**
```bash
brew install openssl@3
```

#### Python Backend Issues

**Error:** `ModuleNotFoundError: No module named 'base'`

**Solution:**
```bash
# Build the Rust-Python bindings
cd base
maturin develop --release
```

#### Tauri Build Fails

**Error:** `webkit2gtk-4.1 not found`

**Solution (Linux):**
```bash
sudo apt install libwebkit2gtk-4.1-dev
```

### Verify Dependencies

```bash
# Check if dependencies are installed
ls node_modules/@types/react-dom   # Should exist
ls frontend/node_modules           # Should exist

# Verify Rust toolchain
rustc --version
cargo --version

# Check Tauri dependencies (Linux)
dpkg -l | grep -E "webkit2gtk|libssl-dev|build-essential"
```

---

## ⚙️ Advanced Configuration

### Custom Database Host

If using a remote PostgreSQL server:

```env
DATABASE_URL=postgresql://user:pass@192.168.1.100:5432/image_toolkit
```

### Performance Tuning

For large image collections (100k+ images):

1. Increase PostgreSQL connection pool:
   ```rust
   // In frontend/src-tauri/src/db.rs
   PgPoolOptions::new()
       .max_connections(20)  // Increase from default 5
   ```

2. Adjust PostgreSQL settings (`/etc/postgresql/14/main/postgresql.conf`):
   ```
   shared_buffers = 256MB
   effective_cache_size = 1GB
   maintenance_work_mem = 128MB
   ```

### Enable Debug Logging

```env
RUST_LOG=debug
RUST_BACKTRACE=full
```

Then check logs:
```bash
# Development mode - logs to terminal
npm run tauri dev

# Production - logs to:
# Linux: ~/.config/image-toolkit/logs/
# macOS: ~/Library/Logs/image-toolkit/
# Windows: %APPDATA%\image-toolkit\logs\
```

### Environment Variables

**Required Variables:**

Create `frontend/src-tauri/.env` from template:
```bash
cp frontend/src-tauri/.env.example frontend/src-tauri/.env
```

Edit and set:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/image_toolkit
```

**Optional Variables:**
```env
RUST_LOG=info          # Log level (debug, info, warn, error)
RUST_BACKTRACE=1       # Enable stack traces
```

---

## 🔄 Development Workflow

### Hot Reload

The development server supports hot reload:
- **Frontend (React):** Changes auto-reload in browser
- **Backend (Rust):** Requires manual restart (`Ctrl+C` then re-run)

### Database Migrations

To create a new migration:

```bash
cd frontend/src-tauri
sqlx migrate add <migration_name>
```

Edit the generated SQL file in `migrations/`, then run:
```bash
sqlx migrate run
```

### Adding New Tauri Commands

1. Create command in appropriate module (e.g., `src/database_commands.rs`)
2. Add to `invoke_handler!` in `src/lib.rs`
3. Call from frontend using `invoke('command_name', { params })`

### Typical Development Session

1. **Start fresh:**
   ```bash
   ./run.sh
   ```

2. **Make changes:**
   - Frontend changes auto-reload
   - Rust changes require restart (Ctrl+C, then `./run.sh` again)

3. **Run tests:**
   ```bash
   npm test
   ```

4. **Build for production:**
   ```bash
   npm run build
   ```

### Quick Iteration

```bash
# Terminal 1: Keep dev server running
npm run dev

# Terminal 2: Run tests on changes
npm test -- --watch
```

---

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Architecture and development guidelines for AI coding assistants
- **[AGENTS.md](AGENTS.md)** - Instructions for coding assistant LLMs
- **[GEMINI.md](GEMINI.md)** - Project instructions for Gemini

---

## 🔒 Security Notes

1. **VaultManager:** Credentials are encrypted with AES-256-GCM
2. **Master Password:** Never stored anywhere - only used for encryption
3. **Database:** Store sensitive data in environment variables, not in code
4. **IPC Security:** Tauri validates all frontend-backend communication
5. **NEVER** hardcode credentials - use `.env` files and `VaultManager`

---

## 📖 Project Implementation Notes

### Root Command System

The project supports multiple ways to run the application from the project root:

**Method 1: Quick Run Script (Best for beginners)**
```bash
./run.sh
```

**Method 2: Using npm (Best for CI/CD)**
```bash
npm run setup    # One-time
npm run dev      # Every time
```

**Method 3: Using Make (Best for developers)**
```bash
make setup       # One-time
make dev         # Every time
```

**Method 4: Traditional (Still works)**
```bash
cd frontend
npm run tauri dev
```

### Workspace Configuration

The root `package.json` uses npm workspaces to manage the frontend:
```json
{
  "workspaces": ["frontend"]
}
```

This allows commands like:
```bash
npm run tauri dev --workspace=frontend
```

### Smart Run Script

The `run.sh` script includes:
- Environment file checking
- Dependency verification
- Database connection testing
- Color-coded output
- Interactive prompts

### Benefits

**For New Users:**
- ✅ One command to get started: `./run.sh`
- ✅ Automatic setup checks and helpful error messages
- ✅ No need to remember complex paths
- ✅ Works from anywhere in the project

**For Developers:**
- ✅ Faster workflow (no cd-ing around)
- ✅ Make commands for common tasks
- ✅ Consistent command structure
- ✅ Easy integration with scripts/CI

---

## 🎯 Common Tasks Quick Reference

### Just want to try it out?
```bash
./run.sh
```

### Need to setup from scratch?
```bash
make setup
make db-setup
npm run dev
```

### Building for distribution?
```bash
npm run build
```

### Database not working?
```bash
make db-check
# If fails: make db-setup
```

### Clean slate?
```bash
make clean
npm run setup
```

---

**Last Updated:** 2026-01-13

**For help:** Run `make help` or `npm run` to see all available commands.
