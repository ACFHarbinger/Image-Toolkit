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
            title: "Data & Model"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                Layout.fillWidth: true
                
                Label { text: "Dataset Directory:"; color: Style.text }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { placeholderText: "Select image folder..."; Layout.fillWidth: true }
                    AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                }

                Label { text: "Base Model ID:"; color: Style.text }
                ComboBox {
                    Layout.fillWidth: true
                    model: ["stabilityai/stable-diffusion-2-1", "runwayml/stable-diffusion-v1-5"]
                }
            }
        }

        GroupBox {
            title: "Training Parameters"
            Layout.fillWidth: true
            GridLayout {
                columns: 4
                rowSpacing: 15
                columnSpacing: 15
                
                Label { text: "Rank (Alpha):"; color: Style.text }
                SpinBox { from: 1; to: 256; value: 64 }

                Label { text: "Learning Rate:"; color: Style.text }
                SpinBox {
                    id: lrSpin
                    from: 1; to: 10000; value: 100
                    stepSize: 10
                    editable: true
                    property int decimals: 6
                    property real realValue: value / 1000000.0
                    
                    textFromValue: function(value, locale) {
                        return Number(value / 1000000.0).toLocaleString(locale, 'f', lrSpin.decimals)
                    }

                    valueFromText: function(text, locale) {
                        return Number.fromLocaleString(locale, text) * 1000000.0
                    }
                }
                Label { text: "Batch Size:"; color: Style.text }
                SpinBox { from: 1; to: 128; value: 4 }

                Label { text: "Epochs:"; color: Style.text }
                SpinBox { from: 1; to: 1000; value: 10 }
            }
        }

        GroupBox {
            title: "Output"
            Layout.fillWidth: true
            RowLayout {
                spacing: 10
                Label { text: "Weights Filename:"; color: Style.text }
                TextField { text: "pytorch_lora_weights.safetensors"; Layout.fillWidth: true }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 15
            AppButton {
                text: "Start Training"
                Layout.fillWidth: true
                background: Rectangle { color: Style.accent; radius: Style.borderRadius }
            }
            AppButton {
                text: "Stop"
                Layout.preferredWidth: 100
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            color: Style.secondaryBackground
            border.color: Style.border
            radius: Style.borderRadius
            TextArea {
                anchors.fill: parent
                readOnly: true
                text: "Training logs will appear here..."
                color: Style.text
                font.family: "Monospace"
            }
        }
    }
}

