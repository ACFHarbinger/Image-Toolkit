/*!
    \qmltype DoubleClickableLabel
    \inqmlmodule ImageToolkit.Components
    \brief Thumbnail label that opens a full-image viewer on double-click.

    DoubleClickableLabel wraps \l ImageCard with an extra double-click signal.
    Single-click emits \l pathClicked; double-click emits \l pathDoubleClicked
    and, if \l openPreviewOnDoubleClick is \c true, requests the main preview
    window via \c mainBackend.open_preview().

    \qmlproperty string DoubleClickableLabel::path
    File-system path associated with this label.

    \qmlproperty string DoubleClickableLabel::imageSource
    Image URL passed to the inner \l ImageCard thumbnail.

    \qmlproperty bool DoubleClickableLabel::openPreviewOnDoubleClick
    When \c true (default) a double-click calls \c mainBackend.open_preview(path).

    \qmlsignal DoubleClickableLabel::pathClicked(string path)
    Emitted on single click.

    \qmlsignal DoubleClickableLabel::pathDoubleClicked(string path)
    Emitted on double-click (before the optional preview call).
*/
import QtQuick 2.15
import "../"

Item {
    id: root

    property string path: ""
    property string imageSource: ""
    property bool openPreviewOnDoubleClick: true

    signal pathClicked(string path)
    signal pathDoubleClicked(string path)

    implicitWidth: 150
    implicitHeight: 170

    ImageCard {
        anchors.fill: parent
        imageSource: root.imageSource
        fileName: root.path ? root.path.split("/").pop() : ""
        onClicked: root.pathClicked(root.path)
        onDoubleClicked: {
            root.pathDoubleClicked(root.path)
            if (root.openPreviewOnDoubleClick && mainBackend)
                mainBackend.open_preview(root.path)
        }
    }
}
