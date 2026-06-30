/*!
    \qmltype SafetensorsInspector
    \inqmlmodule ImageToolkit.Components
    \brief Read-only metadata and tensor summary viewer for .safetensors files.

    SafetensorsInspector displays metadata, tensor count summary, and a layer
    tree for a \c .safetensors model file without loading tensor weights.
    Inspection runs in a background thread; a \l ProgressBar is visible while
    loading.

    The \l backend must expose:
    \list
      \li \c filePath — string path to the .safetensors file.
      \li \c isLoading — bool, true while background inspection is running.
      \li \c metadata — object mapping metadata key strings to value strings.
      \li \c tensorSummary — string describing tensor count, dtype distribution, etc.
      \li \c layerTree — list of objects with \c name and \c shape roles for the tree.
      \li \c load(path) — slot to begin background inspection.
    \endlist

    \qmlproperty var SafetensorsInspector::backend
    Backend object providing inspection results.

    \qmlproperty string SafetensorsInspector::filePath
    Path to inspect.  Setting this property calls \c backend.load(filePath).
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"

Item {
    id: root

    property var backend: null
    property string filePath: ""

    onFilePathChanged: if (backend && filePath) backend.load(filePath)

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Toolbar
        Rectangle {
            Layout.fillWidth: true
            height: 44
            color: Style.secondaryBackground
            border.color: Style.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 10

                Text { text: "Safetensors Inspector"; color: Style.text; font.bold: true; font.pixelSize: 14 }
                Item { Layout.fillWidth: true }

                ProgressBar {
                    Layout.preferredWidth: 120
                    indeterminate: true
                    visible: backend ? backend.isLoading : false
                }

                Text {
                    text: root.filePath ? root.filePath.split("/").pop() : "No file loaded"
                    color: Style.mutedText
                    font.pixelSize: 11
                    elide: Text.ElideLeft
                    Layout.preferredWidth: 260
                    horizontalAlignment: Text.AlignRight
                }
            }
        }

        // Content split: metadata + tensor summary top, layer tree bottom
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Vertical

            // Top: metadata + summary
            RowLayout {
                SplitView.preferredHeight: 220
                SplitView.minimumHeight: 120
                spacing: 0

                // Metadata
                GroupBox {
                    title: "Metadata"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ScrollView {
                        anchors.fill: parent
                        Column {
                            spacing: 4
                            Repeater {
                                model: backend && backend.metadata ? Object.keys(backend.metadata) : []
                                delegate: RowLayout {
                                    spacing: 8
                                    Text {
                                        text: modelData + ":"
                                        color: Style.accent
                                        font.pixelSize: 11
                                        font.bold: true
                                        Layout.preferredWidth: 140
                                    }
                                    Text {
                                        text: backend.metadata[modelData]
                                        color: Style.text
                                        font.pixelSize: 11
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                }
                            }
                        }
                    }
                }

                // Tensor summary
                GroupBox {
                    title: "Tensor Summary"
                    Layout.preferredWidth: 300
                    Layout.fillHeight: true
                    ScrollView {
                        anchors.fill: parent
                        TextArea {
                            readOnly: true
                            text: backend ? (backend.tensorSummary || "Loading…") : ""
                            color: Style.text
                            font.family: "Monospace"
                            font.pixelSize: 11
                            background: null
                            wrapMode: TextEdit.Wrap
                        }
                    }
                }
            }

            // Bottom: layer tree
            GroupBox {
                title: "Layer Tree"
                SplitView.fillHeight: true

                ListView {
                    anchors.fill: parent
                    model: backend ? backend.layerTree : []
                    clip: true
                    delegate: RowLayout {
                        width: ListView.view.width
                        height: 24
                        spacing: 8
                        Text {
                            text: modelData.name || ""
                            color: Style.text
                            font.family: "Monospace"
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.shape || ""
                            color: Style.mutedText
                            font.family: "Monospace"
                            font.pixelSize: 11
                            Layout.preferredWidth: 200
                        }
                        Rectangle { height: 1; width: parent.width; color: Style.border; y: parent.height - 1 }
                    }
                }
            }
        }
    }
}
