/*!
    \qmltype TetheredViewport
    \inqmlmodule ImageToolkit.Components
    \brief Side-by-side viewers with synchronised ("tethered") zoom and pan:
           wheel zooms every pane around the cursor, drag pans all panes.
*/
import QtQuick 2.15
import "../"

Rectangle {
    id: root
    property var paths: []          // list of image paths shown side by side
    property real zoom: 1.0
    property real panX: 0
    property real panY: 0

    color: "black"

    function reset() { zoom = 1.0; panX = 0; panY = 0 }
    onPathsChanged: reset()

    Row {
        anchors.fill: parent
        Repeater {
            model: root.paths
            delegate: Rectangle {
                width: root.width / Math.max(1, root.paths.length)
                height: root.height
                color: "black"
                border.color: Style.border
                clip: true

                Image {
                    id: img
                    source: "file://" + modelData
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    width: parent.width
                    height: parent.height
                    transform: [
                        Scale {
                            origin.x: img.width / 2
                            origin.y: img.height / 2
                            xScale: root.zoom
                            yScale: root.zoom
                        },
                        Translate { x: root.panX; y: root.panY }
                    ]
                }

                Text {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.margins: 6
                    text: String(modelData).split("/").pop()
                    color: "white"
                    font.pixelSize: 10
                    style: Text.Outline; styleColor: "black"
                    width: parent.width - 12
                    elide: Text.ElideMiddle
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        property real lastX: 0
        property real lastY: 0
        onPressed: { lastX = mouse.x; lastY = mouse.y }
        onPositionChanged: {
            if (pressed) {
                root.panX += mouse.x - lastX
                root.panY += mouse.y - lastY
                lastX = mouse.x
                lastY = mouse.y
            }
        }
        onWheel: {
            var factor = wheel.angleDelta.y > 0 ? 1.15 : 1 / 1.15
            root.zoom = Math.max(0.2, Math.min(16, root.zoom * factor))
        }
        onDoubleClicked: root.reset()
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
    }

    Text {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 8
        text: "zoom " + root.zoom.toFixed(2) + "x — double-click to reset"
        color: Style.mutedText
        font.pixelSize: 11
    }
}
