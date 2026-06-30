/*!
    \qmltype FrameSelectionDialog
    \inqmlmodule ImageToolkit.Components
    \brief Video frame picker dialog with scrubber and live preview.

    FrameSelectionDialog presents a frame count label, a \l Slider scrubber,
    a \l SpinBox for exact frame input, and a preview pane that displays
    the currently selected frame via \c backend.frameImage.

    The backend must expose:
    \list
      \li \c totalFrames — int, total frame count in the video.
      \li \c currentFrame — int (read/write), currently selected frame index.
      \li \c frameImage — string URL/path of the rendered preview frame.
      \li \c videoPath — string path of the source video file.
      \li \c seek(frameIndex) — slot to seek to a specific frame.
    \endlist

    Accepted / rejected results are communicated via the \l accepted and
    \l rejected signals.

    \qmlproperty var FrameSelectionDialog::backend
    Backend object providing video metadata and seek functionality.

    \qmlsignal FrameSelectionDialog::accepted(int frameIndex)
    Emitted when the user confirms the selected frame.

    \qmlsignal FrameSelectionDialog::rejected()
    Emitted when the user cancels the dialog.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"

Rectangle {
    id: root

    property var backend: null
    signal accepted(int frameIndex)
    signal rejected()

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 680
    implicitHeight: 520

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Title
        Text {
            text: "Select Frame"
            color: Style.text
            font.pixelSize: 18
            font.bold: true
        }

        // Preview
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#000000"
            radius: 4
            border.color: Style.border

            Image {
                anchors.fill: parent
                anchors.margins: 2
                source: backend ? backend.frameImage : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }

            Text {
                anchors.centerIn: parent
                text: backend ? "" : "No video loaded"
                color: Style.mutedText
                visible: !backend || !backend.frameImage
            }
        }

        // Scrubber row
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text { text: "Frame:"; color: Style.text; Layout.preferredWidth: 48 }

            Slider {
                id: scrubber
                Layout.fillWidth: true
                from: 0
                to: backend ? Math.max(0, backend.totalFrames - 1) : 0
                stepSize: 1
                value: backend ? backend.currentFrame : 0
                onMoved: if (backend) backend.seek(Math.round(value))
            }

            SpinBox {
                id: frameSpinBox
                from: 0
                to: backend ? Math.max(0, backend.totalFrames - 1) : 0
                value: backend ? backend.currentFrame : 0
                Layout.preferredWidth: 100
                onValueModified: if (backend) backend.seek(value)
            }

            Text {
                text: "/ " + (backend ? backend.totalFrames : 0)
                color: Style.mutedText
                Layout.preferredWidth: 70
            }
        }

        // Buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Item { Layout.fillWidth: true }

            Button {
                text: "Cancel"
                onClicked: root.rejected()
                background: Rectangle {
                    color: parent.hovered ? Style.border : "transparent"
                    border.color: Style.border
                    radius: Style.borderRadius
                }
                contentItem: Text { text: parent.text; color: Style.text; horizontalAlignment: Text.AlignHCenter }
            }

            Button {
                text: "Select Frame"
                onClicked: root.accepted(backend ? backend.currentFrame : 0)
                background: Rectangle {
                    color: parent.hovered ? Qt.lighter(Style.accent) : Style.accent
                    radius: Style.borderRadius
                }
                contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter }
            }
        }
    }
}
