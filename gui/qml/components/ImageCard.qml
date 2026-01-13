import QtQuick 2.15
import "../"

Rectangle {
    id: root
    property string imageSource: ""
    property string fileName: ""
    signal clicked()
    signal doubleClicked()
    
    width: 150
    height: 170
    color: Style.secondaryBackground
    border.color: Style.border
    radius: Style.borderRadius

    Column {
        anchors.fill: parent
        anchors.margins: 5
        spacing: 5

        Image {
            width: parent.width
            height: parent.width
            source: root.imageSource
            fillMode: Image.PreserveAspectFit
        }

        Text {
            width: parent.width
            text: root.fileName
            color: Style.text
            elide: Text.ElideMiddle
            horizontalAlignment: Text.AlignHCenter
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.clicked()
        onDoubleClicked: root.doubleClicked()
        hoverEnabled: true
        onEntered: root.border.color = Style.accent
        onExited: root.border.color = Style.border
    }
}

