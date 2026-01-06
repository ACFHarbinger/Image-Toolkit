import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../components"
import "../../../"

ColumnLayout {
    anchors.fill: parent
    spacing: 15

    GroupBox {
        title: "R3GAN Generation"
        Layout.fillWidth: true
        GridLayout {
            columns: 2
            Layout.fillWidth: true
            
            Label { text: "Network (.pkl):"; color: Style.text }
            RowLayout {
                Layout.fillWidth: true
                TextField { placeholderText: "Select model..."; Layout.fillWidth: true }
                AppButton { text: "Browse"; Layout.preferredWidth: 80 }
            }

            Label { text: "Seeds:"; color: Style.text }
            TextField { text: "0-10"; Layout.fillWidth: true }
        }
    }

    AppButton {
        text: "Generate Samples"
        Layout.fillWidth: true
        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
    }
}

