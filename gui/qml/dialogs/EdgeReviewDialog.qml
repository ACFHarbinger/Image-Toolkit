/*!
    \qmltype EdgeReviewDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL checkpoint 2 — edge graph review and manual edge addition.

    EdgeReviewDialog displays the pairwise matching graph as a circular node
    diagram with colour-coded confidence edges.  The user can:
    \list
      \li Inspect edge confidence values in the table.
      \li Toggle individual edges enabled/disabled.
      \li Add a manual edge by specifying frame indices and translation.
      \li Accept the current graph or cancel.
    \endlist

    Backend (\l backend) must expose:
    \list
      \li \c graphImage — string URL of the rendered node/edge diagram.
      \li \c edges — list of objects with \c i, \c j, \c dx, \c dy,
          \c weight (real 0–1), \c enabled (bool) roles.
      \li \c frameCount — int.
      \li \c toggleEdge(idx, enabled) — slot.
      \li \c addManualEdge(i, j, dx, dy) — slot.
      \li \c accept() — slot.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var EdgeReviewDialog::backend
    Pipeline HITL backend.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"
import "../components"

Rectangle {
    id: root

    property var backend: null
    signal accepted()
    signal cancelled()

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 900
    implicitHeight: 640

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Left: graph image
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            Text { text: "Edge Graph Review"; color: Style.text; font.pixelSize: 18; font.bold: true }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#1a1a1a"
                border.color: Style.border

                Image {
                    anchors.fill: parent
                    source: backend ? backend.graphImage : ""
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
            }

            // Manual edge addition
            GroupBox {
                title: "Add Manual Edge"
                Layout.fillWidth: true
                GridLayout {
                    columns: 5
                    columnSpacing: 8
                    Label { text: "i:"; color: Style.text }
                    SpinBox { id: edgeI; from: 0; to: backend ? backend.frameCount - 1 : 0 }
                    Label { text: "j:"; color: Style.text }
                    SpinBox { id: edgeJ; from: 0; to: backend ? backend.frameCount - 1 : 0 }
                    Label { text: ""; Layout.fillWidth: true }
                    Label { text: "dx (px):"; color: Style.text }
                    SpinBox { id: edgeDx; from: -9999; to: 9999 }
                    Label { text: "dy (px):"; color: Style.text }
                    SpinBox { id: edgeDy; from: -9999; to: 9999 }
                    AppButton {
                        text: "Add"
                        onClicked: if (backend) backend.addManualEdge(edgeI.value, edgeJ.value, edgeDx.value, edgeDy.value)
                    }
                }
            }
        }

        // Right: edge table + accept/cancel
        ColumnLayout {
            Layout.preferredWidth: 320
            Layout.fillHeight: true
            spacing: 8

            Text { text: "Edges (" + (backend ? backend.edges.length : 0) + ")"; color: Style.text; font.bold: true }

            // Edge confidence legend
            Row {
                spacing: 12
                Row { spacing: 4; Rectangle { width: 10; height: 10; color: "#50c850"; radius: 2 }; Text { text: "≥0.7"; color: Style.mutedText; font.pixelSize: 10 } }
                Row { spacing: 4; Rectangle { width: 10; height: 10; color: "#c8c850"; radius: 2 }; Text { text: "0.4–0.7"; color: Style.mutedText; font.pixelSize: 10 } }
                Row { spacing: 4; Rectangle { width: 10; height: 10; color: "#dc5050"; radius: 2 }; Text { text: "<0.4"; color: Style.mutedText; font.pixelSize: 10 } }
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: backend ? backend.edges : []
                clip: true
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 36
                    color: index % 2 === 0 ? Style.secondaryBackground : "transparent"
                    border.color: Style.border

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 6

                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: modelData.weight >= 0.7 ? "#50c850"
                                 : modelData.weight >= 0.4 ? "#c8c850"
                                 : "#dc5050"
                        }

                        Text {
                            text: modelData.i + "→" + modelData.j
                            color: Style.text; font.pixelSize: 12; font.bold: true
                            Layout.preferredWidth: 50
                        }
                        Text {
                            text: "dx=" + modelData.dx.toFixed(0) + " dy=" + modelData.dy.toFixed(0)
                            color: Style.mutedText; font.pixelSize: 10
                            Layout.fillWidth: true
                        }
                        Text {
                            text: (modelData.weight * 100).toFixed(0) + "%"
                            color: Style.text; font.pixelSize: 11
                            Layout.preferredWidth: 36
                        }
                        CheckBox {
                            checked: modelData.enabled
                            onCheckedChanged: if (backend) backend.toggleEdge(index, checked)
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "Cancel"
                    background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                    onClicked: { if (backend) backend.cancel(); root.cancelled() }
                }
                AppButton {
                    text: "Accept Graph"
                    background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                    onClicked: { if (backend) backend.accept(); root.accepted() }
                }
            }
        }
    }
}
