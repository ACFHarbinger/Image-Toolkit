/*!
    \qmltype SwipeCompare
    \inqmlmodule ImageToolkit.Components
    \brief Swipe overlay comparator — a draggable vertical divider reveals
           image B over image A for direct pixel comparison.
*/
import QtQuick 2.15
import "../"

Rectangle {
    id: root
    property string pathA: ""
    property string pathB: ""
    property real splitRatio: 0.5

    color: "black"
    clip: true

    Image {
        id: imgA
        anchors.fill: parent
        source: root.pathA ? "file://" + root.pathA : ""
        fillMode: Image.PreserveAspectFit
        asynchronous: true
    }

    // Right side shows B, clipped at the divider
    Item {
        anchors.fill: parent
        clip: true
        Rectangle {
            x: root.splitRatio * root.width
            width: root.width - x
            height: root.height
            color: "black"
            clip: true
            Image {
                x: -root.splitRatio * root.width
                width: root.width
                height: root.height
                source: root.pathB ? "file://" + root.pathB : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
        }
    }

    // Divider + handle
    Rectangle {
        id: divider
        x: root.splitRatio * root.width - width / 2
        width: 2
        height: parent.height
        color: Style.accent

        Rectangle {
            anchors.centerIn: parent
            width: 26
            height: 26
            radius: 13
            color: Style.accent
            border.color: "white"
            Text { anchors.centerIn: parent; text: "↔"; color: "white" }
        }
    }

    MouseArea {
        anchors.fill: parent
        onPositionChanged: if (pressed) root.splitRatio =
            Math.max(0.02, Math.min(0.98, mouse.x / root.width))
        onPressed: root.splitRatio =
            Math.max(0.02, Math.min(0.98, mouse.x / root.width))
        cursorShape: Qt.SplitHCursor
    }

    Text {
        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 8
        text: "A"; color: "white"; font.bold: true
        style: Text.Outline; styleColor: "black"
    }
    Text {
        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8
        text: "B"; color: "white"; font.bold: true
        style: Text.Outline; styleColor: "black"
    }
}
