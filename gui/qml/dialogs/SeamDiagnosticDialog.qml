/*!
    \qmltype SeamDiagnosticDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief §2.4A/C HITL checkpoint 4.6 — seam registration inspector.

    SeamDiagnosticDialog surfaces per-seam diagnostic data:
    \list
      \li \c post_warp_diff coloured green/amber/red (invisible/normal/visible).
      \li Single-pose escalation badge.
      \li ±50 px seam zone crop thumbnail.
      \li "Force single-pose" / "Force blend" override checkboxes per seam.
      \li §2.11B — interactive waypoint placement on the canvas preview.
    \endlist

    Backend (\l backend) must expose:
    \list
      \li \c canvasImage — string URL of the canvas composite.
      \li \c seams — list of objects with \c index, \c postWarpDiff, \c singlePose (bool),
          \c cropImage (URL), \c forceSinglePose (bool), \c forceBlend (bool).
      \li \c setSeamOverride(seamIdx, forceSinglePose, forceBlend) — slot.
      \li \c addWaypoint(seamIdx, xCanvas, yCanvas) — slot.
      \li \c accept() — slot.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var SeamDiagnosticDialog::backend
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
    property int _selectedSeam: 0
    property bool _waypointMode: false

    signal accepted()
    signal cancelled()

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 920
    implicitHeight: 660

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        // Left: canvas preview + waypoint mode
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8

            RowLayout {
                Text { text: "Seam Diagnostic Inspector"; color: Style.text; font.pixelSize: 18; font.bold: true; Layout.fillWidth: true }
                CheckBox {
                    id: waypointChk
                    text: "Add Waypoints"
                    palette.windowText: Style.text
                    onCheckedChanged: root._waypointMode = checked
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#000000"
                border.color: Style.border

                Image {
                    id: canvasImg
                    anchors.fill: parent
                    source: backend ? backend.canvasImage : ""
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: root._waypointMode ? Qt.CrossCursor : Qt.ArrowCursor
                    enabled: root._waypointMode
                    onClicked: {
                        if (!backend || root._selectedSeam < 0) return
                        var xc = (mouse.x - (canvasImg.width - canvasImg.paintedWidth) / 2)
                        var yc = (mouse.y - (canvasImg.height - canvasImg.paintedHeight) / 2)
                        backend.addWaypoint(root._selectedSeam, xc, yc)
                    }
                }
            }

            // Seam crop thumbnail for selected seam
            RowLayout {
                visible: backend && backend.seams.length > 0
                Text { text: "Seam " + root._selectedSeam + " zone (±50 px):"; color: Style.mutedText; font.pixelSize: 11 }
                Rectangle {
                    width: 200; height: 100
                    color: "#000000"
                    border.color: Style.border
                    Image {
                        anchors.fill: parent
                        source: backend && backend.seams.length > root._selectedSeam ? backend.seams[root._selectedSeam].cropImage : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                }
            }
        }

        // Right: seam list + controls
        ColumnLayout {
            Layout.preferredWidth: 310
            Layout.fillHeight: true
            spacing: 8

            Text { text: "Seams (" + (backend ? backend.seams.length : 0) + ")"; color: Style.text; font.bold: true }

            ListView {
                id: seamList
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: backend ? backend.seams : []
                clip: true
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 80
                    color: root._selectedSeam === index ? Qt.rgba(0.44, 0.54, 0.85, 0.12) : (index % 2 === 0 ? Style.secondaryBackground : "transparent")
                    border.color: root._selectedSeam === index ? Style.accent : Style.border
                    radius: 4

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 4

                        RowLayout {
                            Text { text: "Seam " + index; color: Style.text; font.bold: true; Layout.fillWidth: true }
                            Rectangle {
                                visible: modelData.singlePose
                                color: "#8e44ad"; radius: 3; padding: 3
                                Text { text: "single-pose"; color: "white"; font.pixelSize: 9 }
                            }
                            Rectangle {
                                color: modelData.postWarpDiff < 8 ? "#27ae60" : modelData.postWarpDiff < 16 ? "#f0a000" : "#e74c3c"
                                radius: 3; padding: 3
                                Text { text: "Δ" + modelData.postWarpDiff.toFixed(1); color: "white"; font.pixelSize: 9 }
                            }
                        }

                        RowLayout {
                            CheckBox {
                                id: spChk
                                text: "Force single-pose"
                                palette.windowText: Style.text
                                font.pixelSize: 10
                                checked: modelData.forceSinglePose
                                onCheckedChanged: if (backend && checked) { blendChk.checked = false; backend.setSeamOverride(index, true, false) }
                            }
                            CheckBox {
                                id: blendChk
                                text: "Force blend"
                                palette.windowText: Style.text
                                font.pixelSize: 10
                                checked: modelData.forceBlend
                                onCheckedChanged: if (backend && checked) { spChk.checked = false; backend.setSeamOverride(index, false, true) }
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: root._selectedSeam = index
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                AppButton {
                    text: "Cancel"
                    background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                    onClicked: { if (backend) backend.cancel(); root.cancelled() }
                }
                AppButton {
                    text: "Accept"
                    background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                    onClicked: { if (backend) backend.accept(); root.accepted() }
                }
            }
        }
    }
}
