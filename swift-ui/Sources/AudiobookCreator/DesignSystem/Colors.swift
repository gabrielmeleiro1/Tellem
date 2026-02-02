import SwiftUI

// MARK: - Industrial Moss Color Palette

extension Color {
    // Core Backgrounds
    static let mossCore = Color(hex: "#1a1b1a")
    static let mossSurface = Color(hex: "#282828")
    static let mossElevated = Color(hex: "#32302f")
    
    // Borders
    static let mossBorder = Color(hex: "#3c3836")
    static let mossBorderFocus = Color(hex: "#504945")
    static let mossBorderAccent = Color(hex: "#665c54")
    
    // Text
    static let mossTextMain = Color(hex: "#d5c4a1")
    static let mossTextDim = Color(hex: "#a89984")
    static let mossTextFaded = Color(hex: "#7c6f64")
    
    // Accents
    static let mossAccent = Color(hex: "#859900")      // Olive green
    static let mossAccentActive = Color(hex: "#98971a")
    static let mossGold = Color(hex: "#b57614")        // Warning
    static let mossRust = Color(hex: "#af3a03")        // Error
    
    // Status
    static let mossSuccess = Color(hex: "#79740e")
    static let mossInfo = Color(hex: "#458588")
    
    // Initialize from hex string
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }

        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - View Modifiers

struct MossPanelStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .background(Color.mossSurface)
            .border(Color.mossBorder, width: 1)
    }
}

struct MossButtonStyle: ButtonStyle {
    var isPrimary: Bool = false
    
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(.caption, design: .monospaced))
            .textCase(.uppercase)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                isPrimary 
                    ? (configuration.isPressed ? Color.mossAccentActive : Color.mossAccent)
                    : (configuration.isPressed ? Color.mossElevated : Color.mossCore)
            )
            .foregroundColor(isPrimary ? Color.mossCore : Color.mossTextMain)
            .border(isPrimary ? Color.mossAccent : Color.mossBorder, width: 1)
            .opacity(configuration.isPressed ? 0.9 : 1.0)
    }
}

// MARK: - View Extensions

extension View {
    func mossPanel() -> some View {
        modifier(MossPanelStyle())
    }
}
