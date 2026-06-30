/*!
    \qmltype OptionalField
    \inqmlmodule ImageToolkit.Components
    \brief Collapsible section with animated height transition.

    OptionalField wraps arbitrary content in a \l ColumnLayout with a
    clickable header row.  Clicking the header toggles the \l expanded state.
    The height change is animated over 200 ms using an \c InOutQuad easing.
    The header icon shows ➕ when collapsed and ➖ when expanded.

    \qmlproperty string OptionalField::title
    Text shown in the header row.

    \qmlproperty bool OptionalField::expanded
    Whether the content area is currently visible.  Defaults to \c false.

    \qmlproperty Component OptionalField::content
    Alias to the inner \l Loader's \c sourceComponent.  Assign a \l Component
    to populate the collapsible body.
*/
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

