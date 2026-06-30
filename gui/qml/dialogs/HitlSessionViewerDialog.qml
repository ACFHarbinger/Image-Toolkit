/*!
    \qmltype HitlSessionViewerDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL session browser — load, inspect, and export saved sessions.

    HitlSessionViewerDialog lists \c .json session files from the HITL
    sessions directory, shows the checkpoints reached and annotations stored,
    and allows the user to load a session for re-inspection or export it.

    Backend (\l backend) must expose:
    \list
      \li \c sessions — list of objects with \c name, \c timestamp,
          \c checkpointCount roles.
      \li \c selectedSession — int index (read/write).
      \li \c sessionDetail — string (JSON or human-readable) of the selected session.
      \li \c checkpointLabels — list of strings for the selected session.
      \li \c refresh() — slot to rescan the sessions directory.
      \li \c loadSession(index) — slot.
      \li \c exportSession(index, path) — slot.
      \li \c deleteSession(index) — slot.
    \endlist

    \qmlproperty var HitlSessionViewerDialog::backend
    Session manager backend.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"
import "../components"

Rectangle {
    id: root

    property var backend: null
    signal closed()

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 800
    implicitHeight: 540

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Title row
        RowLayout {
            Layout.fillWidth: true
            Text { text: "HITL Session Viewer"; color: Style.text; font.pixelSize: 18; font.bold: true; Layout.fillWidth: true }
            AppButton { text: "Refresh"; Layout.preferredWidth: 90; onClicked: if (backend) backend.refresh() }
            AppButton { text: "Close"; Layout.preferredWidth: 80; onClicked: root.closed() }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // Session list
            ColumnLayout {
                Layout.preferredWidth: 280
                Layout.fillHeight: true
                spacing: 6

                Text { text: "Saved Sessions"; color: Style.text; font.bold: true }

                ListView {
                    id: sessionList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: backend ? backend.sessions : []
                    clip: true
                    delegate: ItemDelegate {
                        width: ListView.view.width
                        highlighted: backend && backend.selectedSession === index
                        background: Rectangle {
                            color: parent.highlighted ? Qt.rgba(0.44, 0.54, 0.85, 0.15) : "transparent"
                            border.color: parent.highlighted ? Style.accent : "transparent"
                            radius: 4
                        }
                        contentItem: ColumnLayout {
                            spacing: 2
                            Text { text: modelData.name; color: Style.text; font.pixelSize: 12; font.bold: true; elide: Text.ElideRight }
                            Text { text: modelData.timestamp + "  |  " + modelData.checkpointCount + " checkpoint(s)"; color: Style.mutedText; font.pixelSize: 10 }
                        }
                        onClicked: if (backend) backend.selectedSession = index
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    AppButton {
                        text: "Load"
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                        enabled: backend && backend.selectedSession >= 0
                        onClicked: if (backend) backend.loadSession(backend.selectedSession)
                    }
                    AppButton {
                        text: "Delete"
                        Layout.fillWidth: true
                        background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                        enabled: backend && backend.selectedSession >= 0
                        onClicked: if (backend) backend.deleteSession(backend.selectedSession)
                    }
                }
            }

            // Detail pane
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 6

                Text { text: "Session Detail"; color: Style.text; font.bold: true }

                // Checkpoints reached
                GroupBox {
                    title: "Checkpoints"
                    Layout.fillWidth: true
                    Flow {
                        spacing: 6
                        Repeater {
                            model: backend ? backend.checkpointLabels : []
                            Rectangle {
                                color: "#27ae60"; radius: 4; padding: 4
                                Text { text: modelData; color: "white"; font.pixelSize: 10 }
                            }
                        }
                    }
                }

                // Raw JSON / text
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    border.color: Style.border
                    radius: 4

                    ScrollView {
                        anchors.fill: parent
                        TextArea {
                            readOnly: true
                            text: backend ? (backend.sessionDetail || "Select a session to view details.") : ""
                            color: Style.text
                            font.family: "Monospace"
                            font.pixelSize: 11
                            background: null
                            wrapMode: TextEdit.Wrap
                        }
                    }
                }

                AppButton {
                    text: "Export Session…"
                    Layout.alignment: Qt.AlignRight
                    enabled: backend && backend.selectedSession >= 0
                    onClicked: if (backend) backend.exportSession(backend.selectedSession, "")
                }
            }
        }
    }
}
