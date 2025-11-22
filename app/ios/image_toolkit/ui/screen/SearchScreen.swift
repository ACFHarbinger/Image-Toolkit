import SwiftUI

struct SearchScreen: View {
    @State private var searchDir: String = ""
    @State private var charName: String = ""
    @State private var seriesName: String = ""
    @State private var selectedTags: Set<String> = []
    @State private var showingAlert = false
    @State private var alertMessage = ""
    @State private var showDirChooser = false
    
    let allTags = [
        "portrait", "full_body", "action", "close_up", "landscape", "night", "day",
        "indoor", "outdoor", "solo", "multiple", "fanart", "official", "color", "monochrome"
    ]
    
    let columns = [GridItem(.adaptive(minimum: 100), spacing: 8)]
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Search Images")
                    .font(AppTheme.Typography.headlineSmall)
                
                HStack(alignment: .bottom) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Search Directory")
                            .font(.caption)
                            .foregroundColor(.gray)
                        TextField("", text: $searchDir)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                    }
                    
                    Button(action: { showDirChooser = true }) {
                        Image(systemName: "folder")
                            .padding()
                            .background(Color.gray.opacity(0.1))
                            .cornerRadius(8)
                    }
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Character Name")
                        .font(.caption)
                        .foregroundColor(.gray)
                    TextField("", text: $charName)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Series Name")
                        .font(.caption)
                        .foregroundColor(.gray)
                    TextField("", text: $seriesName)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                
                SectionCard(title: "Tags (Optional)") {
                    VStack(spacing: 16) {
                        FlowLayout(items: allTags, spacing: 8) { tag in
                            let isSelected = selectedTags.contains(tag)
                            Button(action: {
                                if isSelected { selectedTags.remove(tag) } else { selectedTags.insert(tag) }
                            }) {
                                HStack(spacing: 4) {
                                    if isSelected {
                                        Image(systemName: "checkmark")
                                            .font(.caption)
                                    }
                                    Text(tag)
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
                            Button(action: { selectedTags = Set(allTags) }) {
                                Text("Select All")
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(AppTheme.primary)
                                    .foregroundColor(.white)
                                    .cornerRadius(8)
                            }
                            
                            Button(action: { selectedTags = [] }) {
                                Text("Clear All")
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(Color.red)
                                    .foregroundColor(.white)
                                    .cornerRadius(8)
                            }
                        }
                    }
                }
                
                Button(action: {
                    alertMessage = "Running Search:\nDir: \(searchDir)\nChar: \(charName)"
                    showingAlert = true
                }) {
                    HStack {
                        Image(systemName: "magnifyingglass")
                        Text("Search")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(AppTheme.primary)
                    .foregroundColor(.white)
                    .cornerRadius(8)
                }
                
                Text("Results (Simulated)")
                    .font(AppTheme.Typography.titleMedium)
                
                LazyVGrid(columns: columns, spacing: 8) {
                    ForEach(0..<12, id: \.self) { index in
                        ZStack {
                            Rectangle()
                                .fill(AppTheme.secondary.opacity(0.3))
                                .aspectRatio(1, contentMode: .fit)
                                .cornerRadius(8)
                            Text("Img \(index + 1)")
                                .foregroundColor(AppTheme.onSecondary)
                        }
                    }
                }
                .frame(height: 300)
            }
            .padding(16)
        }
        .alert("Search Action", isPresented: $showingAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
        .alert("Directory Chooser Opened", isPresented: $showDirChooser) {
            Button("OK", role: .cancel) { }
        }
    }
}