import SwiftUI

/// Entry point for the Image Toolkit iOS application.
///
/// Launches ``MainAppScreen`` as the root view and pins the colour scheme to
/// light mode. Override `preferredColorScheme` to support dark mode once the
/// ``AppTheme`` dark-mode token set is defined.
@main
struct ImageToolkitApp: App {
    var body: some Scene {
        WindowGroup {
            MainAppScreen()
                .preferredColorScheme(.light)
        }
    }
}