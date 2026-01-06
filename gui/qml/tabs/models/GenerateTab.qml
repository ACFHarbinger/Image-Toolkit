import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "gen"
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
            Text { text: "Model Architecture:"; color: Style.text; font.bold: true }
            ComboBox {
                id: modelSelector
                Layout.fillWidth: true
                model: [
                    { text: "LoRA (Diffusion and GANs)", value: "lora" },
                    { text: "Stable Diffusion 3.5", value: "sd3" },
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

            LoRAGenerateTab {}
            SD3GenerateTab {}
            R3GANGenerateTab {}
            GANGenerateTab {}
        }
    }
}

