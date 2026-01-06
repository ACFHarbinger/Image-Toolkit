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
            text: "Image / Video Converter"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        // --- Configuration Section ---
        GroupBox {
            title: "Conversion Settings"
            Layout.fillWidth: true
            
            GridLayout {
                anchors.fill: parent
                columns: 3
                rowSpacing: 10
                columnSpacing: 15

                Label { text: "Input Path:"; color: Style.text }
                TextField {
                    id: inputPath
                    Layout.fillWidth: true
                    placeholderText: "Select directory or files..."
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                    color: Style.text
                }
                AppButton { text: "Browse"; Layout.preferredWidth: 80 }

                Label { text: "Output Format:"; color: Style.text }
                ComboBox {
                    model: ["png", "jpg", "webp", "gif", "mp4"]
                    Layout.fillWidth: true
                }
                Item {} // Spacer

                Label { text: "Output Path:"; color: Style.text }
                TextField {
                    id: outputPath
                    Layout.fillWidth: true
                    placeholderText: "Default is input directory"
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                    color: Style.text
                }
                AppButton { text: "Browse"; Layout.preferredWidth: 80 }
            }
        }

        // --- Gallery Section ---
        Text { text: "Files Found:"; color: Style.text; font.bold: true }
        
        GalleryView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // Model will be connected from Python
            model: ListModel {
                ListElement { name: "sample1.png"; path: "/tmp/sample1.png"; selected: false }
                ListElement { name: "sample2.jpg"; path: "/tmp/sample2.jpg"; selected: false }
            }
        }

        // --- Action Buttons ---
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 10

            AppButton { text: "Add All Formats"; Layout.preferredWidth: 150 }
            AppButton { text: "Convert Selected"; Layout.preferredWidth: 150 }
        }

        ProgressBar {
            Layout.fillWidth: true
            value: 0
            background: Rectangle { color: Style.secondaryBackground; radius: 4; height: 8 }
            contentItem: Item {
                Rectangle {
                    width: parent.visualPosition * parent.width
                    height: 8
                    radius: 4
                    color: Style.accent
                }
            }
        }
    }
}
