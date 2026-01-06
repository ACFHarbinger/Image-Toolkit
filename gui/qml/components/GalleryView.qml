import QtQuick 2.15
import QtQuick.Controls 2.15
import "../"

GridView {
    id: grid
    cellWidth: 160
    cellHeight: 180
    delegate: ImageCard {
        imageSource: model.path
        fileName: model.name
    }
    model: ListModel {}
}

