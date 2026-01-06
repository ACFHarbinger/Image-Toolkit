import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"

Rectangle {
    id: root
    property string imageSource: ""
    property string fileName: ""
    property string path: ""

    width: 350
    height: 70
    color: Style.secondaryBackground
    border.color: Style.border
    border.width: 1
    radius: 4

    RowLayout {
        anchors.fill: parent
        anchors.margins: 5
        spacing: 12

        Image {
            Layout.preferredWidth: 80
            Layout.preferredHeight: 60
            source: root.imageSource
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            
            Rectangle {
                anchors.fill: parent
                color: "transparent"
                border.color: Style.border
                border.width: 1
                radius: 4
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            
            Text {
                text: root.fileName
                color: Style.text
                font.pixelSize: 12
                font.bold: true
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            
            Text {
                text: root.path
                color: Style.text
                opacity: 0.5
                font.pixelSize: 10
                Layout.fillWidth: true
                elide: Text.ElideMiddle
            }
        }
    }
    
    ToolTip {
        id: tooltip
        text: root.path
    }
    
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onEntered: tooltip.visible = true
        onExited: tooltip.visible = false
    }
}

