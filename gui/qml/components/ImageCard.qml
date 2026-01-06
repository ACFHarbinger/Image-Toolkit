import QtQuick 2.15
import QtQuick.Controls 2.15
import "../"

Item {
    id: root
    property string imageSource: ""
    property bool isSelected: false
    property string fileName: ""
    
    width: 150
    height: 180

    Rectangle {
        anchors.fill: parent
        color: root.isSelected ? Style.accent : "transparent"
        border.color: Style.border
        border.width: 1
        radius: Style.borderRadius
        
        opacity: root.isSelected ? 0.3 : 1.0

        Column {
            anchors.fill: parent
            anchors.margins: 5
            spacing: 5

            Image {
                width: parent.width
                height: parent.width
                source: root.imageSource
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    border.color: Style.accent
                    border.width: root.isSelected ? 2 : 0
                }
            }

            Text {
                width: parent.width
                text: root.fileName
                color: Style.text
                elide: Text.ElideMiddle
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 10
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.isSelected = !root.isSelected
    }
}
