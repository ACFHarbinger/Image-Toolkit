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
                    placeholderText: "What do you want to generate?"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border }
                    color: Style.text
                }
            }
        }

        AppButton {
            text: "Generate (SD3)"
            Layout.fillWidth: true
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        }
    }
}
