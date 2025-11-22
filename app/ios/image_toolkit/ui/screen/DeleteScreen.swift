import SwiftUI

struct DeleteScreen: View {
    @State private var targetPath: String = ""
    @State private var confirmDelete: Bool = true
    @State private var selectedExtensions: Set<String> = []
    @State private var showingAlert = false
    @State private var alertMessage = ""
    
    let allExtensions = ["jpg", "png", "bmp", "gif", "webp", "tiff", "txt", "tmp"]
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Delete Files")
                    .font(AppTheme.Typography.headlineSmall)
                
                FileInput(label: "Target Path (File or Dir)", path: $targetPath)
                
                FormatSelector(
                    title: "Target Extensions (Optional)",
                    formats: allExtensions,
                    selectedFormats: $selectedExtensions
                )
                
                Toggle("Require confirmation before delete", isOn: $confirmDelete)
                    .padding(.vertical, 8)
                
                Button(action: {
                    alertMessage = "Running Delete:\nTarget: \(targetPath)\nConfirm: \(confirmDelete)"
                    showingAlert = true
                }) {
                    HStack {
                        Image(systemName: "trash.fill")
                        Text("Run Delete")
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.red)
                    .foregroundColor(.white)
                    .cornerRadius(8)
                }
            }
            .padding(16)
        }
        .alert("Delete Action", isPresented: $showingAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
    }
}