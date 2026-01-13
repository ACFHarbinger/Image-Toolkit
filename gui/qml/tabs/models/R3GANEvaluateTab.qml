import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        GroupBox {
            title: "R3GAN Model Evaluation"
            Layout.fillWidth: true
            
            GridLayout {
                anchors.fill: parent
                columns: 2
                rowSpacing: 12

                Label { text: "Network (.pkl):"; color: Style.text; font.bold: true }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { placeholderText: "Select model to evaluate..."; Layout.fillWidth: true }
                    AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                }

                Label { text: "Reference Dataset:"; color: Style.text; font.bold: true }
                RowLayout {
                    Layout.fillWidth: true
                    TextField { placeholderText: "Path to real images..."; Layout.fillWidth: true }
                    AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                }

                Label { text: "Metrics to Calculate:"; color: Style.text; font.bold: true; Layout.alignment: Qt.AlignTop }
                ColumnLayout {
                    CheckBox { text: "FID (fid50k_full)"; palette.windowText: Style.text }
                    CheckBox { text: "KID (kid50k_full)"; palette.windowText: Style.text }
                    CheckBox { text: "Precision/Recall (pr50k3_full)"; palette.windowText: Style.text }
                    CheckBox { text: "Inception Score (is50k)"; palette.windowText: Style.text }
                }
            }
        }

        AppButton {
            text: "Start Evaluation"
            Layout.fillWidth: true
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Style.secondaryBackground
            border.color: Style.border
            radius: Style.borderRadius
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 15
                Text { text: "Evaluation Metrics Log:"; color: Style.text; font.bold: true }
                TextArea {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    readOnly: true
                    text: "FID: ...\nKID: ...\nPR: ..."
                    color: Style.text
                    font.family: "Monospace"
                    background: null
                }
            }
        }
    }
}

