import SwiftUI

@main
struct ImageToolkitApp: App {
    var body: some Scene {
        WindowGroup {
            MainAppScreen()
                .preferredColorScheme(.light) // Defaulting to light, system handles auto
        }
    }
}