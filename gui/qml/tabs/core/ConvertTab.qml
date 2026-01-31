import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../.."

Item {
    id: root
    Layout.fillWidth: true
    Layout.fillHeight: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 20

        Text {
            text: "Image Converter"
            color: Style.text
            font.pixelSize: 24
            font.bold: true
        }

        GridLayout {
            columns: 2
            Layout.fillWidth: true
            
            Label { text: "Input Path:"; color: Style.text }
            RowLayout {
                TextField { 
                    id: inputPath
                    Layout.fillWidth: true
                    color: Style.text
                    placeholderText: "Select input folder..."
                }
                Connections {
                    target: (mainBackend && mainBackend.convertTab) ? mainBackend.convertTab : null
                    function onQml_input_path_changed(newPath) {
                        inputPath.text = newPath
                    }
                }
                AppButton { 
                    text: "Browse"
                    onClicked: {
                        if (mainBackend && mainBackend.convertTab) {
                            mainBackend.convertTab.browse_directory_and_scan_qml(inputPath.text)
                        }
                    }
                }
            }

            Label { text: "Output Format:"; color: Style.text }
            ComboBox { 
                id: outputFormatCombo
                model: ["png", "jpg", "webp"]
                Layout.fillWidth: true 
            }
        }

        AppButton {
            text: "Start Conversion"
            Layout.alignment: Qt.AlignRight
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
            onClicked: {
                 if (mainBackend && mainBackend.convertTab) {
                     mainBackend.convertTab.start_conversion_worker_qml(
                         inputPath.text,
                         outputFormatCombo.currentText,
                         "", // Output dir optional
                         false // Delete original
                     )
                 }
            }
        }
        
        Item { Layout.fillHeight: true }
    }
}

