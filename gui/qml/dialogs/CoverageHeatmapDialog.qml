/*!
    \qmltype CoverageHeatmapDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief Canvas coverage heatmap viewer.

    CoverageHeatmapDialog shows a colour-coded vertical bar on the right-hand
    side indicating how many source frames cover each row of the output canvas.
    Green = 2+, amber = 1, red = 0 (gap).  The left side shows the canvas
    preview image.  Used as part of the coverage review HITL checkpoint.

    Backend (\l backend) must expose:
    \list
      \li \c canvasImage — string URL of the canvas composite.
      \li \c coverageBars — list of objects with \c count (int) and \c heightFrac
          (real 0–1) roles, one per canvas row group.
      \li \c gapCount — int, number of uncovered rows.
      \li \c accept() — slot.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var CoverageHeatmapDialog::backend
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
    implicitWidth: 700
    implicitHeight: 560

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text { text: "Coverage Heatmap"; color: Style.text; font.pixelSize: 18; font.bold: true }

        Text {
            text: backend && backend.gapCount > 0
                  ? "⚠  " + backend.gapCount + " uncovered row(s) — canvas will have gaps."
                  : "✓  Full canvas coverage."
            color: backend && backend.gapCount > 0 ? "#f0a000" : "#27ae60"
            font.pixelSize: 13
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // Canvas preview
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

            // Coverage bar
            Rectangle {
                width: 24
                Layout.fillHeight: true
                color: Style.secondaryBackground
                border.color: Style.border
                clip: true

                Column {
                    anchors.fill: parent
                    Repeater {
                        model: backend ? backend.coverageBars : []
                        Rectangle {
                            width: parent.width
                            height: modelData.heightFrac * parent.parent.height
                            color: modelData.count >= 2 ? "#3cbe50"
                                 : modelData.count === 1 ? "#dc8c28"
                                 : "#c83232"
                        }
                    }
                }
            }

            // Legend
            ColumnLayout {
                Layout.preferredWidth: 100
                spacing: 8
                Text { text: "Legend"; color: Style.text; font.bold: true }
                Row { spacing: 6; Rectangle { width: 14; height: 14; color: "#3cbe50"; radius: 2 }; Text { text: "2+ frames"; color: Style.text; font.pixelSize: 11 } }
                Row { spacing: 6; Rectangle { width: 14; height: 14; color: "#dc8c28"; radius: 2 }; Text { text: "1 frame"; color: Style.text; font.pixelSize: 11 } }
                Row { spacing: 6; Rectangle { width: 14; height: 14; color: "#c83232"; radius: 2 }; Text { text: "No coverage"; color: Style.text; font.pixelSize: 11 } }
                Item { Layout.fillHeight: true }
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
                text: "Accept & Continue"
                background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                onClicked: { if (backend) backend.accept(); root.accepted() }
            }
        }
    }
}
