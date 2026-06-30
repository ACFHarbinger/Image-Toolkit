import SwiftUI

/// A labelled text field with "Choose File" and "Choose Dir" buttons.
///
/// Displays an editable path field below a caption label and two action buttons
/// that simulate file / directory picker dialogs. On iOS the picker is shown via
/// a `UIDocumentPickerViewController`; the current implementation shows alert
/// stubs as placeholders for that integration.
///
/// ```swift
/// @State private var inputPath = ""
///
/// FileInput(label: "Input directory", path: $inputPath)
/// ```
struct FileInput: View {
    /// Caption text displayed above the path field.
    let label: String
    /// Binding to the selected file or directory path string.
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