import SwiftUI

enum Screen: String, CaseIterable, Identifiable {
    case convert
    case merge
    case delete
    case search
    case database
    case scan
    
    var id: String { self.rawValue }
    
    var label: String {
        switch self {
        case .convert: return "Convert"
        case .merge: return "Merge"
        case .delete: return "Delete"
        case .search: return "Search"
        case .database: return "Database"
        case .scan: return "Scan"
        }
    }
    
    // Mapping Material Icons to SF Symbols
    var iconName: String {
        switch self {
        case .convert: return "arrow.triangle.2.circlepath" // Icons.Default.Transform
        case .merge: return "arrow.triangle.merge" // Icons.Default.CallMerge
        case .delete: return "trash" // Icons.Default.DeleteForever
        case .search: return "magnifyingglass" // Icons.Default.Search
        case .database: return "server.rack" // Icons.Default.Storage
        case .scan: return "viewfinder" // Icons.Default.FilterCenterFocus
        }
    }
}