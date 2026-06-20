import SwiftUI

/// A collapsible card with a title header and animated expand/collapse toggle.
///
/// Tapping the header row animates the content region in or out. The card uses
/// ``AppTheme/surface`` as its background and a 2 pt drop shadow.
///
/// ```swift
/// SectionCard(title: "Advanced Options", startOpen: false) {
///     Toggle("Enable GPU", isOn: $useGpu)
///     Stepper("Threads: \(threads)", value: $threads, in: 1...8)
/// }
/// ```
struct SectionCard<Content: View>: View {
    /// Text shown in the header row.
    let title: String
    @State private var expanded: Bool
    let content: Content

    /// Creates a `SectionCard`.
    ///
    /// - Parameters:
    ///   - title: Header label.
    ///   - startOpen: Whether the card begins expanded (default `false`).
    ///   - content: View builder for the card body.
    init(title: String, startOpen: Bool = false, @ViewBuilder content: () -> Content) {
        self.title = title
        self._expanded = State(initialValue: startOpen)
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 0) {
            Button(action: {
                withAnimation {
                    expanded.toggle()
                }
            }) {
                HStack {
                    Text(title)
                        .font(AppTheme.Typography.titleMedium)
                        .foregroundColor(AppTheme.onSurface)
                    Spacer()
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(AppTheme.onSurface)
                }
                .padding(16)
            }
            
            if expanded {
                content
                    .padding([.leading, .trailing, .bottom], 16)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(AppTheme.surface)
        .cornerRadius(8)
        .shadow(color: Color.black.opacity(0.2), radius: 2, x: 0, y: 1)
        .padding(.vertical, 4)
    }
}