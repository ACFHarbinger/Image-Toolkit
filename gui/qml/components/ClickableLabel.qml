import QtQuick 2.15
import "../"

Text {
    id: root
    property string path: ""
    signal pathClicked(string path)
    
    color: Style.text
    font.pixelSize: 14
    
    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.pathClicked(root.path)
    }
}

