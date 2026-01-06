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
            text: "Image Merger"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 20

            // --- Configuration Column ---
            ColumnLayout {
                Layout.preferredWidth: 300
                spacing: 10

                GroupBox {
                    title: "Merge Mode"
                    Layout.fillWidth: true
                    ColumnLayout {
                        RadioButton { text: "Grid (Vertical/Horizontal)"; checked: true; palette.windowText: Style.text }
                        RadioButton { text: "GIF / Video Slideshow"; palette.windowText: Style.text }
                    }
                }

                GroupBox {
                    title: "Parameters"
                    Layout.fillWidth: true
                    GridLayout {
                        columns: 2
                        Label { text: "Grid Columns:"; color: Style.text }
                        SpinBox { from: 1; to: 20; value: 2 }
                        
                        Label { text: "Spacing:"; color: Style.text }
                        SpinBox { from: 0; to: 100; value: 5 }
                        
                        Label { text: "Background Color:"; color: Style.text }
                        Rectangle {
                            width: 30; height: 30
                            color: "black"; border.color: Style.border
                            MouseArea { anchors.fill: parent; onClicked: console.log("Open color picker") }
                        }
                    }
                }

                AppButton {
                    text: "Generate Preview"
                    Layout.fillWidth: true
                }

                AppButton {
                    text: "Save Result"
                    Layout.fillWidth: true
                    background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                }
            }

            // --- Preview Column ---
            ColumnLayout {
                Layout.fillWidth: true
                
                Text { text: "Selected Images:"; color: Style.text; font.bold: true }
                
                GalleryView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {} 
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 200
                    color: Style.secondaryBackground
                    border.color: Style.border
                    Text {
                        anchors.centerIn: parent
                        text: "Preview Area"
                        color: Style.mutedText
                    }
                }
            }
        }
    }
}
