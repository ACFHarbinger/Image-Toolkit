/*!
    \qmltype TrainTab
    \inqmlmodule ImageToolkit.Tabs.Models
    \brief Training dispatcher tab — routes to the active architecture sub-tab.

    TrainTab hosts a \c StackLayout containing five training sub-tabs
    (\l LoRATrainTab, \l R3GANTrainTab, \l GANTrainTab, \l CBIRTrainTab,
    \l StitchTrainTab).  An architecture combo at the top selects the active
    sub-tab.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "delta"
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
                    { text: "Basic GAN (Custom)", value: "basic_gan" },
                    { text: "CBIR (Reverse Search)", value: "cbir" },
                    { text: "AnimeStitch", value: "stitch" }
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
            CBIRTrainTab {}
            StitchTrainTab {}
        }
    }
}

