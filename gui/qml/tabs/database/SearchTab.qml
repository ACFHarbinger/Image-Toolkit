import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        // --- Top: Search Filters ---
        GroupBox {
            title: "Search Filters"
            Layout.fillWidth: true
            
            ColumnLayout {
                anchors.fill: parent
                spacing: 10

                RowLayout {
                    spacing: 15
                    Text { text: "Keywords:"; color: Style.text; font.bold: true }
                    TextField {
                        id: keywordSearch
                        placeholderText: "Search by filename or note..."
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                    }
                }

                RowLayout {
                    spacing: 20
                    
                    // Tags filter
                    ColumnLayout {
                        Text { text: "Tags:"; color: Style.text; font.bold: true }
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 100
                            clip: true
                            Flow {
                                width: parent.width
                                spacing: 8
                                Repeater {
                                    model: ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"]
                                    CheckBox {
                                        text: modelData
                                        palette.windowText: Style.text
                                    }
                                }
                            }
                        }
                    }

                    // Formats filter
                    ColumnLayout {
                        Text { text: "Formats:"; color: Style.text; font.bold: true }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: ["jpg", "png", "webp", "gif", "mp4"]
                                CheckBox {
                                    text: modelData
                                    palette.windowText: Style.text
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 15
                    AppButton {
                        text: "Clear Filters"
                        Layout.preferredWidth: 120
                        onClicked: if (mainBackend && mainBackend.searchTab) mainBackend.searchTab.clear_filters()
                    }
                    Item { Layout.fillWidth: true }
                    AppButton {
                        text: "Search Database"
                        Layout.preferredWidth: 180
                        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                        onClicked: if (mainBackend && mainBackend.searchTab) mainBackend.searchTab.execute_search()
                    }
                }
            }
        }

        // --- Middle: Results Gallery ---
        GroupBox {
            title: "Search Results"
            Layout.fillWidth: true
            Layout.fillHeight: true
            
            ColumnLayout {
                anchors.fill: parent
                
                GalleryView {
                    id: resultsGallery
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {
                        // Populated from Python
                    }
                }

                // Selection Actions
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Text { text: "Selection Actions:"; color: Style.text; font.bold: true }
                    AppButton { text: "Select All"; Layout.preferredWidth: 80 }
                    AppButton { text: "Deselect All"; Layout.preferredWidth: 80 }
                    Item { Layout.fillWidth: true }
                    ComboBox {
                        model: ["Send to Scan Tab", "Send to Merge Tab", "Send to Delete Tab", "Send to Wallpaper Tab"]
                        Layout.preferredWidth: 200
                    }
                    AppButton { text: "Execute"; Layout.preferredWidth: 80 }
                }
            }
        }
    }
}
