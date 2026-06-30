/*!
    \qmltype LandmarkEditorDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief §2.9A BigWarp-style landmark editor for manual edge override.

    LandmarkEditorDialog shows two frame thumbnails side by side.  The user
    clicks corresponding points on each thumbnail to define landmark pairs
    used to reconstruct a failed edge in bundle adjustment.  One pair gives
    a pure translation; two pairs give partial affine; three or more give a
    full affine estimate.

    Backend (\l backend) must expose:
    \list
      \li \c frameIImage — string URL of the left thumbnail (frame i).
      \li \c frameJImage — string URL of the right thumbnail (frame j).
      \li \c frameI — int, index of left frame.
      \li \c frameJ — int, index of right frame.
      \li \c landmarks — list of objects with \c xi, \c yi, \c xj, \c yj
          (all normalised 0–1).
      \li \c addLandmark(xi, yi, xj, yj) — slot.
      \li \c removeLandmark(index) — slot.
      \li \c accept() — slot; finalises edge from current landmarks.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var LandmarkEditorDialog::backend
    Pipeline HITL backend for landmark-based edge override.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"
import "../components"

Rectangle {
    id: root

    property var backend: null
    signal accepted()
    signal cancelled()

    // Click state: waiting for click on i, then on j
    property point _pendingI: Qt.point(-1, -1)
    property bool _awaitingJ: false

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 820
    implicitHeight: 580

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        Text { text: "Landmark Editor — Frame " + (backend ? backend.frameI : "?") + " ↔ Frame " + (backend ? backend.frameJ : "?"); color: Style.text; font.pixelSize: 18; font.bold: true }
        Text {
            text: root._awaitingJ ? "Now click the matching point on the RIGHT frame."
                                  : "Click a point on the LEFT frame to begin a new landmark pair."
            color: Style.accent; font.pixelSize: 12
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // Frame i
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Text { text: "Frame " + (backend ? backend.frameI : "?"); color: Style.mutedText; font.pixelSize: 11 }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#000000"
                    border.color: root._awaitingJ ? Style.border : Style.accent
                    border.width: root._awaitingJ ? 1 : 2

                    Image {
                        id: imgI
                        anchors.fill: parent
                        source: backend ? backend.frameIImage : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }

                    // Landmark dots on frame i
                    Repeater {
                        model: backend ? backend.landmarks : []
                        Rectangle {
                            x: modelData.xi * imgI.paintedWidth + (imgI.width - imgI.paintedWidth) / 2 - 6
                            y: modelData.yi * imgI.paintedHeight + (imgI.height - imgI.paintedHeight) / 2 - 6
                            width: 12; height: 12; radius: 6
                            color: ["#ff5050","#50c850","#5098ff","#f0c030"][index % 4]
                            Text { anchors.centerIn: parent; text: index + 1; color: "white"; font.pixelSize: 8; font.bold: true }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: root._awaitingJ ? Qt.ArrowCursor : Qt.CrossCursor
                        enabled: !root._awaitingJ
                        onClicked: {
                            var xi = (mouse.x - (imgI.width - imgI.paintedWidth) / 2) / imgI.paintedWidth
                            var yi = (mouse.y - (imgI.height - imgI.paintedHeight) / 2) / imgI.paintedHeight
                            root._pendingI = Qt.point(xi, yi)
                            root._awaitingJ = true
                        }
                    }
                }
            }

            // Frame j
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Text { text: "Frame " + (backend ? backend.frameJ : "?"); color: Style.mutedText; font.pixelSize: 11 }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#000000"
                    border.color: root._awaitingJ ? Style.accent : Style.border
                    border.width: root._awaitingJ ? 2 : 1

                    Image {
                        id: imgJ
                        anchors.fill: parent
                        source: backend ? backend.frameJImage : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }

                    Repeater {
                        model: backend ? backend.landmarks : []
                        Rectangle {
                            x: modelData.xj * imgJ.paintedWidth + (imgJ.width - imgJ.paintedWidth) / 2 - 6
                            y: modelData.yj * imgJ.paintedHeight + (imgJ.height - imgJ.paintedHeight) / 2 - 6
                            width: 12; height: 12; radius: 6
                            color: ["#ff5050","#50c850","#5098ff","#f0c030"][index % 4]
                            Text { anchors.centerIn: parent; text: index + 1; color: "white"; font.pixelSize: 8; font.bold: true }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: root._awaitingJ ? Qt.CrossCursor : Qt.ArrowCursor
                        enabled: root._awaitingJ
                        onClicked: {
                            var xj = (mouse.x - (imgJ.width - imgJ.paintedWidth) / 2) / imgJ.paintedWidth
                            var yj = (mouse.y - (imgJ.height - imgJ.paintedHeight) / 2) / imgJ.paintedHeight
                            if (backend) backend.addLandmark(root._pendingI.x, root._pendingI.y, xj, yj)
                            root._awaitingJ = false
                            root._pendingI = Qt.point(-1, -1)
                        }
                    }
                }
            }
        }

        // Landmark list
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Text { text: "Landmarks: " + (backend ? backend.landmarks.length : 0) + "  (1 pair = translation, 2 = partial affine, 3+ = full affine)"; color: Style.mutedText; font.pixelSize: 11; Layout.fillWidth: true }
            AppButton {
                text: "Undo Last"
                enabled: backend && backend.landmarks.length > 0
                onClicked: if (backend) backend.removeLandmark(backend.landmarks.length - 1)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Item { Layout.fillWidth: true }
            AppButton {
                text: "Cancel"
                background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                onClicked: { if (backend) backend.cancel(); root.cancelled() }
            }
            AppButton {
                text: "Accept Edge"
                background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                enabled: backend && backend.landmarks.length >= 1
                onClicked: { if (backend) backend.accept(); root.accepted() }
            }
        }
    }
}
