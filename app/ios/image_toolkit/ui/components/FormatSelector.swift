import SwiftUI

struct FormatSelector: View {
    let title: String
    let formats: [String]
    @Binding var selectedFormats: Set<String>
    
    var body: some View {
        SectionCard(title: title) {
            VStack(spacing: 16) {
                // Custom FlowLayout to mimic Compose FlowRow
                FlowLayout(items: formats, spacing: 8) { format in
                    let isSelected = selectedFormats.contains(format)
                    
                    Button(action: {
                        toggleFormat(format)
                    }) {
                        HStack(spacing: 4) {
                            if isSelected {
                                Image(systemName: "checkmark")
                                    .font(.caption)
                            }
                            Text(format.uppercased())
                                .font(.caption)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(isSelected ? AppTheme.secondary.opacity(0.2) : Color.gray.opacity(0.1))
                        .foregroundColor(AppTheme.onSurface)
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(isSelected ? AppTheme.secondary : Color.clear, lineWidth: 1)
                        )
                    }
                }
                
                HStack(spacing: 16) {
                    Button(action: {
                        formats.forEach { selectedFormats.insert($0) }
                    }) {
                        Text("Add All")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(AppTheme.primary)
                            .foregroundColor(.white)
                            .cornerRadius(8)
                    }
                    
                    Button(action: {
                        formats.forEach { selectedFormats.remove($0) }
                    }) {
                        Text("Remove All")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.red)
                            .foregroundColor(.white)
                            .cornerRadius(8)
                    }
                }
            }
        }
    }
    
    private func toggleFormat(_ format: String) {
        if selectedFormats.contains(format) {
            selectedFormats.remove(format)
        } else {
            selectedFormats.insert(format)
        }
    }
}