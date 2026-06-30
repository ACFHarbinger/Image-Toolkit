import SwiftUI

/// A generic wrapping layout that mirrors Jetpack Compose's `FlowRow`.
///
/// Items are laid out left-to-right and wrap onto new rows when the available
/// width is exhausted. The view's height adjusts automatically to fit all rows.
///
/// ```swift
/// FlowLayout(items: ["PNG", "WEBP", "AVIF"], spacing: 8) { format in
///     Text(format)
///         .padding(.horizontal, 12)
///         .background(Color.accentColor.opacity(0.15))
///         .cornerRadius(8)
/// }
/// ```
///
/// - Note: This is a layout workaround for iOS 15/16. On iOS 16+ you can use
///   the native `Layout` protocol; on iOS 17+ prefer `FlowLayout` from SwiftUI.
struct FlowLayout<Data: Collection, Content: View>: View where Data.Element: Hashable {
    /// The collection of items to lay out.
    let items: Data
    /// Horizontal and vertical spacing between items (applied as half-padding on each side).
    let spacing: CGFloat
    /// View builder called once per item.
    let content: (Data.Element) -> Content

    @State private var totalHeight: CGFloat = .zero

    /// Creates a `FlowLayout`.
    ///
    /// - Parameters:
    ///   - items: The data collection to display.
    ///   - spacing: Gap between items (default `8`).
    ///   - content: View builder receiving each element.
    init(items: Data, spacing: CGFloat = 8, @ViewBuilder content: @escaping (Data.Element) -> Content) {
        self.items = items
        self.spacing = spacing
        self.content = content
    }
    
    var body: some View {
        GeometryReader { geometry in
            self.generateContent(in: geometry)
        }
        .frame(height: totalHeight)
    }
    
    private func generateContent(in geometry: GeometryProxy) -> some View {
        var width = CGFloat.zero
        var height = CGFloat.zero
        
        return ZStack(alignment: .topLeading) {
            ForEach(Array(items), id: \.self) { item in
                self.content(item)
                    .padding([.horizontal, .vertical], spacing / 2)
                    .alignmentGuide(.leading) { d in
                        if (abs(width - d.width) > geometry.size.width) {
                            width = 0
                            height -= d.height
                        }
                        let result = width
                        if item == self.items.first! {
                            width = 0 // Reset for first item
                        } else {
                            width -= d.width
                        }
                        return result
                    }
                    .alignmentGuide(.top) { d in
                        let result = height
                        if item == self.items.last! {
                            width = 0 // Last item
                        }
                        return result
                    }
            }
        }
        .background(viewHeightReader($totalHeight))
    }
    
    private func viewHeightReader(_ binding: Binding<CGFloat>) -> some View {
        GeometryReader { geometry -> Color in
            DispatchQueue.main.async {
                binding.wrappedValue = geometry.frame(in: .local).size.height
            }
            return .clear
        }
    }
}