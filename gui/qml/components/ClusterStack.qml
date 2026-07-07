/*!
    \qmltype ClusterStack
    \inqmlmodule ImageToolkit.Components
    \brief "Album" card for one cluster of similar images: fanned thumbnail
           stack, member count, mean confidence bar and detection-tier badge.
*/
import QtQuick 2.15
import "../"

Rectangle {
    id: root
    property var paths: []
    property string clusterId: ""
    property int clusterSize: 0
    property real confidence: 0
    property string tier: ""
    property string keeperPath: ""
    property bool current: false
    signal clicked()

    width: 190
    height: 220
    radius: Style.borderRadius
    color: current ? Qt.darker(Style.accent, 2.5) : Style.secondaryBackground
    border.color: current ? Style.accent : Style.border
    border.width: current ? 2 : 1

    function tierColor(t) {
        if (t === "exact") return "#2ecc71"
        if (t === "structural") return "#e67e22"
        if (t === "perceptual") return "#3498db"
        return "#9b59b6"   // semantic
    }

    Column {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        // Fanned stack of up to 3 thumbnails
        Item {
            width: parent.width
            height: 140

            Repeater {
                model: Math.min(3, root.paths.length)
                delegate: Rectangle {
                    property int rev: Math.min(3, root.paths.length) - 1 - index
                    x: rev * 8
                    y: rev * 6
                    width: parent.width - 20
                    height: 126
                    radius: 4
                    color: "black"
                    border.color: Style.border
                    z: index
                    Image {
                        anchors.fill: parent
                        anchors.margins: 1
                        source: "file://" + root.paths[rev]
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: 320
                    }
                }
            }

            // member count badge
            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                width: countText.width + 14
                height: 22
                radius: 11
                color: Style.accent
                z: 10
                Text {
                    id: countText
                    anchors.centerIn: parent
                    text: root.clusterSize
                    color: "white"
                    font.bold: true
                    font.pixelSize: 12
                }
            }
        }

        // tier badge + confidence
        Row {
            spacing: 6
            Rectangle {
                width: tierText.width + 12
                height: 18
                radius: 9
                color: root.tierColor(root.tier)
                Text {
                    id: tierText
                    anchors.centerIn: parent
                    text: root.tier
                    color: "white"
                    font.pixelSize: 10
                    font.bold: true
                }
            }
            Text {
                text: (root.confidence * 100).toFixed(0) + "%"
                color: Style.text
                font.pixelSize: 12
            }
        }

        // confidence bar
        Rectangle {
            width: parent.width
            height: 5
            radius: 2
            color: Style.border
            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, root.confidence))
                height: parent.height
                radius: 2
                color: root.tierColor(root.tier)
            }
        }

        Text {
            width: parent.width
            text: root.keeperPath
                  ? "keep: " + String(root.keeperPath).split("/").pop()
                  : ""
            color: Style.mutedText
            font.pixelSize: 10
            elide: Text.ElideMiddle
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.clicked()
        hoverEnabled: true
        onEntered: if (!root.current) root.border.color = Style.accent
        onExited: if (!root.current) root.border.color = Style.border
    }
}
