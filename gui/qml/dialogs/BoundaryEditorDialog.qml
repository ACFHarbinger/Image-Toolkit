/*!
    \qmltype BoundaryEditorDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL checkpoint 3.5 — interactive seam boundary editor.

    BoundaryEditorDialog shows a downsampled canvas preview with N-1
    draggable horizontal lines representing ownership boundaries between
    adjacent frames.  The user drags lines to place each seam where the
    character overlap looks best, then clicks "Resume Pipeline" to pass the
    adjusted boundaries back to the worker.

    Only used for vertical-scroll stitches; horizontal scroll bypasses this
    checkpoint.

    Backend (\l backend) must expose:
    \list
      \li \c canvasImage — string URL of the downsampled canvas preview.
      \li \c boundaries — list of y-coordinate values (0.0–1.0, normalised).
      \li \c frameLabels — list of strings (e.g. "Frame 1", "Frame 2", …).
      \li \c setBoundary(index, yNorm) — slot to update one boundary.
      \li \c resume() — slot called when the user accepts.
      \li \c cancel() — slot called when the user cancels.
    \endlist

    \qmlproperty var BoundaryEditorDialog::backend
    Pipeline HITL backend providing boundary data and resume/cancel slots.

    \qmlsignal BoundaryEditorDialog::resumed()
    Emitted after \c backend.resume() is called.

    \qmlsignal BoundaryEditorDialog::cancelled()
    Emitted after \c backend.cancel() is called.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"
import "../components"

Rectangle {
    id: root

    property var backend: null
    signal resumed()
    signal cancelled()

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 620
    implicitHeight: 620

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text { text: "Seam Boundary Editor"; color: Style.text; font.pixelSize: 18; font.bold: true }
        Text {
            text: "Drag the red lines to adjust where each frame's ownership boundary falls on the canvas."
            color: Style.mutedText; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true
        }

        // Canvas preview with draggable boundary lines
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#000000"
            border.color: Style.border
            clip: true

            Image {
                id: canvasPreview
                anchors.fill: parent
                source: backend ? backend.canvasImage : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }

            // Boundary lines overlay
            Repeater {
                model: backend ? backend.boundaries : []
                delegate: Item {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    y: modelData * canvasPreview.paintedHeight + (canvasPreview.height - canvasPreview.paintedHeight) / 2

                    Rectangle {
                        anchors.left: parent.left; anchors.right: parent.right
                        height: 2
                        color: "#ff5050"
                        opacity: 0.85
                    }

                    Text {
                        text: "↕  Boundary " + (index + 1)
                        color: "#ffdc3c"
                        font.pixelSize: 11
                        font.bold: true
                        x: 8; y: -14
                    }

                    MouseArea {
                        anchors.left: parent.left; anchors.right: parent.right
                        height: 20; y: -10
                        cursorShape: Qt.SizeVerCursor
                        drag.target: parent
                        drag.axis: Drag.YAxis
                        drag.minimumY: 0
                        drag.maximumY: canvasPreview.paintedHeight
                        onPositionChanged: {
                            if (drag.active && backend) {
                                var yNorm = parent.y / canvasPreview.paintedHeight
                                backend.setBoundary(index, Math.min(Math.max(yNorm, 0), 1))
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Item { Layout.fillWidth: true }
            AppButton {
                text: "Cancel"
                background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                onClicked: { if (backend) backend.cancel(); root.cancelled() }
            }
            AppButton {
                text: "Resume Pipeline"
                background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                onClicked: { if (backend) backend.resume(); root.resumed() }
            }
        }
    }
}
