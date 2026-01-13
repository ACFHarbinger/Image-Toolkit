import QtQuick 2.15

pragma Singleton

QtObject {
    // Colors
    readonly property color background: "#0f111a"
    readonly property color secondaryBackground: "#1a1c2e"
    readonly property color accent: "#7289da"
    readonly property color text: "#e0e0e0"
    readonly property color border: "#2d314d"
    
    // Layout
    readonly property int borderRadius: 8
    readonly property int sidebarWidth: 200
    readonly property int headerHeight: 60
}
