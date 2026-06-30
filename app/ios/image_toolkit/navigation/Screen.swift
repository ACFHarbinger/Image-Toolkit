import SwiftUI

/// The top-level navigation destinations for the Image Toolkit app.
///
/// Each case maps to a tab in ``MainAppScreen`` and carries the display
/// label and SF Symbol icon name used in the `TabView`.
///
/// ```swift
/// TabView(selection: $selectedTab) {
///     ForEach(Screen.allCases) { screen in
///         ScreenContent(screen: screen)
///             .tabItem { Label(screen.label, systemImage: screen.iconName) }
///             .tag(screen)
///     }
/// }
/// ```
enum Screen: String, CaseIterable, Identifiable {
    /// Image format conversion (single file or batch directory).
    case convert
    /// Merge multiple images into a composite or stitch output.
    case merge
    /// Bulk-delete images by format or criteria.
    case delete
    /// Semantic vector search over the indexed image library.
    case search
    /// Browse and manage the pgvector database of indexed images.
    case database
    /// Scan a directory and ingest new images into the database.
    case scan

    /// A stable identifier equal to the raw string value.
    var id: String { self.rawValue }

    /// Human-readable tab label shown beneath the icon.
    var label: String {
        switch self {
        case .convert:  return "Convert"
        case .merge:    return "Merge"
        case .delete:   return "Delete"
        case .search:   return "Search"
        case .database: return "Database"
        case .scan:     return "Scan"
        }
    }

    /// SF Symbol name for the tab bar icon (mirrors the Android Material Icon).
    var iconName: String {
        switch self {
        case .convert:  return "arrow.triangle.2.circlepath"
        case .merge:    return "arrow.triangle.merge"
        case .delete:   return "trash"
        case .search:   return "magnifyingglass"
        case .database: return "server.rack"
        case .scan:     return "viewfinder"
        }
    }
}