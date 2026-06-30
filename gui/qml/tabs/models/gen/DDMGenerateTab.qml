/*!
    \qmltype DDMGenerateTab
    \inqmlmodule ImageToolkit.Tabs.Models.Gen
    \brief Diffusion model (SD 3.5 / DDM) generation sub-tab.

    DDMGenerateTab exposes controls for running text-to-image generation with
    Stable Diffusion 3.5 or similar diffusion model wrappers.  It supports
    optional ControlNet conditioning.

    Backend object: \c mainBackend.ddmTab

    Key slots: \c start_generation(), \c cancel_generation()
    Key properties: \c is_generating, \c status_text, \c log_output,
    \c model, \c prompt, \c width, \c height, \c steps
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../components"
import "../../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.ddmTab ? mainBackend.ddmTab : null

    ScrollView {
        anchors.fill: parent

        ColumnLayout {
            width: parent.parent.width
            anchors.margins: 20
            spacing: 15

            Text {
                text: "Diffusion Model Generation"
                color: Style.text
                font.pixelSize: 22
                font.bold: true
            }

            GroupBox {
                title: "Base Model"
                Layout.fillWidth: true

                FormLayout {
                    Label { text: "Model:"; Layout.alignment: Qt.AlignRight; color: Style.text }
                    ComboBox {
                        id: modelCombo
                        Layout.fillWidth: true
                        editable: true
                        model: [
                            "models/sd3.5_large.safetensors",
                            "models/sd3.5_large_turbo.safetensors",
                            "models/sd3.5_medium.safetensors",
                            "models/sd3_medium.safetensors"
                        ]
                        onCurrentTextChanged: if (tab) tab.model = currentText
                    }

                    Label { text: "Prompt:"; Layout.alignment: Qt.AlignRight; color: Style.text }
                    TextField {
                        id: promptField
                        Layout.fillWidth: true
                        text: tab ? tab.prompt : "cute wallpaper art of a cat"
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                        onTextChanged: if (tab) tab.prompt = text
                    }

                    Label { text: "Output Postfix:"; Layout.alignment: Qt.AlignRight; color: Style.text }
                    TextField {
                        id: postfixField
                        Layout.fillWidth: true
                        placeholderText: "(optional)"
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                        onTextChanged: if (tab) tab.postfix = text
                    }
                }
            }

            GroupBox {
                title: "Dimensions & Steps"
                Layout.fillWidth: true

                GridLayout {
                    columns: 4
                    columnSpacing: 12
                    rowSpacing: 8

                    Label { text: "Width:"; color: Style.text }
                    SpinBox { id: widthSpin; from: 256; to: 4096; value: tab ? tab.width : 1024; stepSize: 64
                              onValueChanged: if (tab) tab.width = value }
                    Label { text: "Height:"; color: Style.text }
                    SpinBox { id: heightSpin; from: 256; to: 4096; value: tab ? tab.height : 1024; stepSize: 64
                              onValueChanged: if (tab) tab.height = value }

                    Label { text: "Steps:"; color: Style.text }
                    SpinBox { id: stepsSpin; from: 1; to: 200; value: tab ? tab.steps : 28
                              onValueChanged: if (tab) tab.steps = value }
                    CheckBox {
                        text: "Skip Layer Cfg (SD3.5-M)"
                        palette.windowText: Style.text
                        Layout.columnSpan: 2
                        onCheckedChanged: if (tab) tab.skip_layer_cfg = checked
                    }
                }
            }

            GroupBox {
                title: "ControlNet (optional)"
                Layout.fillWidth: true

                FormLayout {
                    Label { text: "ControlNet Model:"; Layout.alignment: Qt.AlignRight; color: Style.text }
                    ComboBox {
                        id: cnModelCombo
                        Layout.fillWidth: true
                        editable: true
                        model: [
                            "None",
                            "models/sd3.5_large_controlnet_blur.safetensors",
                            "models/sd3.5_large_controlnet_canny.safetensors",
                            "models/sd3.5_large_controlnet_depth.safetensors"
                        ]
                        onCurrentTextChanged: if (tab) tab.controlnet_ckpt = currentText
                    }

                    Label { text: "Cond. Image:"; Layout.alignment: Qt.AlignRight; color: Style.text }
                    TextField {
                        Layout.fillWidth: true
                        text: tab ? tab.controlnet_cond_image : "inputs/canny.png"
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                        onTextChanged: if (tab) tab.controlnet_cond_image = text
                    }
                }
            }

            // Status + progress
            Text {
                text: tab ? tab.status_text : "Ready."
                color: Style.mutedText
            }

            Rectangle {
                Layout.fillWidth: true
                height: 120
                color: "black"
                radius: Style.borderRadius
                border.color: Style.border
                visible: tab ? (tab.log_output !== "") : false

                ScrollView {
                    anchors.fill: parent
                    TextArea {
                        readOnly: true
                        text: tab ? tab.log_output : ""
                        color: "#00ff00"
                        font.family: "Monospace"
                        font.pixelSize: 11
                        background: null
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                AppButton {
                    text: (tab && tab.is_generating) ? "Cancel" : "Generate"
                    Layout.fillWidth: true
                    background: Rectangle {
                        color: (tab && tab.is_generating) ? "#e74c3c" : Style.accent
                        radius: Style.borderRadius
                    }
                    onClicked: {
                        if (!tab) return
                        if (tab.is_generating) tab.cancel_generation()
                        else tab.start_generation()
                    }
                }
            }
        }
    }
}
