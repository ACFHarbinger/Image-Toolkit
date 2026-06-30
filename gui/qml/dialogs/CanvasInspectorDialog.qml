/*!
    \qmltype CanvasInspectorDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL checkpoint 4 — interactive canvas layout inspector.

    CanvasInspectorDialog shows a composite canvas preview with per-frame
    coloured overlap overlays.  The user can select a frame in the list to
    highlight it, adjust its X/Y translation nudge via spin boxes, and either
    accept the layout or re-trigger bundle adjustment.

    Backend (\l backend) must expose:
    \list
      \li \c canvasImage — string URL of the rendered composite.
      \li \c frameCount — int.
      \li \c selectedFrame — int (read/write), currently highlighted frame.
      \li \c nudgeX — real (read/write), X translation override in px.
      \li \c nudgeY — real (read/write), Y translation override in px.
      \li \c accept() — slot.
      \li \c reBundle() — slot to re-run bundle adjustment.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var CanvasInspectorDialog::backend
    Pipeline HITL backend for canvas layout review.
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
    implicitHeight: 620

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Left: canvas preview
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            Text { text: "Canvas Layout Inspector"; color: Style.text; font.pixelSize: 18; font.bold: true }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#000000"
                border.color: Style.border

                Image {
                    anchors.fill: parent
                    source: backend ? backend.canvasImage : ""
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "Re-Bundle"
                    background: Rectangle { color: "#8e44ad"; radius: Style.borderRadius }
                    onClicked: if (backend) backend.reBundle()
                }
                AppButton {
                    text: "Cancel"
                    background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                    onClicked: { if (backend) backend.cancel(); root.cancelled() }
                }
                AppButton {
                    text: "Accept Layout"
                    background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                    onClicked: { if (backend) backend.accept(); root.accepted() }
                }
            }
        }

        // Right: frame list + nudge controls
        ColumnLayout {
            Layout.preferredWidth: 260
            Layout.fillHeight: true
            spacing: 12

            Text { text: "Frames"; color: Style.text; font.bold: true }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: backend ? backend.frameCount : 0
                clip: true
                delegate: ItemDelegate {
                    width: ListView.view.width
                    highlighted: backend && backend.selectedFrame === index
                    text: "Frame " + index
                    contentItem: Text {
                        text: parent.text
                        color: parent.highlighted ? Style.accent : Style.text
                        font.bold: parent.highlighted
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 8
                    }
                    background: Rectangle {
                        color: parent.highlighted ? Qt.rgba(0.44, 0.54, 0.85, 0.15) : "transparent"
                        border.color: parent.highlighted ? Style.accent : "transparent"
                        radius: 4
                    }
                    onClicked: if (backend) backend.selectedFrame = index
                }
            }

            GroupBox {
                title: "Translation Nudge (px)"
                Layout.fillWidth: true
                GridLayout {
                    columns: 2
                    columnSpacing: 8
                    rowSpacing: 6
                    Label { text: "X:"; color: Style.text }
                    SpinBox {
                        from: -500; to: 500
                        value: backend ? backend.nudgeX : 0
                        onValueModified: if (backend) backend.nudgeX = value
                    }
                    Label { text: "Y:"; color: Style.text }
                    SpinBox {
                        from: -500; to: 500
                        value: backend ? backend.nudgeY : 0
                        onValueModified: if (backend) backend.nudgeY = value
                    }
                }
            }
        }
    }
}
