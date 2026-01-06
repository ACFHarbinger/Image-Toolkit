import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../components"
import "../../../"

ScrollView {
    anchors.fill: parent
    ColumnLayout {
        width: parent.width
        spacing: 15

        GroupBox {
            title: "Model & Output"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                rowSpacing: 15
                columnSpacing: 15
                Layout.fillWidth: true
                
                Label { text: "Model ID:"; color: Style.text }
                ComboBox {
                    Layout.fillWidth: true
                    model: ["stabilityai/stable-diffusion-2-1", "runwayml/stable-diffusion-v1-5"]
                }

                Label { text: "LoRA Path:"; color: Style.text }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { placeholderText: "Path to .safetensors"; Layout.fillWidth: true }
                    AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                }

                Label { text: "Output Name:"; color: Style.text }
                TextField { text: "output.png"; Layout.fillWidth: true }
            }
        }

        GroupBox {
            title: "Prompts"
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                Label { text: "Positive Prompt:"; color: Style.text; font.bold: true }
                TextArea {
                    placeholderText: "Describe what you want to see..."
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border }
                    color: Style.text
                }
                Label { text: "Negative Prompt:"; color: Style.text; font.bold: true }
                TextArea {
                    placeholderText: "Describe what you want to exclude..."
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border }
                    color: Style.text
                }
            }
        }

        GroupBox {
            title: "Hyperparameters"
            Layout.fillWidth: true
            RowLayout {
                spacing: 20
                ColumnLayout {
                    Label { text: "Steps:"; color: Style.text }
                    SpinBox { from: 1; to: 100; value: 30 }
                }
                ColumnLayout {
                    Label { text: "Guidance Scale:"; color: Style.text }
                    SpinBox {
                        id: guidanceSpin
                        from: 10; to: 200; value: 75
                        stepSize: 5
                        editable: true
                        property int decimals: 1
                        property real realValue: value / 10.0
                        
                        validator: DoubleValidator {
                            bottom: Math.min(guidanceSpin.from, guidanceSpin.to)
                            top:  Math.max(guidanceSpin.from, guidanceSpin.to)
                        }

                        textFromValue: function(value, locale) {
                            return Number(value / 10.0).toLocaleString(locale, 'f', guidanceSpin.decimals)
                        }

                        valueFromText: function(text, locale) {
                            return Number.fromLocaleString(locale, text) * 10.0
                        }
                    }
                }
                ColumnLayout {
                    Label { text: "Batch Size:"; color: Style.text }
                    SpinBox { from: 1; to: 32; value: 1 }
                }
            }
        }

        AppButton {
            text: "Generate Images"
            Layout.fillWidth: true
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        }
    }
}

