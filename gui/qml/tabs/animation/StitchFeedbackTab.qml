/*!
    \qmltype StitchFeedbackTab
    \inqmlmodule ImageToolkit.Tabs.Animation
    \brief RLHF feedback collection and reward model training tab.

    StitchFeedbackTab lets the user load a stitched panorama, annotate
    flaw regions on a canvas, set a quality rating, and submit feedback
    records.  Once enough feedback has accumulated the user can train the
    CNN reward model and fine-tune the DRL registration agent.

    Backend object: \c mainBackend.stitchFeedbackTab

    Key slots: \c load_image_qml(path), \c submit_feedback_qml(rating,
    flaw_type, severity), \c train_reward_model_qml(), \c fine_tune_agent_qml()

    Key properties: \c is_training, \c status_text, \c feedback_count,
    \c current_image_path
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.stitchFeedbackTab
                               ? mainBackend.stitchFeedbackTab : null

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Left — annotation canvas
        ColumnLayout {
            Layout.fillHeight: true
            Layout.preferredWidth: parent.width * 0.6
            spacing: 8
            anchors.margins: 12

            RowLayout {
                Layout.margins: 8
                spacing: 8
                Text { text: "Stitch Feedback"; color: Style.text; font.pixelSize: 18; font.bold: true }
                Item { Layout.fillWidth: true }
                Text {
                    text: "Feedback records: " + (tab ? tab.feedback_count : 0)
                    color: Style.mutedText
                }
            }

            // Load image bar
            RowLayout {
                Layout.leftMargin: 8
                Layout.rightMargin: 8
                spacing: 8
                TextField {
                    id: imagePathField
                    Layout.fillWidth: true
                    text: tab ? tab.current_image_path : ""
                    placeholderText: "Load a stitched panorama to annotate..."
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                    color: Style.text
                    readOnly: true
                }
                AppButton {
                    text: "Load Image"
                    onClicked: {
                        if (!tab) return
                        tab.load_image_qml(imagePathField.text)
                    }
                }
            }

            // Annotation canvas placeholder
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 8
                color: "#1a1a1a"
                border.color: Style.border
                radius: 4

                Image {
                    id: annotationImage
                    anchors.fill: parent
                    anchors.margins: 2
                    source: (tab && tab.current_image_path) ? "file://" + tab.current_image_path : ""
                    fillMode: Image.PreserveAspectFit
                    visible: source !== ""
                }

                Text {
                    anchors.centerIn: parent
                    text: "Load a stitched image to begin annotating flaw regions"
                    color: Style.mutedText
                    opacity: 0.5
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                    width: parent.width - 40
                    visible: !(tab && tab.current_image_path)
                }

                // Annotation overlay hint
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottomMargin: 8
                    color: "#aa000000"
                    radius: 4
                    padding: 4
                    visible: annotationImage.visible
                    Text {
                        text: "Drag to mark flaw regions (annotation canvas)"
                        color: "white"
                        font.pixelSize: 11
                    }
                }
            }
        }

        // Divider
        Rectangle { width: 1; Layout.fillHeight: true; color: Style.border }

        // Right — controls + training
        ScrollView {
            Layout.fillHeight: true
            Layout.fillWidth: true

            ColumnLayout {
                width: parent.parent.width
                anchors.margins: 16
                spacing: 14

                Text { text: "Annotation Controls"; color: Style.text; font.pixelSize: 16; font.bold: true }

                GroupBox {
                    title: "Quality Rating"
                    Layout.fillWidth: true
                    ColumnLayout {
                        RowLayout {
                            Text { text: "1"; color: Style.mutedText }
                            Slider {
                                id: ratingSlider
                                Layout.fillWidth: true
                                from: 1; to: 10; stepSize: 1; value: 5
                            }
                            Text { text: "10"; color: Style.mutedText }
                            Text { text: ratingSlider.value.toFixed(0); color: Style.accent; font.bold: true; Layout.preferredWidth: 20 }
                        }
                    }
                }

                GroupBox {
                    title: "Flaw Type"
                    Layout.fillWidth: true
                    ComboBox {
                        id: flawCombo
                        Layout.fillWidth: true
                        model: ["seam_visible", "ghosting", "misalignment", "color_shift", "blur", "distortion", "other"]
                    }
                }

                GroupBox {
                    title: "Severity"
                    Layout.fillWidth: true
                    ComboBox {
                        id: severityCombo
                        Layout.fillWidth: true
                        model: ["minor", "moderate", "severe", "critical"]
                    }
                }

                AppButton {
                    text: "Submit Feedback"
                    Layout.fillWidth: true
                    background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                    enabled: tab ? tab.current_image_path !== "" : false
                    onClicked: if (tab) tab.submit_feedback_qml(ratingSlider.value, flawCombo.currentText, severityCombo.currentText)
                }

                Rectangle { height: 1; Layout.fillWidth: true; color: Style.border }

                Text { text: "Model Training"; color: Style.text; font.pixelSize: 14; font.bold: true }

                Text {
                    text: tab ? tab.status_text : "Ready."
                    color: Style.mutedText
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }

                ProgressBar { Layout.fillWidth: true; visible: tab ? tab.is_training : false; indeterminate: true }

                AppButton {
                    text: "Train Reward Model"
                    Layout.fillWidth: true
                    enabled: !(tab && tab.is_training)
                    onClicked: if (tab) tab.train_reward_model_qml()
                }

                AppButton {
                    text: "Fine-tune DRL Agent"
                    Layout.fillWidth: true
                    enabled: !(tab && tab.is_training)
                    onClicked: if (tab) tab.fine_tune_agent_qml()
                }

                Item { Layout.fillHeight: true }
            }
        }
    }
}
