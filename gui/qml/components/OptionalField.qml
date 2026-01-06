import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"

ColumnLayout {
    id: root
    property string title: ""
    property bool expanded: false
    property alias content: contentLoader.sourceComponent
    
    Layout.fillWidth: true
    spacing: 0

    // Header
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 40
        color: headerMouseArea.containsMouse ? Style.secondaryBackground : "transparent"
        border.color: Style.border
        border.width: 1
        radius: 4

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 10

            Text {
                text: root.expanded ? "➖" : "➕"
                color: Style.text
                font.pixelSize: 14
            }

            Text {
                text: root.title
                color: Style.text
                font.bold: true
                Layout.fillWidth: true
            }
        }

        MouseArea {
            id: headerMouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.expanded = !root.expanded
        }
    }

    // Content
    Item {
        id: contentContainer
        Layout.fillWidth: true
        Layout.preferredHeight: root.expanded ? contentLoader.height + 10 : 0
        clip: true
        visible: root.expanded

        Behavior on Layout.preferredHeight {
            NumberAnimation { duration: 200; easing.type: Easing.InOutQuad }
        }

        ColumnLayout {
            id: contentLoaderLayout
            anchors.top: parent.top
            anchors.topMargin: 5
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 0
            
            Loader {
                id: contentLoader
                Layout.fillWidth: true
            }
        }
    }
}

