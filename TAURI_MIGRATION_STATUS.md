# Tauri Migration Status - PySide6 to Tauri Framework

## Overview
This document tracks the migration of PySide6 GUI features to the Tauri/React framework, maintaining full functional parity with the original Python application while leveraging the performance and cross-platform benefits of Tauri.

## Architecture

### Technology Stack
- **Frontend**: React 19 + TypeScript
- **Backend Bridge**: Tauri (Rust)
- **Core Logic**: Rust (via PyO3/Maturin in `base/` module)
- **Python Orchestrator**: Used as sidecar for ML/DB operations
- **State Management**: React Context API (custom implementation)

### Design Principles
1. **Rust-First**: Heavy computation in Rust (`base` crate)
2. **Python Bridge**: Use Python for ML (PyTorch), DB (pgvector), and legacy code
3. **Async Communication**: Tauri events for progress tracking
4. **Security**: VaultManager integration for credentials

---

## Implementation Status

### ✅ Completed Features

#### 1. Global State Management
**Location**: `frontend/src/store/`
- ✅ `appStore.ts` - Type definitions and context
- ✅ `AppStoreProvider.tsx` - React Context provider with:
  - Authentication state management
  - Background task tracking
  - User preferences (theme, configs)
  - UI state (modals, dialogs)
  - Tauri event listeners for async tasks

**Features**:
- Persistent auth via localStorage
- Theme management (light/dark/system)
- Background task progress tracking
- Event-driven updates from Rust backend

#### 2. Authentication & Security
**Frontend**: `frontend/src/components/LoginDialog.tsx`
**Backend**: `frontend/src-tauri/src/auth_commands.rs`

**Implemented**:
- ✅ Login UI with account name + password
- ✅ Create account workflow
- ✅ Theme toggle in login screen
- ✅ Password visibility toggle
- ✅ Error handling and loading states

**Tauri Commands**:
- ✅ `authenticate_user` - Verifies credentials via Python VaultManager
- ✅ `create_user_account` - Creates new encrypted account
- ✅ `load_user_settings` - Loads user preferences from vault
- ✅ `save_user_settings` - Persists settings to vault
- ✅ `update_master_password` - Changes master password

**Python Bridge**: All auth commands call Python VaultManager for:
- AES-256-GCM encryption
- Password hashing (SHA-256 + salt + pepper)
- KeyStore management (via Kotlin cryptography module)

#### 3. Settings Management
**Location**: `frontend/src/components/SettingsDialog.tsx`

**Sections**:
1. **General Settings**:
   - ✅ Theme selection (dark/light/system)
   - ✅ Master password reset
   - ✅ Confirmation dialog

2. **Tab Configurations**:
   - ⏳ Load/save named configs per tab
   - ⏳ JSON editor for config values
   - ⏳ Apply configs to active tabs

3. **System Profiles**:
   - ✅ Create new preference profiles
   - ✅ Load existing profiles
   - ✅ Delete profiles
   - ⏳ Profile selection on login

**Storage**: All settings persisted in encrypted `.vault` files via VaultManager

#### 4. Core File Operations (Existing)
**Backend**: `frontend/src-tauri/src/core_commands.rs`

- ✅ `scan_files` - Recursive directory scanning
- ✅ `convert_image_batch` - Batch image conversion
- ✅ `delete_files` - File deletion
- ✅ `delete_directory` - Directory deletion
- ✅ `merge_images` - Image merging (horizontal/vertical/grid)

**Integration**: Uses Rust `base` crate for high-performance IO

#### 5. Wallpaper Management (Existing)
**Backend**: `frontend/src-tauri/src/wallpaper_commands.rs`

- ✅ `set_wallpaper` - Multi-monitor wallpaper setting
- ✅ `get_monitors` - Monitor enumeration
- ✅ `update_slideshow_config` - Slideshow configuration
- ✅ `toggle_slideshow_daemon` - Start/stop slideshow daemon

**Platform Support**:
- KDE Plasma (via `qdbus`)
- GNOME (via `gsettings`)

#### 6. Video Processing Commands
**Backend**: `frontend/src-tauri/src/video_commands.rs`

**Implemented**:
- ✅ `extract_video_clip` - Extract video segments with:
  - FFmpeg backend (fast, recommended)
  - MoviePy backend (fallback)
  - Audio muting
  - Speed adjustment
  - Resolution scaling
  - Progress events

