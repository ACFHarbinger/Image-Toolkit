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

                    Layout.fillWidth: true
                    ColumnLayout {
                        Label { text: "Direction:"; color: Style.text }
                        ComboBox {
                            id: directionCombo
                            Layout.fillWidth: true
                            model: ["horizontal", "vertical", "grid", "panorama", "stitch", "sequential", "gif"]
                        }
                    }

                GroupBox {
                    title: "Parameters"
                    Layout.fillWidth: true
                    GridLayout {
                        columns: 2
                        Label { text: "Spacing:"; color: Style.text }
                        SpinBox { id: spacingSpin; from: 0; to: 1000; value: 10 }
                        
                        Label { text: "Duration (ms):"; color: Style.text }
                        SpinBox { id: durationSpin; from: 10; to: 10000; value: 500; stepSize: 50 }

                        Label { text: "Alignment:"; color: Style.text }
                        ComboBox {
                            id: alignCombo
                            Layout.fillWidth: true
                            model: ["Default (Top/Center)", "Align Top/Left", "Align Bottom/Right", "Center", "Scaled (Grow Smallest)", "Squish (Shrink Largest)"]
                        }
                    }
                }

                AppButton {
                    text: "Generate Preview"
                    Layout.fillWidth: true
                }

                AppButton {
                    text: "Run Merge"
                    Layout.fillWidth: true
                    background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                    onClicked: {
                        if (mainBackend && mainBackend.mergeTab) {
                            mainBackend.mergeTab.start_merge_qml(
                                directionCombo.currentText,
                                spacingSpin.value,
                                durationSpin.value,
                                alignCombo.currentText
                            )
                        }
                    }
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
