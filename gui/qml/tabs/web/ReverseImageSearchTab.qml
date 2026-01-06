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

        Text {
            text: "Reverse Image Search"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            spacing: 15
            Label { text: "Scan Directory:"; color: Style.text }
            TextField {
                id: scanDir
                Layout.fillWidth: true
                placeholderText: "Select directory to scan for source images..."
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                color: Style.text
            }
            AppButton { text: "Browse"; Layout.preferredWidth: 80 }
            AppButton { text: "Scan"; Layout.preferredWidth: 80 }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Local Gallery
            ColumnLayout {
                Layout.preferredWidth: parent.width * 0.4
                Layout.fillHeight: true
                Text { text: "1. Select Source Image:"; color: Style.text; font.bold: true }
                GalleryView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {
                        // Populated from Python
                    }
                }
            }

            Rectangle { width: 1; Layout.fillHeight: true; color: Style.border }

            // Results Area
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10
                Text { text: "2. Search Options & Results:"; color: Style.text; font.bold: true }
                
                GroupBox {
                    title: "Search Configuration"
                    Layout.fillWidth: true
                    GridLayout {
                        columns: 4
                        columnSpacing: 10
                        CheckBox { text: "Use Proxies"; palette.windowText: Style.text }
                        CheckBox { text: "Exact Match Only"; palette.windowText: Style.text }
                        Label { text: "Engine:"; color: Style.text }
                        ComboBox { model: ["Google", "Bing", "SauceNAO", "Yandex"] }
                    }
                }

                AppButton {
                    text: "Start Reverse Search"
                    Layout.fillWidth: true
                    background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    radius: Style.borderRadius
                    border.color: Style.border
                    
                    Text {
                        anchors.centerIn: parent
                        text: "Search results will appear here."
                        color: Style.mutedText
                    }
                }
            }
        }
    }
}