- ✅ `extract_video_frames` - Extract frames at intervals
- ✅ `get_video_metadata` - FFprobe metadata extraction

**Features**:
- Async task execution
- Real-time progress tracking via Tauri events
- Error handling and recovery

---

### 🚧 In Progress

#### 7. Video Extractor Tab UI
**Location**: `frontend/src/tabs/core/ImageExtractorTab.tsx`

**Current State**: Uses browser `<video>` API (frontend-only)
**Needed**: Integration with new `video_commands` Tauri backend

**TODO**:
- Replace frontend video capture with `extract_video_clip` command
- Add FFmpeg/MoviePy toggle
- Integrate with task progress system
- Add batch extraction support

#### 8. Database Integration
**Backend**: ⏳ `frontend/src-tauri/src/database_commands.rs` (to be created)

**Needed Commands**:
- `connect_database` - PostgreSQL connection
- `search_images` - Vector similarity search (pgvector)
- `add_images_to_db` - Insert images with metadata
- `scan_directory_metadata` - Extract and store image metadata
- `get_image_groups` - Retrieve image groupings

**Python Bridge**: PostgreSQL operations via existing `backend/src/core/image_database.py`

---

### 📋 Pending Features

#### 9. Log Viewer Component
**Status**: Not started
**Priority**: Medium

**Requirements**:
- Real-time log streaming from backend
- Tauri event listener for log messages
- Filterable log levels (INFO, WARN, ERROR)
- Scrollable log view with timestamps
- Export logs functionality

**Implementation**:
- Create `LogViewerDialog.tsx` component
- Add `stream_logs` Tauri command
- Emit log events from Rust backend

#### 10. Image Preview & Slideshow
**Status**: Not started
**Priority**: Medium

**Requirements**:
- Full-screen image preview
- Keyboard navigation
- Zoom/pan controls
- Slideshow mode with timer
- Multi-monitor support

**Implementation**:
- `ImagePreviewDialog.tsx` - Single image viewer
- `SlideshowWindow.tsx` - Full-screen slideshow
- Use Tauri's `WebviewWindow` API for multi-window support

#### 11. Advanced Drag-and-Drop
**Status**: Not started
**Priority**: Low

**Requirements**:
- Monitor layout visualization (WallpaperTab)
- Drag-and-drop image assignment
- Topological sorting for multi-monitor setups

**Implementation**:
- Use `@dnd-kit/core` library
- Visual monitor representation
- Save layout config to vault

#### 12. Web Integration Commands
**Backend**: ⏳ To be created

**Needed**:
- **Crawlers**: Danbooru, Gelbooru, Sankaku, generic Selenium
- **Drive Sync**: Dropbox, Google Drive, OneDrive
- **Reverse Search**: SauceNAO, IQDB, Google Images
- **Web Requests**: Generic HTTP client with retry logic

**Implementation Strategy**:
- Rust wrappers for `base::web` module
- Python sidecar for Selenium-based crawlers
- OAuth integration for cloud sync

#### 13. ML/Training Commands
**Backend**: ⏳ To be created

**Needed**:
- `train_model` - Train PyTorch models (R3GAN, SD3)
- `generate_images` - Image generation
- `run_inference` - MetaCLIP inference
- `evaluate_model` - R3GAN evaluation

**Implementation**:
- Python sidecar for PyTorch operations
- Progress streaming via Tauri events
- GPU acceleration support
- Model checkpoint management

---

## Migration Checklist

### Phase 1: Foundation ✅
- [x] Set up Tauri project structure
- [x] Implement global state management
- [x] Create authentication system
- [x] Build settings dialog
- [x] Add video processing commands

### Phase 2: Core Features 🚧
- [x] Video extraction backend
- [ ] Update Video Extractor Tab UI
- [ ] Database commands
- [ ] Search Tab integration
- [ ] Database Tab integration

### Phase 3: Advanced Features 📋
- [ ] Log viewer
- [ ] Image preview/slideshow
- [ ] Drag-and-drop monitor layout
- [ ] Web crawlers
- [ ] Drive sync
- [ ] ML training commands

