import SwiftUI

struct ConvertScreen: View {
    @State private var outputFormat: String = "png"
    @State private var inputPath: String = ""
    @State private var outputPath: String = ""
    @State private var selectedFormats: Set<String> = []
    @State private var showingAlert = false
    @State private var alertMessage = ""

    let allFormats = ["jpg", "png", "bmp", "gif", "webp", "tiff"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Convert Image Format")
                    .font(AppTheme.Typography.headlineSmall)
                
                VStack(alignment: .leading, spacing: 8) {
                    Text("Output Format")
                        .font(.caption)
                        .foregroundColor(.gray)
                    TextField("png", text: $outputFormat)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                
                FileInput(label: "Input Path (File or Dir)", path: $inputPath)
                
                SectionCard(title: "Output Path (Optional)") {
                    FileInput(label: "Output Path", path: $outputPath)
                }
                
                FormatSelector(
                    title: "Input Formats (if input is dir)",
                    formats: allFormats,
                    selectedFormats: $selectedFormats
                )
                
                Button(action: {
                    alertMessage = "Running Convert: \n- Format: \(outputFormat)\n- Input: \(inputPath)"
                    showingAlert = true
                }) {
                    HStack {
                        Image(systemName: "play.fill")
                        Text("Run Conversion")
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
        .alert("Convert Action", isPresented: $showingAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
    }
}