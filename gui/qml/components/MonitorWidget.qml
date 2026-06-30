/*!
    \qmltype MonitorWidget
    \inqmlmodule ImageToolkit.Components
    \brief Single monitor display tile with drag-and-drop image assignment.

    MonitorWidget renders a 200 × 150 px rectangle representing one physical
    display.  Users can drag an image file from the file manager onto the tile
    to assign it as that monitor's wallpaper.  A right-click context menu
    offers \e {Clear Monitor} and \e {Monitor Settings} actions.

    \qmlproperty string MonitorWidget::monitorId
    Unique identifier for this monitor (e.g.\ \c "HDMI-1").

    \qmlproperty string MonitorWidget::monitorName
    Human-readable display name shown as the tile label.

    \qmlproperty string MonitorWidget::currentImagePath
    File path of the image currently assigned to this monitor.  Empty when
    no image is assigned.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"

Rectangle {
    id: root
    property string monitorId: ""
    property string monitorName: ""
    property string currentImagePath: ""
    
    width: 200
    height: 150
    color: dropArea.containsDrag ? Qt.darker(Style.accent, 1.5) : Style.secondaryBackground
    border.color: dropArea.containsDrag ? Style.accent : Style.border
    border.width: 2
    radius: 8
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 5
        
        Text {
            text: root.monitorName
            color: Style.text
            font.bold: true
            font.pixelSize: 12
            Layout.alignment: Qt.AlignHCenter
        }
        
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#000000"
            radius: 4
            clip: true
            
            Image {
                anchors.fill: parent
                source: root.currentImagePath
                fillMode: Image.PreserveAspectFit
                opacity: root.currentImagePath === "" ? 0.2 : 1.0
                asynchronous: true
                
                Text {
                    anchors.centerIn: parent
                    text: "DROP IMAGE HERE"
                    color: "white"
                    font.pixelSize: 10
                    visible: root.currentImagePath === ""
                }
            }
        }
    }
    
    DropArea {
        id: dropArea
        anchors.fill: parent
        onDropped: {
            if (drop.hasUrls) {
                root.currentImagePath = drop.urls[0].toString()
            }
        }
    }
    
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: {
            if (mouse.button === Qt.RightButton) {
                contextMenu.open()
            }
        }
    }
    
    Menu {
        id: contextMenu
        MenuItem { text: "Clear Monitor"; onClicked: root.currentImagePath = "" }
        MenuItem { text: "Monitor Settings..." }
    }
}

