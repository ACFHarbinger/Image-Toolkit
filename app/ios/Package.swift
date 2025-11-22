// swift-tools-version: 5.9
import PackageDescription

// Equivalent to build.gradle.kts dependencies and project structure
let package = Package(
    name: "ImageToolkit",
    defaultLocalization: "en",
    platforms: [
        // Equivalent to minSdk = 24 (Android 7). 
        // iOS 16 is a reasonable modern baseline comparable to recent Android targets.
        .iOS(.v16) 
    ],
    products: [
        // The main application module
        .library(
            name: "ImageToolkit",
            targets: ["ImageToolkit"]
        ),
    ],
    dependencies: [
        // --- 3rd Party Libraries (Equivalent to libs.coil.compose) ---
        // Kingfisher is the standard equivalent to Coil for image loading in Swift
        .package(url: "https://github.com/onevcat/Kingfisher.git", from: "7.10.0"),
        
        // Note: 
        // - androidx.core/lifecycle/activity -> Built-in 'UIKit' and 'SwiftUI'
        // - androidx.compose.* -> Built-in 'SwiftUI' framework
    ],
    targets: [
        // --- Local Module (Equivalent to implementation(project(":cryptography"))) ---
        .target(
            name: "Cryptography",
            dependencies: [],
            path: "Cryptography" // Assumes source files are in a 'Cryptography' folder
        ),
        
        // --- Main App Module ---
        .target(
            name: "ImageToolkit",
            dependencies: [
                "Cryptography", // Link local module
                "Kingfisher"    // Link external image loader
            ],
            path: "ImageToolkit" // Assumes source files are in 'ImageToolkit' folder
        ),
        
        // --- Testing (Equivalent to testImplementation / androidTestImplementation) ---
        .testTarget(
            name: "ImageToolkitTests",
            dependencies: ["ImageToolkit"],
            path: "ImageToolkitTests"
        ),
    ]
)