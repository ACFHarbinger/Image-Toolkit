import SwiftUI

struct MergeScreen: View {
    @State private var direction: String = "horizontal"
    @State private var inputPath: String = ""
    @State private var outputPath: String = ""
    @State private var spacing: String = "0"
    @State private var gridRows: String = "2"
    @State private var gridCols: String = "2"
    @State private var selectedFormats: Set<String> = []
    @State private var showingAlert = false
    @State private var alertMessage = ""
    
    let directions = ["horizontal", "vertical", "grid"]
    let allFormats = ["jpg", "png", "bmp", "gif", "webp", "tiff"]
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Merge Images")
                    .font(AppTheme.Typography.headlineSmall)
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Direction")
                        .font(.caption)
                        .foregroundColor(.gray)
                    
                    Picker("Direction", selection: $direction) {
                        ForEach(directions, id: \.self) { dir in
                            Text(dir.capitalized).tag(dir)
                        }
                    }
                    .pickerStyle(MenuPickerStyle())
                    .frame(maxWidth: .infinity)
                    .padding(8)
                    .background(RoundedRectangle(cornerRadius: 8).stroke(Color.gray.opacity(0.2), lineWidth: 1))
                }
                
                FileInput(label: "Input Paths (Files or Dir)", path: $inputPath)
                
                SectionCard(title: "Output Path (Optional)") {
                    FileInput(label: "Output Path", path: $outputPath)
                }
                
                FormatSelector(
                    title: "Input Formats (if input is dir)",
                    formats: allFormats,
                    selectedFormats: $selectedFormats
                )
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Spacing (px)")
                        .font(.caption)
                        .foregroundColor(.gray)
                    TextField("0", text: $spacing)
                        .keyboardType(.numberPad)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .onChange(of: spacing) { newValue in
                            spacing = newValue.filter { "0123456789".contains($0) }
                        }
                }
                
                if direction == "grid" {
                    HStack(spacing: 16) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Rows")
                                .font(.caption)
                                .foregroundColor(.gray)
                            TextField("2", text: $gridRows)
                                .keyboardType(.numberPad)
                                .textFieldStyle(RoundedBorderTextFieldStyle())
                                .onChange(of: gridRows) { newValue in
                                    gridRows = newValue.filter { "0123456789".contains($0) }
                                }
                        }
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Cols")
                                .font(.caption)
                                .foregroundColor(.gray)
                            TextField("2", text: $gridCols)
                                .keyboardType(.numberPad)
                                .textFieldStyle(RoundedBorderTextFieldStyle())
                                .onChange(of: gridCols) { newValue in
                                    gridCols = newValue.filter { "0123456789".contains($0) }
                                }
                        }
                    }
                }
                
                Button(action: {
                    alertMessage = "Running Merge:\nDirection: \(direction)\nInput: \(inputPath)"
                    showingAlert = true
                }) {
                    HStack {
                        Image(systemName: "play.fill")
                        Text("Run Merge")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(AppTheme.primary)
                    .foregroundColor(.white)
                    .cornerRadius(8)
                }
            }
            .padding(16)
        }
        .alert("Merge Action", isPresented: $showingAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
    }
}