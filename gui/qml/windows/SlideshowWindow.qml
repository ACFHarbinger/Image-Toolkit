/*!
    \qmltype SlideshowWindow
    \inqmlmodule ImageToolkit.Windows
    \brief Fullscreen frameless slideshow window.

    SlideshowWindow is a frameless \l ApplicationWindow that stays on top of
    all other windows and displays images in full-screen.  Image transitions
    use an opacity \c Behavior for a smooth cross-fade.  An auto-advance
    \l Timer fires according to \l interval.  Hovering reveals a controls bar
    with PREV, PLAY/PAUSE, NEXT, and EXIT buttons.  The \c Escape key closes
    the window.

    \qmlproperty int SlideshowWindow::interval
    Slide duration in milliseconds, sourced from \c backend.interval.

    \qmlproperty bool SlideshowWindow::isPlaying
    Whether the slideshow is currently auto-advancing, sourced from
    \c backend.isPlaying.
*/
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

