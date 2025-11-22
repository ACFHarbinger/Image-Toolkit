import SwiftUI

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