import SwiftUI

struct DatabaseScreen: View {
    @State private var host = "localhost"
    @State private var port = "5432"
    @State private var user = "postgres"
    @State private var password = ""
    @State private var dbName = "image_db"
    
    @State private var imagePath = ""
    @State private var seriesName = ""
    @State private var characters = ""
    @State private var selectedTags: Set<String> = []
    
    @State private var showingAlert = false
    @State private var alertMessage = ""
    
    let allTags = [
        "landscape", "night", "day", "indoor", "outdoor", "solo", "multiple", "fanart",
        "official", "cosplay", "portrait", "full_body", "action", "close_up", "nsfw"
    ]
    
    let seriesOptions = ["Naruto", "Bleach", "One Piece", "Dragon Ball"]
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Section 1: Postgres Connection
                SectionCard(title: "PostgreSQL Connection", startOpen: true) {
                    VStack(spacing: 8) {
                        inputField(label: "Host", text: $host)
                        inputField(label: "Port", text: $port, keyboardType: .numberPad)
                        inputField(label: "User", text: $user)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Password")
                                .font(.caption)
                                .foregroundColor(.gray)
                            SecureField("", text: $password)
                                .textFieldStyle(RoundedBorderTextFieldStyle())
                        }
                        
                        inputField(label: "Database Name", text: $dbName)
                        
                        Button(action: {
                            alertMessage = "Connecting to \(dbName)..."
                            showingAlert = true
                        }) {
                            HStack {
                                Image(systemName: "power")
                                Text("Connect to PostgreSQL")
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(AppTheme.primary)
                            .foregroundColor(.white)
                            .cornerRadius(8)
                        }
                    }
                }
                
                Text("Stats: Not connected to database")
                    .frame(maxWidth: .infinity)
                    .padding(16)
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                
                // Section 2: Metadata
                SectionCard(title: "Single Image Metadata", startOpen: true) {
                    VStack(spacing: 16) {
                        inputField(label: "Image File Path", text: $imagePath)
                        
                        HStack(spacing: 8) {
                            actionButton(label: "Browse")
                            actionButton(label: "View")
                            actionButton(label: "Load")
                        }
                        
                        ZStack {
                            Rectangle()
                                .fill(AppTheme.secondary.opacity(0.3))
                                .frame(height: 200)
                                .cornerRadius(8)
                            Text("Select an image to edit...")
                                .foregroundColor(AppTheme.onSecondary)
                        }
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Series Name")
                                .font(.caption)
                                .foregroundColor(.gray)
                            
                            Picker("Series Name", selection: $seriesName) {
                                Text("Select Series").tag("")
                                ForEach(seriesOptions, id: \.self) { series in
                                    Text(series).tag(series)
                                }
                            }
                            .pickerStyle(MenuPickerStyle())
                            .frame(maxWidth: .infinity)
                            .padding(8)
                            .background(RoundedRectangle(cornerRadius: 8).stroke(Color.gray.opacity(0.2), lineWidth: 1))
                        }
                        
                        inputField(label: "Characters (comma-separated)", text: $characters)
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Tags")
                                .font(AppTheme.Typography.titleSmall)
                            
                            FlowLayout(items: allTags, spacing: 8) { tag in
                                let isSelected = selectedTags.contains(tag)
                                Button(action: {
                                    if isSelected { selectedTags.remove(tag) } else { selectedTags.insert(tag) }
                                }) {
                                    Text(tag)
                                        .font(.caption)
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
                        }
                        
                        VStack(spacing: 8) {
                            actionButton(label: "Add/Update Image Path", color: AppTheme.primary, textColor: .white)
                            actionButton(label: "Update Loaded Metadata", color: AppTheme.primary, textColor: .white)
                            actionButton(label: "Delete from Database", color: .red, textColor: .white)
                        }
                    }
                }
            }
            .padding(16)
        }
        .alert("Database Action", isPresented: $showingAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
    }
    
    @ViewBuilder
    private func inputField(label: String, text: Binding<String>, keyboardType: UIKeyboardType = .default) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.caption)
                .foregroundColor(.gray)
            TextField("", text: text)
                .keyboardType(keyboardType)
                .textFieldStyle(RoundedBorderTextFieldStyle())
        }
    }
    
    @ViewBuilder
    private func actionButton(label: String, color: Color = AppTheme.primary.opacity(0.1), textColor: Color = AppTheme.primary) -> some View {
        Button(action: {}) {
            Text(label)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(color)
                .foregroundColor(textColor)
                .cornerRadius(8)
        }
    }
}