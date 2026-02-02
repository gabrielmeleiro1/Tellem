// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "AudiobookCreator",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(
            name: "AudiobookCreator",
            targets: ["AudiobookCreator"]
        )
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "AudiobookCreator",
            dependencies: [],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
    ]
)
