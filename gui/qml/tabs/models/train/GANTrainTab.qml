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
            title: "Custom GAN Architecture"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                Layout.fillWidth: true
                
                Label { text: "GAN Type:"; color: Style.text }
                ComboBox { model: ["DCGAN", "WGAN", "SNGAN"]; Layout.fillWidth: true }

                Label { text: "Optimizer:"; color: Style.text }
                ComboBox { model: ["Adam", "RMSprop", "SGD"]; Layout.fillWidth: true }
            }
        }

        GroupBox {
            title: "Training Loop"
            Layout.fillWidth: true
            RowLayout {
                spacing: 20
                ColumnLayout {
                    Label { text: "Num Iterations:"; color: Style.text }
                    SpinBox { from: 1000; to: 1000000; value: 100000; stepSize: 1000 }
                }
                ColumnLayout {
                    Label { text: "Save Every:"; color: Style.text }
                    SpinBox { from: 100; to: 10000; value: 5000 }
                }
            }
        }

        AppButton {
            text: "Train GAN"
            Layout.fillWidth: true
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        }
    }
}

