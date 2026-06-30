/*!
    \qmltype FinalOutputReviewDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL checkpoint 5 — final output RLHF feedback dialog.

    FinalOutputReviewDialog shows the finished stitch and collects an overall
    quality rating (1–10 slider) plus optional flaw annotations (type +
    severity).  Feedback is persisted by the caller via \c backend.submit().

    Backend (\l backend) must expose:
    \list
      \li \c outputImage — string URL of the stitched result.
      \li \c flawTypes — list of strings (flaw type options).
      \li \c submit(rating, flaws) — slot; \a flaws is a list of
          \c {type, severity} objects.
      \li \c accept() — slot (no feedback, just continue).
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var FinalOutputReviewDialog::backend
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
    signal submitted()
    signal accepted()
    signal cancelled()

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 760
    implicitHeight: 600

    // Collected flaws
    property var _flaws: []

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text { text: "Final Output — RLHF Feedback"; color: Style.text; font.pixelSize: 18; font.bold: true }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // Output image
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#000000"
                border.color: Style.border

                Image {
                    anchors.fill: parent
                    source: backend ? backend.outputImage : ""
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
            }

            // Rating + flaw controls
            ColumnLayout {
                Layout.preferredWidth: 260
                Layout.fillHeight: true
                spacing: 14

                GroupBox {
                    title: "Overall Quality (1–10)"
                    Layout.fillWidth: true
                    ColumnLayout {
                        RowLayout {
                            Text { text: "1"; color: Style.mutedText }
                            Slider {
                                id: ratingSlider
                                Layout.fillWidth: true
                                from: 1; to: 10; stepSize: 1; value: 7
                            }
                            Text { text: "10"; color: Style.mutedText }
                            Text { text: ratingSlider.value.toFixed(0); color: Style.accent; font.bold: true; Layout.preferredWidth: 20 }
                        }
                    }
                }

                GroupBox {
                    title: "Add Flaw Annotation"
                    Layout.fillWidth: true
                    ColumnLayout {
                        ComboBox { id: flawType; model: backend ? backend.flawTypes : ["seam", "ghosting", "misalignment", "color_shift", "blur"]; Layout.fillWidth: true }
                        ComboBox { id: flawSeverity; model: ["minor", "moderate", "severe", "critical"]; Layout.fillWidth: true }
                        AppButton {
                            text: "Add Flaw"
                            Layout.fillWidth: true
                            onClicked: {
                                root._flaws.push({ type: flawType.currentText, severity: flawSeverity.currentText })
                                flawList.model = root._flaws.slice()
                            }
                        }
                    }
                }

                Text { text: "Flaws (" + root._flaws.length + ")"; color: Style.text; font.bold: true }
                ListView {
                    id: flawList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: root._flaws
                    delegate: RowLayout {
                        width: ListView.view.width
                        Text { text: modelData.type; color: Style.text; font.pixelSize: 11; Layout.fillWidth: true }
                        Text { text: modelData.severity; color: Style.mutedText; font.pixelSize: 11 }
                        Button {
                            text: "✕"; flat: true
                            contentItem: Text { text: parent.text; color: "#e74c3c" }
                            onClicked: { root._flaws.splice(index, 1); flawList.model = root._flaws.slice() }
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
                text: "Accept (No Feedback)"
                onClicked: { if (backend) backend.accept(); root.accepted() }
            }
            AppButton {
                text: "Submit Feedback"
                background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                onClicked: { if (backend) backend.submit(ratingSlider.value, root._flaws); root.submitted() }
            }
        }
    }
}
