# ``ImageToolkit``

Image Database & Edit Toolkit — iOS companion app.

## Overview

Image Toolkit iOS is the mobile companion to the cross-platform image management
suite. It provides the same core operations (convert, merge, delete, search, scan,
database) as the PySide6 desktop app, implemented natively in SwiftUI with an
`async`/`await` network layer that calls the Python backend via the REST API.

### Architecture

The iOS app follows MVVM with SwiftUI:

```
App.swift (entry point)
└── MainAppScreen          ← TabView shell, owns navigation state
    ├── ConvertScreen      ← Format conversion (calls /convert endpoint)
    ├── MergeScreen        ← Image merging / stitch  
    ├── DeleteScreen       ← Bulk delete by format
    ├── SearchScreen       ← Semantic vector search (pgvector)
    ├── DatabaseScreen     ← Database browse / manage
    └── ScanScreen         ← Directory scan & ingest
```

Shared UI primitives live in `ui/components/`:
- ``FileInput`` — path field with file/directory chooser buttons
- ``SectionCard`` — collapsible card with animated expand/collapse
- ``FormatSelector`` — chip grid for selecting image formats

Layout helpers live in `layout/`:
- ``FlowLayout`` — wrapping row layout (mirrors Jetpack Compose `FlowRow`)

Design tokens are centralised in ``AppTheme`` (`theme/Theme.swift`).
Navigation destinations are defined by ``Screen`` (`navigation/Screen.swift`).

### Running

```bash
# Open in Xcode and run on Simulator or device:
xed app/ios

# Or build from the command line (requires macOS + Xcode):
xcodebuild -scheme ImageToolkit -destination 'platform=iOS Simulator,name=iPhone 15' build
```

### Generating Documentation

```bash
# Generate DocC archive (requires Xcode 15+):
xcodebuild docbuild \
  -scheme ImageToolkit \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  -derivedDataPath /tmp/docc-build

# Or via Swift Package Manager (swift-docc-plugin required):
swift package generate-documentation --target ImageToolkit
```

## Topics

### Navigation

- ``Screen``
- ``MainAppScreen``

### Screens

- ``ConvertScreen``

### UI Components

- ``FileInput``
- ``SectionCard``
- ``FormatSelector``

### Layout

- ``FlowLayout``

### Theme

- ``AppTheme``
