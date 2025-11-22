import SwiftUI

struct ScanScreen: View {
    @State private var scanDir: String = ""
    @State private var showingAlert = false
    @State private var alertMessage = ""
    @State private var showDirChooser = false
    
    let columns = [GridItem(.adaptive(minimum: 100), spacing: 8)]
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                SectionCard(title: "Scan Directory", startOpen: true) {
                    VStack(spacing: 16) {
                        HStack(alignment: .bottom) {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Directory to Scan")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                                TextField("", text: $scanDir)
                                    .textFieldStyle(RoundedBorderTextFieldStyle())
                            }
                            
                            Button(action: { showDirChooser = true }) {
                                Image(systemName: "folder")
                                    .padding()
                                    .background(Color.gray.opacity(0.1))
                                    .cornerRadius(8)
                            }
                        }
                        
                        Button(action: { /* View */ }) {
                            Text("View Full Size Image (from selection)")
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(AppTheme.primary)
                                .foregroundColor(.white)
                                .cornerRadius(8)
                        }
                        
                        Text("Scanned Images (Simulated)")
                            .font(AppTheme.Typography.titleMedium)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        
                        LazyVGrid(columns: columns, spacing: 8) {
                            ForEach(0..<20, id: \.self) { index in
                                Button(action: {
                                    alertMessage = "Selected Image \(index + 1)"
                                    showingAlert = true
                                }) {
                                    ZStack {
                                        Rectangle()
                                            .fill(AppTheme.secondary.opacity(0.3))
                                            .aspectRatio(1, contentMode: .fit)
                                            .cornerRadius(8)
                                        Text("Img \(index + 1)")
                                            .foregroundColor(AppTheme.onSecondary)
                                    }
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                        .frame(height: 400)
                        
                        VStack(spacing: 8) {
                            Button(action: { /* Add */ }) {
                                Text("Add Selected Images to Database")
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(AppTheme.primary)
                                    .foregroundColor(.white)
                                    .cornerRadius(8)
                            }
                            
                            Button(action: { /* Refresh */ }) {
                                Text("Refresh Image Directory")
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(AppTheme.secondary)
                                    .foregroundColor(AppTheme.onSecondary)
                                    .cornerRadius(8)
                            }
                            
                            Button(action: { /* Delete All */ }) {
                                Text("Delete All Image Paths in Directory")
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
            .padding(16)
        }
        .alert("Scan Action", isPresented: $showingAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
        .alert("Directory Chooser Opened", isPresented: $showDirChooser) {
            Button("OK", role: .cancel) { }
        }
    }
}