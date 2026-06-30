/*!
    \qmltype SelectionReviewDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL checkpoint 1 — frame selection review and override.

    SelectionReviewDialog presents the selected frames as thumbnail cards
    with per-pair temporal diff bars.  The user can toggle frames in/out
    of the final selection before accepting.  Cards whose diff score is
    high (≥0.15 normalised) are highlighted in amber.

    Backend (\l backend) must expose:
    \list
      \li \c frames — list of objects with \c path (string), \c thumbnail
          (URL), \c diff (real 0–1), \c selected (bool) roles.
      \li \c toggleFrame(index, selected) — slot.
      \li \c accept() — slot.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var SelectionReviewDialog::backend
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
    implicitWidth: 860
    implicitHeight: 580

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Text { text: "Frame Selection Review"; color: Style.text; font.pixelSize: 18; font.bold: true; Layout.fillWidth: true }
            Text {
                text: backend ? (backend.frames.filter(function(f){return f.selected}).length + " / " + backend.frames.length + " selected") : ""
                color: Style.mutedText; font.pixelSize: 12
            }
        }

        Text {
            text: "Toggle frames to include/exclude them.  High diff score (amber) = large temporal gap to previous frame."
            color: Style.mutedText; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true
        }

        // Frame grid
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Flow {
                width: parent.width
                spacing: 10

                Repeater {
                    model: backend ? backend.frames : []

                    Rectangle {
                        width: 160
                        height: 185
                        color: modelData.selected ? Style.secondaryBackground : "#0a0a0a"
                        border.color: modelData.selected ? Style.accent : Style.border
                        border.width: modelData.selected ? 2 : 1
                        radius: 6
                        opacity: modelData.selected ? 1.0 : 0.45

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 4

                            Image {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                source: modelData.thumbnail || ""
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                            }

                            // Diff bar
                            Rectangle {
                                Layout.fillWidth: true
                                height: 6
                                radius: 3
                                color: Style.secondaryBackground
                                Rectangle {
                                    width: parent.width * Math.min(1, modelData.diff / 0.15)
                                    height: parent.height
                                    radius: 3
                                    color: modelData.diff >= 0.15 ? "#f0a000" : "#27ae60"
                                }
                                ToolTip.visible: diffMA.containsMouse
                                ToolTip.text: "Diff: " + (modelData.diff * 100).toFixed(1) + "%"
                                MouseArea { id: diffMA; anchors.fill: parent; hoverEnabled: true }
                            }

                            RowLayout {
                                Text {
                                    text: modelData.path ? modelData.path.split("/").pop() : ""
                                    color: Style.text; font.pixelSize: 9
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                CheckBox {
                                    checked: modelData.selected
                                    onCheckedChanged: if (backend) backend.toggleFrame(index, checked)
                                }
                            }
                        }
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
                text: "Accept Selection"
                background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                onClicked: { if (backend) backend.accept(); root.accepted() }
            }
        }
    }
}
