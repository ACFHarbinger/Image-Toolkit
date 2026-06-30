/*!
    \qmltype ImagePreviewWindow
    \inqmlmodule ImageToolkit.Windows
    \brief Floating image preview window with zoom and pan.

    ImagePreviewWindow opens as a separate 1024 × 768 \l ApplicationWindow
    with a black background.  It supports:
    \list
      \li Zoom in / zoom out / fit-screen toolbar buttons.
      \li Ctrl+wheel zoom via a wheel \l MouseArea.
      \li Pan via a \l Flickable.
      \li Optional PREV / NEXT navigation when a \l backend is provided.
    \endlist

    \qmlproperty real ImagePreviewWindow::zoomFactor
    Current zoom multiplier.  Defaults to \c 1.0.

    \qmlproperty string ImagePreviewWindow::imagePath
    Static image path.  Takes precedence over \l backend's path when set.

    \qmlproperty var ImagePreviewWindow::backend
    Optional backend exposing \c currentImagePath, \c previous(), \c next(),
    and \c navigationInfo.  When set, navigation controls are visible.

    \qmlproperty string ImagePreviewWindow::currentSource
    Resolved source: \l imagePath if non-empty, otherwise
    \c backend.currentImagePath.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import ".."

ApplicationWindow {
    id: window
    width: 1024
    height: 768
    visible: true
    title: "Image Preview"
    color: "#000000"

    property real zoomFactor: 1.0
    property string imagePath: ""
    property var backend
    property string currentSource: imagePath !== "" ? imagePath
                                                    : (backend ? backend.currentImagePath : "")

    // Header bar
    Rectangle {
        id: header
        z: 10
        width: parent.width
        height: 60
        color: Qt.rgba(0, 0, 0, 0.6)
        anchors.top: parent.top

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 20

            Text {
                text: currentSource ? currentSource.split("/").pop() : "No Image"
                color: "white"
                font.bold: true
                Layout.fillWidth: true
                elide: Text.ElideLeft
            }

            RowLayout {
                spacing: 15
                AppButton {
                    text: "Zoom In"
                    Layout.preferredWidth: 90
                    onClicked: zoomFactor = Math.min(zoomFactor + 0.2, 10.0)
                }
                AppButton {
                    text: "Zoom Out"
                    Layout.preferredWidth: 90
                    onClicked: zoomFactor = Math.max(zoomFactor - 0.2, 0.1)
                }
                AppButton {
                    text: "Fit Screen"
                    Layout.preferredWidth: 90
                    onClicked: zoomFactor = 1.0
                }
                AppButton {
                    text: "Close"
                    Layout.preferredWidth: 70
                    onClicked: window.close()
                }
            }
        }
    }

    // Main image area — Flickable for pan
    Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: img.width * zoomFactor
        contentHeight: img.height * zoomFactor
        clip: true

        Image {
            id: img
            source: window.currentSource
            width: flick.width
            height: flick.height
            fillMode: Image.PreserveAspectFit
            scale: zoomFactor
            transformOrigin: Item.Center
            asynchronous: true
        }

        MouseArea {
            anchors.fill: parent
            onWheel: {
                if (wheel.modifiers & Qt.ControlModifier) {
                    var delta = wheel.angleDelta.y > 0 ? 0.1 : -0.1
                    zoomFactor = Math.min(Math.max(zoomFactor + delta, 0.1), 10.0)
                }
            }
        }
    }

    // Navigation overlay (visible only when a backend with prev/next is supplied)
    RowLayout {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 30
        spacing: 20
        z: 10
        visible: window.backend !== undefined && window.backend !== null

        AppButton {
            text: "← Previous"
            Layout.preferredWidth: 120
            background: Rectangle { color: Qt.rgba(0, 0, 0, 0.5); border.color: "white"; radius: 20 }
            onClicked: if (backend) backend.previous()
        }

        Rectangle {
            width: 100; height: 40; radius: 20
            color: Qt.rgba(0, 0, 0, 0.5)
            Text {
                anchors.centerIn: parent
                text: backend ? backend.navigationInfo : ""
                color: "white"
                font.bold: true
            }
        }

        AppButton {
            text: "Next →"
            Layout.preferredWidth: 120
            background: Rectangle { color: Qt.rgba(0, 0, 0, 0.5); border.color: "white"; radius: 20 }
            onClicked: if (backend) backend.next()
        }
    }

    Shortcut { sequence: "Escape"; onActivated: window.close() }
}
