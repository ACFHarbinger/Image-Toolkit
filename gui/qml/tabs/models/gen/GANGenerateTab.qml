import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../components"
import "../../../"

ColumnLayout {
    anchors.fill: parent
    spacing: 15

    GroupBox {
        title: "Custom GAN Settings"
        Layout.fillWidth: true
            Label { text: "Checkpoint (.pth):"; color: Style.text }
            RowLayout {
                Layout.fillWidth: true
                TextField { id: ckptPathField; placeholderText: "Path to .pth checkpoint file"; Layout.fillWidth: true }
                AppButton { text: "Browse"; Layout.preferredWidth: 80 } 
            }

            Label { text: "Count:"; color: Style.text }
            SpinBox { id: countSpin; from: 1; to: 64; value: 8 }
    }

    AppButton {
        text: "Run GAN Generator"
        Layout.fillWidth: true
        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        onClicked: {
            if (mainBackend && mainBackend.generateTab && mainBackend.generateTab.basic_gan_gen_tab) {
                mainBackend.generateTab.basic_gan_gen_tab.generate_from_qml(
                    ckptPathField.text,
                    countSpin.value
                )
            }
        }
    }
}