### Phase 4: Polish & Testing 📋
- [ ] Error boundary components
- [ ] Loading states
- [ ] Tooltips and help text
- [ ] Keyboard shortcuts
- [ ] Cross-platform testing (Linux, Windows)
- [ ] Build and bundle verification

---

## Integration Guide

### Adding a New Tauri Command

1. **Create Rust Command** (`src-tauri/src/`):
```rust
#[tauri::command]
pub async fn my_command(param: String) -> Result<String, String> {
    // Implementation
    Ok("success".to_string())
}
```

2. **Register in `lib.rs`**:
```rust
.invoke_handler(tauri::generate_handler![
    my_command,
    // ... other commands
])
```

3. **Call from Frontend**:
```typescript
import { invoke } from '@tauri-apps/api/core';

const result = await invoke<string>('my_command', { param: 'value' });
```

### Adding Progress Tracking

1. **Emit Events from Rust**:
```rust
let _ = app.emit("task-progress", TaskProgress {
    task_id: id.clone(),
    progress: 50,
    message: "Half done".to_string(),
    status: "running".to_string(),
});
```

2. **Listen in React**:
```typescript
const { updateTask } = useAppStore();

useEffect(() => {
    const unlisten = listen<any>('task-progress', (event) => {
        updateTask(event.payload.taskId, {
            progress: event.payload.progress,
            message: event.payload.message,
        });
    });
    return () => { unlisten.then(fn => fn()); };
}, []);
```

### Python Bridge Pattern

For operations requiring Python (ML, DB):

```rust
let output = Command::new("python")
    .arg("-c")
    .arg(format!(r#"
import sys
sys.path.insert(0, '../../backend/src')
from module import function

result = function({})
print(result)
"#, params))
    .output()
    .map_err(|e| format!("Python error: {}", e))?;
```

---

## Testing Strategy

### Unit Tests
- Rust: `cargo test` in `frontend/src-tauri/`
- React: `npm run test` in `frontend/`

### Integration Tests
- End-to-end Tauri command testing
- Mock Python backend responses
- UI component interaction tests

### Manual Testing
- Login/logout workflows
- Settings persistence
- Video extraction (FFmpeg + MoviePy)
- Multi-monitor wallpaper setting
- Database search and scan

---

## Known Issues & Limitations

1. **Python Dependency**: Requires Python environment for ML/DB operations
   - **Solution**: Bundle Python as sidecar in production builds

2. **JVM Startup**: VaultManager requires JVM for Kotlin crypto
   - **Impact**: ~500ms startup delay
   - **Mitigation**: Lazy load vault operations

3. **Platform-Specific Features**:
   - Wallpaper setting requires `qdbus` (KDE) or `gsettings` (GNOME)
   - Windows wallpaper support pending

4. **Video Extraction**:
   - FFmpeg must be installed separately
   - MoviePy fallback has slower performance

---

## Performance Optimizations

1. **Rust Core**: All heavy IO in `base` crate
2. **Lazy Loading**: Load Python modules on-demand
3. **Streaming**: Use Tauri events for large operations
4. **Caching**: Cache database queries and image metadata
5. **Parallel Processing**: Use Tokio for async Rust operations

---

## Security Considerations

1. **Credentials**: All secrets encrypted via VaultManager (AES-256-GCM)
2. **IPC**: Tauri commands use secure IPC (no `nodeIntegration`)
3. **Input Validation**: Sanitize all user inputs
4. **File Permissions**: Check file access before operations
5. **HTTPS**: Use HTTPS for all API requests

---

## Future Enhancements

1. **WebAssembly**: Compile Rust image processing to WASM for browser
2. **Remote Backend**: Separate backend server for multi-user support
3. **Cloud Storage**: Direct cloud integration (S3, GCS)
4. **Mobile Support**: React Native bridge for Android/iOS
5. **Plugin System**: Extensible architecture for custom processors

---

## Documentation

- **User Guide**: TODO
- **API Reference**: TODO
- **Developer Guide**: This document
- **Deployment Guide**: TODO

---

## Contact & Support

For questions or contributions:
- GitHub Issues: [Image-Toolkit Issues](https://github.com/ACFHarbinger/Image-Toolkit/issues)
- Project Maintainer: ACFHarbinger

---

**Last Updated**: January 12, 2026
**Migration Progress**: ~40% Complete
