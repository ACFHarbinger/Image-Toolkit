import SwiftUI

/// The root view of the Image Toolkit iOS app.
///
/// Renders a `TabView` containing one tab per ``Screen`` case. The navigation
/// bar displays the app name with the brand primary colour as its background.
///
/// Navigation is driven by `selectedTab: Screen` — deep links or push
/// notifications that want to surface a specific tab should update this binding.
///
/// ```swift
/// @main
/// struct ImageToolkitApp: App {
///     var body: some Scene {
///         WindowGroup { MainAppScreen() }
///     }
/// }
/// ```
struct MainAppScreen: View {
    @State private var selectedTab: Screen = .database
    
    var body: some View {
        NavigationView {
            TabView(selection: $selectedTab) {
                ForEach(Screen.allCases) { screen in
                    getScreenView(for: screen)
                        .tabItem {
                            Label(screen.label, systemImage: screen.iconName)
                        }
                        .tag(screen)
                }
            }
            .navigationTitle("Image Database & Edit Toolkit")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(AppTheme.primary, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }
    
    @ViewBuilder
    func getScreenView(for screen: Screen) -> some View {
        switch screen {
        case .convert:
            Text("Convert Screen Placeholder") // Replace with actual ConvertScreen View
        case .merge:
            Text("Merge Screen Placeholder")
        case .delete:
            Text("Delete Screen Placeholder")
        case .search:
            Text("Search Screen Placeholder")
        case .database:
            Text("Database Screen Placeholder")
        case .scan:
            Text("Scan Screen Placeholder")
        }
    }
}