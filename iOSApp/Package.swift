// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "JewelElite",
    platforms: [
        .iOS(.v15)
    ],
    products: [
        .executable(name: "JewelElite", targets: ["JewelElite"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "JewelElite",
            dependencies: [],
            path: ".",
            exclude: [
                "Package.swift",
                "SIDELOAD_GUIDE.md"
            ]
        )
    ]
)
