import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property alias model: gridView.model
    
    GridView {
        id: gridView
        anchors.fill: parent
        cellWidth: 160
        cellHeight: 190
        clip: true
        
        delegate: ImageCard {
            imageSource: model.path ? "file://" + model.path : ""
            fileName: model.name || ""
            isSelected: model.selected || false
        }
        
        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
        }
    }
}
