/*!
    \qmltype DraggableLabel
    \inqmlmodule ImageToolkit.Components
    \brief Thumbnail label that supports drag-and-drop transfer of file paths.

    DraggableLabel displays a square thumbnail at a configurable \l size.
    A long-press or mouse-drag emits \l dragStarted so the host can start a
    \c Drag operation.  Single and double clicks emit \l pathClicked and
    \l pathDoubleClicked respectively.  A right-click emits \l pathRightClicked.

    \qmlproperty string DraggableLabel::filePath
    File-system path of the image this label represents.

    \qmlproperty int DraggableLabel::size
    Side length (width and height) of the thumbnail square in pixels.
    Defaults to \c 120.

    \qmlsignal DraggableLabel::pathClicked(string path)
    Emitted on single left-click.

    \qmlsignal DraggableLabel::pathDoubleClicked(string path)
    Emitted on double-click.

    \qmlsignal DraggableLabel::pathRightClicked(point globalPos, string path)
    Emitted on right-click.  \a globalPos is in screen coordinates suitable
    for positioning a \l Menu.

    \qmlsignal DraggableLabel::dragStarted(string path)
    Emitted when a drag gesture exceeds the drag threshold.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import "../"

Rectangle {
    id: root

    property string filePath: ""
    property int size: 120

    signal pathClicked(string path)
    signal pathDoubleClicked(string path)
    signal pathRightClicked(point globalPos, string path)
    signal dragStarted(string path)

    width: size
    height: size
    color: Style.secondaryBackground
    border.color: dragHandler.active ? Style.accent : Style.border
    border.width: dragHandler.active ? 2 : 1
    radius: 4

    Image {
        anchors.fill: parent
        anchors.margins: 2
        source: root.filePath ? "file://" + root.filePath : ""
        fillMode: Image.PreserveAspectFit
        asynchronous: true

        Text {
            anchors.centerIn: parent
            text: "Loading…"
            color: Style.mutedText
            font.pixelSize: 10
            visible: parent.status === Image.Loading
        }
    }

    Text {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 3
        text: root.filePath ? root.filePath.split("/").pop() : ""
        color: Style.text
        font.pixelSize: 9
        elide: Text.ElideMiddle
        width: root.width - 4
        horizontalAlignment: Text.AlignHCenter
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor

        onClicked: {
            if (mouse.button === Qt.RightButton)
                root.pathRightClicked(mapToGlobal(mouse.x, mouse.y), root.filePath)
            else
                root.pathClicked(root.filePath)
        }
        onDoubleClicked: root.pathDoubleClicked(root.filePath)
    }

    DragHandler {
        id: dragHandler
        onActiveChanged: if (active) root.dragStarted(root.filePath)
    }

    Drag.active: dragHandler.active
    Drag.mimeData: { "text/uri-list": "file://" + root.filePath }
    Drag.supportedActions: Qt.CopyAction
}
