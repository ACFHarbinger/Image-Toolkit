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
                    text: (mainBackend && mainBackend.convertTab) ? mainBackend.convertTab.input_path_text : "" // Need to expose this
                }
                AppButton { 
                    text: "Browse"
                    onClicked: mainBackend.convertTab.browse_directory_and_scan()
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
            onClicked: mainBackend.convertTab.start_conversion_worker(false)
        }
        
        Item { Layout.fillHeight: true }
    }
}

