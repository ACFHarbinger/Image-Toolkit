/*!
    \qmltype CBIRTrainTab
    \inqmlmodule ImageToolkit.Tabs.Models.Delta
    \brief CBIR embedding model training sub-tab.

    CBIRTrainTab trains a content-based image retrieval embedding model
    (CLIP ViT-B/32, ResNet-50, or EfficientNet-V2-S backbone) using InfoNCE
    or TripletMargin loss, then optionally builds a FAISS index for fast
    retrieval.

    Backend object: \c mainBackend.cbirTrainTab

    Key slots: \c start_training(), \c stop_training(),
    \c browse_dataset_dir(), \c browse_output_dir(), \c build_index()
    Key properties: \c is_training, \c status_text, \c progress, \c log_output,
    \c recall_at_1, \c recall_at_5, \c recall_at_10
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../components"
import "../../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.cbirTrainTab ? mainBackend.cbirTrainTab : null

    ScrollView {
        anchors.fill: parent

        ColumnLayout {
            width: parent.parent.width
            anchors.margins: 20
            spacing: 15

            Text {
                text: "CBIR Embedding Model Training"
                color: Style.text
                font.pixelSize: 22
                font.bold: true
            }

            // Dataset
            GroupBox {
                title: "Dataset"
                Layout.fillWidth: true
                GridLayout {
                    columns: 3
                    columnSpacing: 10
                    rowSpacing: 8
                    Layout.fillWidth: true

                    Label { text: "Image Directory:"; color: Style.text }
                    TextField {
                        id: datasetDirField
                        Layout.fillWidth: true
                        placeholderText: "Path to labelled image directory..."
                        text: tab ? tab.dataset_dir : ""
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                        readOnly: true
                    }
                    AppButton { text: "Browse"; onClicked: if (tab) tab.browse_dataset_dir() }

                    Label { text: "Output Directory:"; color: Style.text }
                    TextField {
                        id: outputDirField
                        Layout.fillWidth: true
                        text: tab ? tab.output_dir : ""
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                        readOnly: true
                    }
                    AppButton { text: "Browse"; onClicked: if (tab) tab.browse_output_dir() }

                    Label { text: "Val Split:"; color: Style.text }
                    SpinBox { from: 5; to: 50; value: tab ? Math.round(tab.val_split * 100) : 15; suffix: "%" }
                    Item {}
                }
            }

            // Backbone
            GroupBox {
                title: "Backbone"
                Layout.fillWidth: true
                GridLayout {
                    columns: 2; columnSpacing: 16; rowSpacing: 8
                    Label { text: "Architecture:"; color: Style.text }
                    ComboBox {
                        model: ["CLIP ViT-B/32", "ResNet-50", "EfficientNet-V2-S"]
                        onCurrentTextChanged: if (tab) tab.backbone = currentText
                    }
                    Label { text: "Projection Head Width:"; color: Style.text }
                    SpinBox { from: 64; to: 2048; value: tab ? tab.proj_head_width : 256; stepSize: 64
                              onValueChanged: if (tab) tab.proj_head_width = value }
                    Label { text: "Freeze Backbone Warmup (epochs):"; color: Style.text }
                    SpinBox { from: 0; to: 50; value: tab ? tab.freeze_warmup_epochs : 5
                              onValueChanged: if (tab) tab.freeze_warmup_epochs = value }
                }
            }

            // Loss + Training
            GroupBox {
                title: "Loss & Training"
                Layout.fillWidth: true
                GridLayout {
                    columns: 2; columnSpacing: 16; rowSpacing: 8
                    Label { text: "Loss:"; color: Style.text }
                    ComboBox {
                        model: ["InfoNCE (NT-Xent)", "TripletMargin"]
                        onCurrentTextChanged: if (tab) tab.loss_type = currentText
                    }
                    Label { text: "Epochs:"; color: Style.text }
                    SpinBox { from: 1; to: 1000; value: tab ? tab.epochs : 50
                              onValueChanged: if (tab) tab.epochs = value }
                    Label { text: "Batch Size:"; color: Style.text }
                    SpinBox { from: 8; to: 512; value: tab ? tab.batch_size : 64; stepSize: 8
                              onValueChanged: if (tab) tab.batch_size = value }
                    Label { text: "Learning Rate:"; color: Style.text }
                    TextField {
                        text: tab ? tab.lr : "1e-4"
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                        onTextChanged: if (tab) tab.lr = text
                        Layout.preferredWidth: 100
                    }
                    CheckBox {
                        text: "AMP (mixed precision)"
                        palette.windowText: Style.text
                        Layout.columnSpan: 2
                        onCheckedChanged: if (tab) tab.use_amp = checked
                    }
                }
            }

            // Progress + telemetry
            ProgressBar { Layout.fillWidth: true; value: tab ? tab.progress / 100.0 : 0; visible: tab ? tab.is_training : false }

            RowLayout {
                spacing: 20
                Text { text: "Recall@1: " + (tab ? tab.recall_at_1 : "—"); color: Style.text }
                Text { text: "Recall@5: " + (tab ? tab.recall_at_5 : "—"); color: Style.text }
                Text { text: "Recall@10: " + (tab ? tab.recall_at_10 : "—"); color: Style.text }
            }

            Rectangle {
                Layout.fillWidth: true; height: 150
                color: Style.secondaryBackground; border.color: Style.border; radius: Style.borderRadius
                ScrollView {
                    anchors.fill: parent
                    TextArea {
                        readOnly: true
                        text: tab ? tab.log_output : ""
                        color: Style.text; font.family: "Monospace"; font.pixelSize: 11
                        background: null
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true; spacing: 12
                AppButton {
                    text: (tab && tab.is_training) ? "Stop Training" : "Start Training"
                    Layout.fillWidth: true
                    background: Rectangle { color: (tab && tab.is_training) ? "#e74c3c" : Style.accent; radius: Style.borderRadius }
                    onClicked: { if (!tab) return; if (tab.is_training) tab.stop_training(); else tab.start_training() }
                }
                AppButton {
                    text: "Build FAISS Index"
                    Layout.preferredWidth: 180
                    enabled: !(tab && tab.is_training)
                    onClicked: if (tab) tab.build_index()
                }
            }
        }
    }
}
