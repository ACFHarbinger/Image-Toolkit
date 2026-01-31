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
                TextField { id: networkField; placeholderText: "Select model..."; Layout.fillWidth: true }
                AppButton { text: "Browse"; Layout.preferredWidth: 80 }
            }

            Label { text: "Seeds:"; color: Style.text }
            TextField { id: seedsField; text: "0-10"; Layout.fillWidth: true }

            Label { text: "Class Index (opt.):"; color: Style.text }
            SpinBox { id: classIdxSpin; from: -1; to: 1000; value: -1 }
        }
    }

    AppButton {
        text: "Generate Samples"
        Layout.fillWidth: true
        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        onClicked: {
            if (mainBackend && mainBackend.generateTab && mainBackend.generateTab.r3gan_tab) {
                mainBackend.generateTab.r3gan_tab.generate_from_qml(
                    networkField.text,
                    seedsField.text,
                    classIdxSpin.value
                )
            }
        }
    }
}

