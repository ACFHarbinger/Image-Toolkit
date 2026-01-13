import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "train"
import "../../components"
import "../../"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        // --- Model Selector ---
        RowLayout {
            Layout.fillWidth: true
            spacing: 15
            Text { text: "Training Architecture:"; color: Style.text; font.bold: true }
            ComboBox {
                id: modelSelector
                Layout.fillWidth: true
                model: [
                    { text: "LoRA (Diffusion and GANs)", value: "lora" },
                    { text: "R3GAN (NVLabs)", value: "r3gan" },
                    { text: "Basic GAN (Custom)", value: "basic_gan" }
                ]
                textRole: "text"
            }
        }

        // --- Content Stack ---
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: modelSelector.currentIndex

            LoRATrainTab {}
            R3GANTrainTab {}
            GANTrainTab {}
        }
    }
}

