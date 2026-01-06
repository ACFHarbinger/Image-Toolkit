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
    color: "#000000" // Black background for previews

    property real zoomFactor: 1.0
    property string currentImagePath: ""

    // Overlay Controls
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
                text: currentImagePath.split('/').pop()
                color: "white"
                font.bold: true
                Layout.fillWidth: true
            }

            RowLayout {
                spacing: 15
                AppButton { text: "Zoom In"; Layout.preferredWidth: 100 }
                AppButton { text: "Zoom Out"; Layout.preferredWidth: 100 }
                AppButton { text: "Fit Screen"; Layout.preferredWidth: 100 }
                AppButton { text: "Close"; Layout.preferredWidth: 80; onClicked: window.close() }
            }
        }
    }

    // Main Image Area
    Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: img.width * zoomFactor
        contentHeight: img.height * zoomFactor
        clip: true

        Image {
            id: img
            source: currentImagePath
            width: parent.width
            height: parent.height
            fillMode: Image.PreserveAspectFit
            scale: zoomFactor
            transformOrigin: Item.Center
            asynchronous: true
            
            onStatusChanged: {
                if (status == Image.Ready) {
                    // Initial fit logic could go here
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            onWheel: {
                if (wheel.modifiers & Qt.ControlModifier) {
                    zoomFactor += wheel.angleDelta.y > 0 ? 0.1 : -0.1
                    if (zoomFactor < 0.1) zoomFactor = 0.1
                }
            }
        }
    }

    // Navigation Overlay
    RowLayout {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 30
        spacing: 20
        z: 10

        AppButton {
            text: "← Previous"
            Layout.preferredWidth: 120
            background: Rectangle { color: Qt.rgba(0, 0, 0, 0.5); border.color: "white"; radius: 20 }
        }
        
        Rectangle {
            width: 100; height: 40; radius: 20; color: Qt.rgba(0, 0, 0, 0.5)
            Text { anchors.centerIn: parent; text: "1 / 42"; color: "white"; font.bold: true }
        }

        AppButton {
            text: "Next →"
            Layout.preferredWidth: 120
            background: Rectangle { color: Qt.rgba(0, 0, 0, 0.5); border.color: "white"; radius: 20 }
        }
    }
}

