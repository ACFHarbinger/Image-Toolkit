import SwiftUI

struct SectionCard<Content: View>: View {
    let title: String
    @State private var expanded: Bool
    let content: Content

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