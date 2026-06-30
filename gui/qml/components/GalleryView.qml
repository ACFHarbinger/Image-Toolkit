/*!
    \qmltype GalleryView
    \inqmlmodule ImageToolkit.Components
    \brief Scrollable image grid backed by a ListModel.

    GalleryView is a \l GridView with 160 × 180 px cells.  Each delegate is
    an \l ImageCard whose \c imageSource is set from \c model.path and whose
    \c fileName is set from \c model.name.

    \qmlproperty ListModel GalleryView::model
    The data model.  Each element must expose \c path and \c name roles.

    \qmlsignal GalleryView::itemClicked(string path)
    Emitted when a thumbnail is single-clicked.

    \qmlsignal GalleryView::itemDoubleClicked(string path)
    Emitted when a thumbnail is double-clicked, typically to open the preview
    window.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import "../"

GridView {
    id: grid
    signal itemClicked(string path)
    signal itemDoubleClicked(string path)
    cellWidth: 160
    cellHeight: 180
    delegate: ImageCard {
        imageSource: model.path
        fileName: model.name
        onClicked: grid.itemClicked(model.path)
        onDoubleClicked: grid.itemDoubleClicked(model.path)
    }
    model: ListModel {}
}

