/*!
    \qmltype BlinkComparator
    \inqmlmodule ImageToolkit.Components
    \brief "Blink" A/B comparator — Space (or click) toggles between two
           images in place so differences pop out perceptually.
*/
import QtQuick 2.15
import "../"

Rectangle {
    id: root
    property string pathA: ""
    property string pathB: ""
    property bool showingA: true

    color: "black"
    focus: true

    function blink() { showingA = !showingA }

    Keys.onSpacePressed: blink()

    Image {
        anchors.fill: parent
        source: root.pathA ? "file://" + root.pathA : ""
        fillMode: Image.PreserveAspectFit
        visible: root.showingA
        asynchronous: true
        cache: true
    }
    Image {
        anchors.fill: parent
        source: root.pathB ? "file://" + root.pathB : ""
        fillMode: Image.PreserveAspectFit
        visible: !root.showingA
        asynchronous: true
        cache: true
    }

    MouseArea {
        anchors.fill: parent
        onClicked: { root.forceActiveFocus(); root.blink() }
    }

    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 10
        width: badge.width + 16
        height: badge.height + 8
        radius: Style.borderRadius
        color: root.showingA ? Style.accent : "#e67e22"
        Text {
            id: badge
            anchors.centerIn: parent
            text: root.showingA ? "A" : "B"
            color: "white"
            font.bold: true
        }
    }

    Text {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.margins: 8
        text: "Space / click to blink"
        color: Style.mutedText
        font.pixelSize: 11
    }
}
