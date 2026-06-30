/*!
    \qmltype ClickableLabel
    \inqmlmodule ImageToolkit.Components
    \brief Text label that emits pathClicked when the user clicks it.

    ClickableLabel wraps a \l Text element with a \l MouseArea and a pointer
    cursor.  It is used throughout the gallery views to make file-path labels
    interactive.

    \qmlproperty string ClickableLabel::path
    The file-system path associated with this label.  Emitted verbatim via
    \l pathClicked.

    \qmlsignal ClickableLabel::pathClicked(string path)
    Emitted when the user clicks the label.  \a path is the value of the
    \l path property at the time of the click.
*/
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

