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
            title: "Stable Diffusion 3.5 Settings"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                Layout.fillWidth: true
                
                Label { text: "Model variant:"; color: Style.text }
                ComboBox {
                    id: modelCombo
                    Layout.fillWidth: true
                    model: ["SD3 (Medium)", "SD3 (Large)", "SD3.5 (Turbo)"]
                }
            }
        }

        GroupBox {
            title: "Prompting"
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                Label { text: "Prompt:"; color: Style.text; font.bold: true }
                TextArea {
                    id: promptArea
                    placeholderText: "What do you want to generate?"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120
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
                    Label { text: "Dimensions (WxH):"; color: Style.text }
                    RowLayout {
                        SpinBox { id: widthSpin; from: 512; to: 2048; value: 1024; stepSize: 64; editable: true }
                        Label { text: "x"; color: Style.text }
                        SpinBox { id: heightSpin; from: 512; to: 2048; value: 1024; stepSize: 64; editable: true }
                    }
                }
                ColumnLayout {
                    Label { text: "Steps:"; color: Style.text }
                    SpinBox { id: stepsSpin; from: 1; to: 100; value: 28 }
                }
                ColumnLayout {
                    Label { text: "Guidance:"; color: Style.text }
                    SpinBox {
                        id: guidanceSpin
                        from: 10; to: 200; value: 70
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
                    Label { text: "Batch:"; color: Style.text }
                    SpinBox { id: batchSizeSpin; from: 1; to: 8; value: 1 }
                }

        AppButton {
            text: "Generate (SD3)"
            Layout.fillWidth: true
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
            onClicked: {
                if (mainBackend && mainBackend.generateTab && mainBackend.generateTab.sd3_tab) {
                    mainBackend.generateTab.sd3_tab.generate_from_qml(
                        modelCombo.currentText,
                        promptArea.text,
                        widthSpin.value,
                        heightSpin.value,
                        stepsSpin.value,
                        guidanceSpin.realValue,
                        batchSizeSpin.value
                    )
                }
            }
        }
    }
}
