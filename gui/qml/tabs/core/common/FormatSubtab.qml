/*!
    \qmltype FormatSubtab
    \inqmlmodule ImageToolkit.Tabs.Core.Common
    \brief Image format conversion sub-tab.

    FormatSubtab lets the user select an input directory, choose an output
    format and optional output directory, then runs a batch conversion worker.

    Backend object: \c mainBackend.convertTab (FormatSubTab is the active
    inner tab).

    \qmlsignal FormatSubtab::qml_input_path_changed(string path)
    Emitted when the user browses to a new input directory.

    Key slots:
    \list
      \li \c browse_directory_and_scan_qml(currentPath)
      \li \c start_conversion_worker_qml(inputPath, outputFormat, outputDir, deleteOriginal)
    \endlist
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../../components"
import "../../../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.convertTab ? mainBackend.convertTab : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Text {
            text: "Format Conversion"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        // Input path
        GroupBox {
            title: "Convert Targets"
            Layout.fillWidth: true
            RowLayout {
                spacing: 10
                Layout.fillWidth: true
                TextField {
                    id: inputPathField
                    Layout.fillWidth: true
                    placeholderText: "Path to directory containing images for conversion..."
                    text: tab ? tab.input_path : ""
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                    color: Style.text
                    readOnly: true
                }
                AppButton {
                    text: "Browse..."
                    Layout.preferredWidth: 90
                    onClicked: if (tab) tab.browse_directory_and_scan_qml(inputPathField.text)
                }
            }
        }

        // Convert settings
        GroupBox {
            title: "Convert Settings"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                columnSpacing: 16
                rowSpacing: 8
                Layout.fillWidth: true

                Label { text: "Output Format:"; color: Style.text }
                ComboBox {
                    id: outputFormatCombo
                    model: ["jpg", "jpeg", "png", "webp", "bmp", "tiff", "gif", "avif"]
                    Layout.preferredWidth: 160
                }

                Label { text: "Output Directory:"; color: Style.text }
                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        id: outputDirField
                        Layout.fillWidth: true
                        placeholderText: "(Optional) Leave blank to convert in-place"
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                    }
                    AppButton {
                        text: "Browse..."
                        Layout.preferredWidth: 90
                    }
                }

                CheckBox {
                    id: deleteOriginalCheck
                    text: "Delete originals after conversion"
                    palette.windowText: Style.text
                    Layout.columnSpan: 2
                }
            }
        }

        // Status + progress
        ProgressBar {
            id: progressBar
            Layout.fillWidth: true
            visible: tab ? tab.is_converting : false
            value: tab ? tab.progress / 100.0 : 0
        }

        Text {
            text: tab ? tab.status_text : "Ready."
            color: Style.mutedText
        }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            AppButton {
                text: (tab && tab.is_converting) ? "Cancel" : "Start Conversion"
                Layout.fillWidth: true
                background: Rectangle {
                    color: (tab && tab.is_converting) ? "#e74c3c" : Style.accent
                    radius: Style.borderRadius
                }
                enabled: tab ? (inputPathField.text !== "" || tab.is_converting) : false
                onClicked: {
                    if (!tab) return
                    if (tab.is_converting)
                        tab.cancel_conversion_qml()
                    else
                        tab.start_conversion_worker_qml(
                            inputPathField.text,
                            outputFormatCombo.currentText,
                            outputDirField.text,
                            deleteOriginalCheck.checked
                        )
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
