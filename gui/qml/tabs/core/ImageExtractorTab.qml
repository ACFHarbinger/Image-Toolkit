import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtMultimedia 5.15
import "../../components"
import "../../"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Text {
            text: "Video Frame Extractor"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            // --- Video Player Area ---
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Rectangle {
                    id: playerContainer
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "black"
                    
                    Text {
                        anchors.centerIn: parent
                        text: "Video Output Placeholder\n(Requires QtMultimedia)"
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                    }
                    
                    // VideoOutput { anchors.fill: parent; source: mediaPlayer }
                }

                // --- Controls ---
                RowLayout {
                    Layout.fillWidth: true
                    AppButton { text: "▶"; Layout.preferredWidth: 40 }
                    Slider { Layout.fillWidth: true; from: 0; to: 100; value: 30 }
                    Text { text: "00:00 / 00:00"; color: Style.text }
                }

                RowLayout {
                    Layout.fillWidth: true
                    AppButton { text: "Extract Current Frame"; Layout.fillWidth: true }
                    AppButton { text: "Batch Extract (Auto)"; Layout.fillWidth: true }
                }
            }

            // --- Extracted Frames Sidebar ---
            Rectangle {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                color: Style.secondaryBackground
                radius: Style.borderRadius
                border.color: Style.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    
                    Text { text: "Extracted Frames"; color: Style.text; font.bold: true }

                    GalleryView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: ListModel {}
                    }

                    AppButton {
                        text: "Export Selected"
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                    }
                }
            }
        }
    }
}
