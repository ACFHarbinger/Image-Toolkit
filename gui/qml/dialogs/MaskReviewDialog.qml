/*!
    \qmltype MaskReviewDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL checkpoint 1.5 — SAM-2 mask review with click-based refinement.

    MaskReviewDialog displays each frame with its foreground mask overlaid.
    The user can left-click to add positive prompts (expand the mask) or
    right-click to add negative prompts (exclude a region), type a text
    description for re-segmentation, and specify a seam-exclusion region.

    Backend (\l backend) must expose:
    \list
      \li \c frameCount — int.
      \li \c currentFrame — int (read/write).
      \li \c frameImage — string URL of the current frame with mask overlay.
      \li \c isRefining — bool, true while re-segmenting.
      \li \c addPositivePrompt(x, y) — slot (normalised coords).
      \li \c addNegativePrompt(x, y) — slot.
      \li \c resegment(description) — slot.
      \li \c setSeamExclusion(regionDescription) — slot.
      \li \c accept() — slot; accepts all masks and resumes pipeline.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var MaskReviewDialog::backend
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
    implicitWidth: 840
    implicitHeight: 600

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        Text { text: "Mask Review — Segmentation Refinement"; color: Style.text; font.pixelSize: 18; font.bold: true }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // Left: frame + mask overlay
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 6

                // Frame navigator
                RowLayout {
                    Text { text: "Frame:"; color: Style.text }
                    Slider {
                        id: frameSlider
                        Layout.fillWidth: true
                        from: 0
                        to: backend ? Math.max(0, backend.frameCount - 1) : 0
                        stepSize: 1
                        value: backend ? backend.currentFrame : 0
                        onMoved: if (backend) backend.currentFrame = Math.round(value)
                    }
                    Text { text: (backend ? backend.currentFrame : 0) + " / " + (backend ? backend.frameCount - 1 : 0); color: Style.mutedText; font.pixelSize: 11 }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#000000"
                    border.color: Style.border

                    Image {
                        id: frameImg
                        anchors.fill: parent
                        source: backend ? backend.frameImage : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }

                    ProgressBar {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left
                        anchors.right: parent.right
                        indeterminate: true
                        visible: backend ? backend.isRefining : false
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.CrossCursor
                        onClicked: {
                            if (!backend) return
                            var xn = (mouse.x - (frameImg.width - frameImg.paintedWidth) / 2) / frameImg.paintedWidth
                            var yn = (mouse.y - (frameImg.height - frameImg.paintedHeight) / 2) / frameImg.paintedHeight
                            if (mouse.button === Qt.LeftButton) backend.addPositivePrompt(xn, yn)
                            else backend.addNegativePrompt(xn, yn)
                        }
                    }
                }

                Row {
                    spacing: 8
                    Rectangle { width: 12; height: 12; radius: 6; color: "#00ff00" }
                    Text { text: "Left-click: positive prompt"; color: Style.mutedText; font.pixelSize: 11 }
                    Rectangle { width: 12; height: 12; radius: 6; color: "#ff0000" }
                    Text { text: "Right-click: negative prompt"; color: Style.mutedText; font.pixelSize: 11 }
                }
            }

            // Right: controls
            ColumnLayout {
                Layout.preferredWidth: 270
                Layout.fillHeight: true
                spacing: 14

                GroupBox {
                    title: "Re-segment with Description"
                    Layout.fillWidth: true
                    ColumnLayout {
                        TextField {
                            id: descField
                            Layout.fillWidth: true
                            placeholderText: "e.g. anime character, shirt logo…"
                            color: Style.text
                            background: Rectangle { color: Style.inputBackground; border.color: Style.inputBorder; radius: 4 }
                        }
                        AppButton {
                            text: "Re-segment"
                            Layout.fillWidth: true
                            enabled: !(backend && backend.isRefining)
                            onClicked: if (backend) backend.resegment(descField.text)
                        }
                    }
                }

                GroupBox {
                    title: "Seam Exclusion Region"
                    Layout.fillWidth: true
                    ColumnLayout {
                        Text { text: "Route DP seam away from:"; color: Style.mutedText; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        TextField {
                            id: seamExclField
                            Layout.fillWidth: true
                            placeholderText: "e.g. right arm, logo on shirt"
                            color: Style.text
                            background: Rectangle { color: Style.inputBackground; border.color: Style.inputBorder; radius: 4 }
                        }
                        AppButton {
                            text: "Set Exclusion"
                            Layout.fillWidth: true
                            onClicked: if (backend) backend.setSeamExclusion(seamExclField.text)
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    AppButton {
                        text: "Cancel"
                        Layout.fillWidth: true
                        background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                        onClicked: { if (backend) backend.cancel(); root.cancelled() }
                    }
                    AppButton {
                        text: "Accept All Masks"
                        Layout.fillWidth: true
                        background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                        enabled: !(backend && backend.isRefining)
                        onClicked: { if (backend) backend.accept(); root.accepted() }
                    }
                }
            }
        }
    }
}
