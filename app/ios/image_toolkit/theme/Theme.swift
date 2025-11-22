import SwiftUI

// Equivalent to Theme.kt and Type.kt

struct AppTheme {
    static let primary = Color(hex: 0x6200EE)
    static let secondary = Color(hex: 0x03DAC6)
    static let tertiary = Color(hex: 0x3700B3)
    
    static let background = Color.white
    static let surface = Color.white
    static let onPrimary = Color.white
    static let onSecondary = Color.black
    static let onBackground = Color.black
    static let onSurface = Color.black
    
    // Typography (Approximation of Type.kt)
    struct Typography {
        static let headlineLarge = Font.system(size: 32, weight: .bold)
        static let headlineMedium = Font.system(size: 28, weight: .bold)
        static let headlineSmall = Font.system(size: 24, weight: .semibold)
        
        static let titleLarge = Font.system(size: 22, weight: .semibold)
        static let titleMedium = Font.system(size: 18, weight: .medium)
        static let titleSmall = Font.system(size: 16, weight: .medium)
        
        static let bodyLarge = Font.system(size: 16, weight: .regular)
        static let bodyMedium = Font.system(size: 14, weight: .regular)
    }
}

// Helper for Hex Colors
extension Color {
    init(hex: UInt, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xff) / 255,
            green: Double((hex >> 08) & 0xff) / 255,
            blue: Double((hex >> 00) & 0xff) / 255,
            opacity: alpha
        )
    }
}