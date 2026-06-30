import SwiftUI

/// Central design-token namespace for Image Toolkit (mirrors `Theme.kt` / `Type.kt`).
///
/// Use the static color constants rather than hard-coding hex values in views:
///
/// ```swift
/// Text("Title")
///     .foregroundColor(AppTheme.onSurface)
///     .background(AppTheme.surface)
/// ```
struct AppTheme {
    // MARK: - Brand colours

    /// Primary brand colour — deep purple `#6200EE`.
    static let primary    = Color(hex: 0x6200EE)
    /// Secondary / accent colour — teal `#03DAC6`.
    static let secondary  = Color(hex: 0x03DAC6)
    /// Tertiary / dark purple `#3700B3`, used for pressed states.
    static let tertiary   = Color(hex: 0x3700B3)

    // MARK: - Surface colours

    /// App background (light theme: white).
    static let background  = Color.white
    /// Card / sheet surface colour.
    static let surface     = Color.white

    // MARK: - On-colour tokens

    /// Text / icon colour on top of ``primary``.
    static let onPrimary    = Color.white
    /// Text / icon colour on top of ``secondary``.
    static let onSecondary  = Color.black
    /// Text / icon colour on top of ``background``.
    static let onBackground = Color.black
    /// Text / icon colour on top of ``surface``.
    static let onSurface    = Color.black

    // MARK: - Typography scale

    /// Material Design 3 typography scale mapped to SF system fonts.
    ///
    /// Mirrors `Type.kt` in the Android module. Use these constants in views
    /// instead of `Font.system(size:weight:)` to keep typography consistent.
    struct Typography {
        /// 32 pt bold — page-level headlines.
        static let headlineLarge  = Font.system(size: 32, weight: .bold)
        /// 28 pt bold — section headlines.
        static let headlineMedium = Font.system(size: 28, weight: .bold)
        /// 24 pt semibold — sub-section headlines.
        static let headlineSmall  = Font.system(size: 24, weight: .semibold)

        /// 22 pt semibold — card / dialog titles.
        static let titleLarge  = Font.system(size: 22, weight: .semibold)
        /// 18 pt medium — list item titles.
        static let titleMedium = Font.system(size: 18, weight: .medium)
        /// 16 pt medium — compact titles.
        static let titleSmall  = Font.system(size: 16, weight: .medium)

        /// 16 pt regular — primary body copy.
        static let bodyLarge  = Font.system(size: 16, weight: .regular)
        /// 14 pt regular — secondary / caption body copy.
        static let bodyMedium = Font.system(size: 14, weight: .regular)
    }
}

// MARK: - Color hex initialiser

extension Color {
    /// Initialise a `Color` from a 24-bit hex literal and an optional opacity.
    ///
    /// - Parameters:
    ///   - hex: 24-bit RGB value, e.g. `0x6200EE`.
    ///   - alpha: Opacity in `[0, 1]` (default `1`).
    ///
    /// ```swift
    /// let purple = Color(hex: 0x6200EE)
    /// let semiTransparent = Color(hex: 0x03DAC6, alpha: 0.5)
    /// ```
    init(hex: UInt, alpha: Double = 1) {
        self.init(
            .sRGB,
            red:     Double((hex >> 16) & 0xff) / 255,
            green:   Double((hex >> 08) & 0xff) / 255,
            blue:    Double((hex >> 00) & 0xff) / 255,
            opacity: alpha
        )
    }
}