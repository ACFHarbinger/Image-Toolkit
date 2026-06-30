/*!
    \qmltype SamplerSubtab
    \inqmlmodule ImageToolkit.Tabs.Core.Common
    \brief Image / GIF / video resampling sub-tab.

    SamplerSubtab allows up-sampling or down-sampling images, GIFs, and
    videos to a target resolution or scale factor.

    Backend object: \c mainBackend.convertTab (SamplerSubTab is routed via
    ConvertTab).

    Key slots: \c browse_input_qml(path), \c start_sampling_qml(...)
    Key properties: \c is_sampling, \c status_text, \c progress
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
            text: "Image Sampler"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        GroupBox {
            title: "Input"
            Layout.fillWidth: true
            RowLayout {
                spacing: 10
                TextField {
                    id: inputField
                    Layout.fillWidth: true
                    placeholderText: "Directory or single file to resample..."
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                    color: Style.text
                    readOnly: true
                }
                AppButton {
                    text: "Browse..."
                    onClicked: if (tab) tab.browse_sampler_input_qml(inputField.text)
                }
            }
        }

        GroupBox {
            title: "Sampling Settings"
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 10

                // Scale mode
                RowLayout {
                    spacing: 20
                    RadioButton {
                        id: factorMode
                        text: "Scale factor"
                        palette.windowText: Style.text
                        checked: true
                    }
                    RadioButton {
                        id: dimsMode
                        text: "Target dimensions"
                        palette.windowText: Style.text
                    }
                }

                // Factor row
                RowLayout {
                    visible: factorMode.checked
                    spacing: 12
                    Label { text: "Scale factor:"; color: Style.text }
                    SpinBox {
                        id: factorSpin
                        from: 1; to: 800; value: 200
                        stepSize: 10
                        textFromValue: function(v) { return (v / 100).toFixed(2) + "×" }
                    }
                }

                // Dimensions row
                RowLayout {
                    visible: dimsMode.checked
                    spacing: 12
                    Label { text: "Width:"; color: Style.text }
                    SpinBox { id: widthSpin; from: 1; to: 16384; value: 1920 }
                    Label { text: "Height:"; color: Style.text }
                    SpinBox { id: heightSpin; from: 1; to: 16384; value: 1080 }
                }

                // Algorithm
                RowLayout {
                    spacing: 12
                    Label { text: "Algorithm:"; color: Style.text }
                    ComboBox {
                        id: algoCombo
                        model: ["LANCZOS4", "INTER_CUBIC", "INTER_LINEAR", "INTER_AREA", "NEAREST"]
                    }
                }
            }
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: tab ? tab.is_sampling : false
            value: tab ? tab.sampler_progress / 100.0 : 0
        }

        Text {
            text: tab ? tab.sampler_status : "Ready."
            color: Style.mutedText
        }

        AppButton {
            text: (tab && tab.is_sampling) ? "Cancel" : "Start Resampling"
            Layout.fillWidth: true
            background: Rectangle {
                color: (tab && tab.is_sampling) ? "#e74c3c" : Style.accent
                radius: Style.borderRadius
            }
            onClicked: {
                if (!tab) return
                if (tab.is_sampling)
                    tab.cancel_sampling_qml()
                else
                    tab.start_sampling_qml(
                        inputField.text,
                        factorMode.checked ? factorSpin.value / 100.0 : -1,
                        dimsMode.checked ? widthSpin.value : -1,
                        dimsMode.checked ? heightSpin.value : -1,
                        algoCombo.currentText
                    )
            }
        }

        Item { Layout.fillHeight: true }
    }
}
