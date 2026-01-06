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
            title: "CLIP Zero-Shot Classification"
            Layout.fillWidth: true
            
            ColumnLayout {
                anchors.fill: parent
                spacing: 12

                RowLayout {
                    spacing: 10
                    Label { text: "Model Version:"; color: Style.text; font.bold: true }
                    ComboBox {
                        id: modelVersion
                        Layout.fillWidth: true
                        model: [
                            "Meta CLIP 2 (ViT-H-14, Worldwide)",
                            "Meta CLIP 2 (ViT-bigG-14, Worldwide)",
                            "Meta CLIP 1 (ViT-G-14, 2.5B)",
                            "Meta CLIP 1 (ViT-H-14, 2.5B)"
                        ]
                    }
                }

                RowLayout {
                    spacing: 10
                    Label { text: "Image Path:"; color: Style.text; font.bold: true }
                    TextField {
                        id: imagePath
                        placeholderText: "Path to image to classify..."
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                    }
                    AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Label { text: "Text Prompts (one per line):"; color: Style.text; font.bold: true }
                    TextArea {
                        id: textPrompts
                        text: "a diagram\na dog\na cat"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 120
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                        font.family: "Monospace"
                    }
                }
            }
        }

        AppButton {
            text: "Run CLIP Inference"
            Layout.fillWidth: true
            background: Rectangle { color: Style.accent; radius: Style.borderRadius }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Style.secondaryBackground
            border.color: Style.border
            radius: Style.borderRadius
            clip: true
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 15
                Text { text: "Classification Results:"; color: Style.text; font.bold: true }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {
                        ListElement { label: "dog"; confidence: "0.85" }
                        ListElement { label: "cat"; confidence: "0.12" }
                        ListElement { label: "diagram"; confidence: "0.03" }
                    }
                    delegate: RowLayout {
                        width: parent.width
                        Text { text: model.label; color: Style.text; Layout.fillWidth: true }
                        Rectangle {
                            height: 10
                            Layout.preferredWidth: 100
                            color: Style.border
                            Rectangle {
                                height: parent.height
                                width: parent.width * parseFloat(model.confidence)
                                color: Style.accent
                            }
                        }
                        Text { text: (parseFloat(model.confidence) * 100).toFixed(1) + "%"; color: Style.accent; Layout.preferredWidth: 50 }
                    }
                }
            }
        }
    }
}

