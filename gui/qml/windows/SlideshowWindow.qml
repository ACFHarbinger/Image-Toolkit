import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import ".."

ApplicationWindow {
    id: window
    width: Screen.width
    height: Screen.height
    visible: true
    title: "Slideshow"
    color: "black"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

    property int interval: backend.interval
    property bool isPlaying: backend.isPlaying

    // Background Image
    Image {
        id: bgImage
        anchors.fill: parent
        source: backend.currentImagePath
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        
        Behavior on opacity { NumberAnimation { duration: 1000 } }
    }

    // Foreground Image (unused for now, keeping structure)
    Image {
        id: fgImage
        anchors.fill: parent
        source: ""
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        opacity: 0
    }

    Timer {
        id: slideshowTimer
        interval: window.interval
        running: window.isPlaying
        repeat: true
        onTriggered: backend.next()
    }

    // Hidden Controls (appear on mouse move)
    Rectangle {
        id: controls
        width: 400
        height: 80
        color: Qt.rgba(0, 0, 0, 0.7)
        radius: 40
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 50
        anchors.horizontalCenter: parent.horizontalCenter
        opacity: mouseArea.containsMouse ? 1 : 0
        visible: opacity > 0

        Behavior on opacity { NumberAnimation { duration: 300 } }

        RowLayout {
            anchors.centerIn: parent
            spacing: 25

            AppButton {
                text: "PREV"
                background: null
                contentItem: Text { text: parent.text; color: "white"; font.bold: true }
                onClicked: backend.previous()
            }

            AppButton {
                text: isPlaying ? "PAUSE" : "PLAY"
                background: Rectangle { width: 60; height: 60; radius: 30; color: Style.accent }
                onClicked: backend.setPlaying(!isPlaying)
            }

            AppButton {
                text: "NEXT"
                background: null
                contentItem: Text { text: parent.text; color: "white"; font.bold: true }
                onClicked: backend.next()
            }
            
            AppButton {
                text: "EXIT"
                onClicked: window.close()
            }
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        onClicked: controls.opacity = 1.0
    }

    Shortcut {
        sequence: "Escape"
        onActivated: window.close()
    }
}

