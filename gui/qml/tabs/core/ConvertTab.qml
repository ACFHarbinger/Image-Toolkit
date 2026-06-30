/*!
    \qmltype ConvertTab
    \inqmlmodule ImageToolkit.Tabs.Core
    \brief Image format conversion tab.

    ConvertTab lets users pick an input folder, select an output format
    (\c png, \c jpg, or \c webp), optionally specify an output directory and
    whether to delete the originals, then start a background conversion worker.

    The tab binds to \c mainBackend.convertTab.  Key backend calls:
    \list
      \li \c browse_directory_and_scan_qml() — opens a folder picker
      \li \c start_conversion_worker_qml(inputPath, format, outputDir, deleteOriginal)
    \endlist

    The input path label updates when the backend emits
    \c onQml_input_path_changed.
*/
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

