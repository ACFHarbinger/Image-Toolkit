/*!
    \qmltype Style
    \inqmlmodule ImageToolkit
    \brief Application-wide design-token singleton.

    Style is a \c pragma Singleton \l QtObject that centralises every colour
    and layout constant used across the Image Toolkit QML layer.  All
    properties are \c readonly.

    \qmlproperty color Style::background
    Primary window background colour (\c #0f111a).

    \qmlproperty color Style::secondaryBackground
    Panel and card background colour (\c #1a1c2e).

    \qmlproperty color Style::accent
    Interactive element accent colour (\c #7289da).

    \qmlproperty color Style::text
    Primary text colour (\c #e0e0e0).

    \qmlproperty color Style::mutedText
    Secondary / placeholder text colour (\c #888888).

    \qmlproperty color Style::border
    Border and separator colour (\c #2d314d).

    \qmlproperty int Style::borderRadius
    Default corner radius in pixels (\c 8).

    \qmlproperty int Style::sidebarWidth
    Fixed width of the collapsible sidebar in pixels (\c 200).

    \qmlproperty int Style::headerHeight
    Height of the top-bar header in pixels (\c 60).
*/
import QtQuick 2.15

pragma Singleton

QtObject {
    // Colors
    readonly property color background: "#0f111a"
    readonly property color secondaryBackground: "#1a1c2e"
    readonly property color accent: "#7289da"
    readonly property color text: "#e0e0e0"
    readonly property color mutedText: "#888888"
    readonly property color border: "#2d314d"
    
    // Layout
    readonly property int borderRadius: 8
    readonly property int sidebarWidth: 200
    readonly property int headerHeight: 60
}
