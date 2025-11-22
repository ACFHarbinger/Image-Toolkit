import SwiftUI

struct FileInput: View {
    let label: String
    @Binding var path: String
    @State private var showFileAlert = false
    @State private var showDirAlert = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.caption)
                .foregroundColor(.gray)
            
            TextField("Select path...", text: $path)
                .textFieldStyle(RoundedBorderTextFieldStyle())
            
            HStack(spacing: 16) {
                Button(action: {
                    showFileAlert = true
                }) {
                    Label("Choose File", systemImage: "doc")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(AppTheme.primary)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                
                Button(action: {
                    showDirAlert = true
                }) {
                    Label("Choose Dir", systemImage: "folder")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(AppTheme.primary)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
            }
        }
        .alert("File Chooser Opened", isPresented: $showFileAlert) {
            Button("OK", role: .cancel) { }
        }
        .alert("Directory Chooser Opened", isPresented: $showDirAlert) {
            Button("OK", role: .cancel) { }
        }
    }
}