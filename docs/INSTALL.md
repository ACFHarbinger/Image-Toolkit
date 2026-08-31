# Image-Toolkit Installation & Prerequisites Guide

This document describes how to install the pre-built desktop application, set up external prerequisites (PostgreSQL with `pgvector`), and configure the environment.

---

## 1. Desktop Application Installation

### Linux
Image-Toolkit distributes two Linux packages for 64-bit systems:

- **AppImage** (Universal):
  ```bash
  chmod +x ImageToolkit-*-x86_64.AppImage
  ./ImageToolkit-*-x86_64.AppImage
  ```

- **Debian / Ubuntu Package** (`.deb`):
  ```bash
  sudo dpkg -i image-toolkit_*_amd64.deb
  # If missing dependencies:
  sudo apt-get install -f
  ```
  Launches from the desktop application menu or by running `image-toolkit`.

### Windows
- Download `ImageToolkit-*-windows-x86_64.zip`.
- Extract the archive to a folder of your choice.
- Run `ImageToolkitApp.exe`.
- *Note:* The Windows executable is unsigned; if Windows SmartScreen displays a warning, click **"More info"** and then **"Run anyway"**.

---

## 2. Database Architecture & External Prerequisites

Image-Toolkit uses a hybrid storage architecture:

1. **Unified Primary Store (`~/.image-toolkit/library.db`)**:
   - An encrypted SQLCipher SQLite database created and managed automatically on first launch.
   - Houses entities, media listings, tags, and local image registries.

2. **External PostgreSQL + `pgvector`**:
   - Required for vector similarity search, anime training pipelines, and legacy PostgreSQL migration.
   - **PostgreSQL Version:** 14, 15, or 16+
   - **Extension:** `pgvector` (>= 0.5.0)

---

## 3. Setting Up PostgreSQL + pgvector

### Step 1: Install PostgreSQL and pgvector

#### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib

# Install pre-packaged pgvector if available for your PostgreSQL version:
sudo apt-get install -y postgresql-14-pgvector  # or postgresql-15-pgvector, postgresql-16-pgvector

# Or build pgvector from source:
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

#### macOS (Homebrew)
```bash
brew install postgresql@14
brew install pgvector
brew services start postgresql@14
```

### Step 2: Initialize Database and Extension

#### Automated Setup (using `just`)
```bash
just db-setup
```

#### Manual Setup (using `psql`)
```sql
-- Connect to PostgreSQL as admin
sudo -u postgres psql

-- Create database and user
CREATE DATABASE image_toolkit;
CREATE USER toolkit_user WITH PASSWORD 'change_me_123';
GRANT ALL PRIVILEGES ON DATABASE image_toolkit TO toolkit_user;

-- Enable pgvector extension
\c image_toolkit
CREATE EXTENSION IF NOT EXISTS vector;
ALTER DATABASE image_toolkit OWNER TO toolkit_user;
\q
```

### Step 3: Configure Environment Variables

Create or update `.env` in the application root (or set system environment variables):

```env
DATABASE_URL=postgresql://toolkit_user:change_me_123@localhost:5432/image_toolkit
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=image_toolkit
POSTGRES_USER=toolkit_user
POSTGRES_PASSWORD=change_me_123
```

Verify connection:
```bash
just db-check
```

---

## 4. First-Run & Fallback Behavior

- On initial startup, Image-Toolkit prompts you to create a secure master vault password.
- If PostgreSQL is offline or unconfigured, the application runs normally using the unified SQLCipher local storage.
- Features requiring the vector database or legacy migration will report connection status and point to this installation guide if the database is unreachable.
