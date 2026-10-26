// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "CelShadedGenerator",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "CelShadedGenerator", targets: ["cel_shaded_generator"])
    ],
    targets: [
        .target(name: "cel_shaded_generator", path: "cel_shaded_generator")
    ]
)
