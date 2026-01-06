pragma Singleton
import QtQuick 2.15

QtObject {
    // --- Dark Theme Colors (Default) ---
    readonly property color background: "#1e1e1e"
    readonly property color secondaryBackground: "#2d2d30"
    readonly property color text: "#cccccc"
    readonly property color accent: "#00bcd4"
    readonly property color accentHover: "#0097a7"
    readonly property color accentPressed: "#00838f"
    readonly property color border: "#3e3e3e"
    
    // --- Light Theme Colors ---
    readonly property color lightBackground: "#f5f5f5"
    readonly property color lightSecondaryBackground: "#ffffff"
    readonly property color lightText: "#1e1e1e"
    readonly property color lightAccent: "#007AFF"
    
    // --- Fonts ---
    readonly property string fontFamily: "Segoe UI"
    readonly property int fontSize: 13
    readonly property int headerFontSize: 18

    // --- Layout ---
    readonly property int padding: 10
    readonly property int borderRadius: 6
}
