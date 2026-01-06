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

        // --- Top: Search and Scan Controls ---
        RowLayout {
            Layout.fillWidth: true
            spacing: 15
            
            Text { text: "Scan Path:"; color: Style.text; font.bold: true }
            TextField {
                id: scanPathField
                placeholderText: "Enter directory to scan..."
                Layout.fillWidth: true
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                color: Style.text
            }
            AppButton { text: "Browse"; Layout.preferredWidth: 80 }
            AppButton { text: "Start Scan"; Layout.preferredWidth: 100 }
            AppButton { text: "Stop"; Layout.preferredWidth: 60 }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 15
            TextField {
                placeholderText: "Quick Filter..."
                Layout.fillWidth: true
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                color: Style.text
            }
            CheckBox { text: "Recursive"; palette.windowText: Style.text }
            CheckBox { text: "Skip Existing"; palette.windowText: Style.text }
        }

        // --- Middle: Found Images Gallery ---
        GroupBox {
            title: "Found Images"
            Layout.fillWidth: true
            Layout.fillHeight: true
            
            ColumnLayout {
                anchors.fill: parent
                
                GalleryView {
                    id: foundGallery
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {
                        // Populated from Python
                    }
                }

                // Pagination
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10
                    AppButton { text: "Prev"; Layout.preferredWidth: 60 }
                    Text { text: "Page 1 of 1"; color: Style.text }
                    AppButton { text: "Next"; Layout.preferredWidth: 60 }
                    ComboBox { model: ["50", "100", "500"]; Layout.preferredWidth: 80 }
                }
            }
        }

        // --- Bottom Area: Selected and Tagging ---
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: parent.height * 0.35
            spacing: 20

            // Selected Images
            GroupBox {
                title: "Selected Images"
                Layout.fillWidth: true
                Layout.fillHeight: true
                
                GalleryView {
                    anchors.fill: parent
                    model: ListModel {
                        // Populated from Python
                    }
                }
            }

            // Batch Tagging Panel
            GroupBox {
                title: "Batch Database Actions"
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    Text { text: "Assign Tags:"; color: Style.text; font.bold: true }
                    
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        Flow {
                            width: parent.width
                            spacing: 10
                            Repeater {
                                model: ["Tag1", "Tag2", "Tag3", "Tag4"]
                                CheckBox {
                                    text: modelData
                                    palette.windowText: Style.text
                                }
                            }
                        }
                    }

                    ComboBox {
                        id: groupCombo
                        Layout.fillWidth: true
                        model: ["Default Group"]
                        // To be populated
                    }
                    
                    ComboBox {
                        id: subgroupCombo
                        Layout.fillWidth: true
                        model: ["Default Subgroup"]
                        // To be populated
                    }

                    AppButton {
                        text: "Add to Database"
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                    }
                }
            }
        }
    }
}
