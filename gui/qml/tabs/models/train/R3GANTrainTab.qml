/*!
    \qmltype R3GANTrainTab
    \inqmlmodule ImageToolkit.Tabs.Models.Train
    \brief R3GAN training sub-tab.

    R3GANTrainTab launches an R3GAN training run from a ZIP archive or
    directory dataset.  Controls cover the dataset path, output directory,
    GPU count, and output resolution (256, 512, or 1024 px).  Clicking
    \e {Launch R3GAN Training} starts the run.  The backend slot is not yet
    wired.
*/
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
            title: "R3GAN Configuration"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                Layout.fillWidth: true
                
                Label { text: "Dataset Path (ZIP or dir):"; color: Style.text }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { placeholderText: "Select dataset..."; Layout.fillWidth: true }
                    AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                }

                Label { text: "Output Directory:"; color: Style.text }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { text: "training-runs"; Layout.fillWidth: true }
                    AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                }
            }
        }

        GroupBox {
            title: "Hardware & Quality"
            Layout.fillWidth: true
            RowLayout {
                spacing: 20
                ColumnLayout {
                    Label { text: "GPU Count:"; color: Style.text }
                    SpinBox { from: 1; to: 8; value: 1 }
                }
                ColumnLayout {
                    Label { text: "Resolution:"; color: Style.text }
                    ComboBox { model: ["256", "512", "1024"] }
                }
            }
        }

        AppButton {
            text: "Launch R3GAN Training"
            Layout.fillWidth: true
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        }
    }
}

