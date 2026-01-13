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

