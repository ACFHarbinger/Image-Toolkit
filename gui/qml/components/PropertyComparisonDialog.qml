/*!
    \qmltype PropertyComparisonDialog
    \inqmlmodule ImageToolkit.Components
    \brief Tabular dialog comparing metadata properties across selected images.

    PropertyComparisonDialog displays a scrollable table with one column per
    image and one row per metadata property (file size, dimensions, format,
    mode, timestamps, path).  Cells that differ across images are highlighted
    in amber.

    The \l model is a list of objects where each object maps property names to
    values — typically the list returned by the backend's \c compare_properties()
    slot.

    \qmlproperty list<var> PropertyComparisonDialog::model
    List of property maps.  Each element represents one image; keys are
    property names and values are the property values (strings).

    \qmlsignal PropertyComparisonDialog::closed()
    Emitted when the user dismisses the dialog.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"

Rectangle {
    id: root

    property var model: []
    signal closed()

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 700
    implicitHeight: 540

    readonly property var _rowKeys: [
        "File Size", "Width", "Height", "Format", "Mode",
        "Last Modified", "Created", "Path"
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Title bar
        RowLayout {
            Layout.fillWidth: true
            Text { text: "Image Property Comparison"; color: Style.text; font.pixelSize: 18; font.bold: true; Layout.fillWidth: true }
            Button {
                text: "Close"
                onClicked: root.closed()
                background: Rectangle { color: parent.hovered ? Style.border : "transparent"; border.color: Style.border; radius: 4 }
                contentItem: Text { text: parent.text; color: Style.text; horizontalAlignment: Text.AlignHCenter }
            }
        }

        // Table
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Column {
                width: parent.width

                // Header row
                Row {
                    width: parent.width
                    height: 36

                    Rectangle {
                        width: 130; height: 36
                        color: Style.secondaryBackground
                        border.color: Style.border
                        Text { anchors.centerIn: parent; text: "Property"; color: Style.accent; font.bold: true; font.pixelSize: 12 }
                    }

                    Repeater {
                        model: root.model.length
                        Rectangle {
                            width: Math.max(130, (root.width - 130) / Math.max(1, root.model.length))
                            height: 36
                            color: Style.secondaryBackground
                            border.color: Style.border
                            Text {
                                anchors.centerIn: parent
                                text: "Image " + (index + 1)
                                color: Style.text
                                font.bold: true
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                width: parent.width - 8
                                horizontalAlignment: Text.AlignHCenter
                            }
                        }
                    }
                }

                // Data rows
                Repeater {
                    model: root._rowKeys
                    delegate: Row {
                        width: parent.width
                        height: 32

                        property string propKey: modelData

                        Rectangle {
                            width: 130; height: 32
                            color: index % 2 === 0 ? Style.secondaryBackground : "transparent"
                            border.color: Style.border
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left; anchors.leftMargin: 8
                                text: propKey; color: Style.text; font.pixelSize: 11
                                elide: Text.ElideRight; width: parent.width - 12
                            }
                        }

                        Repeater {
                            model: root.model.length
                            delegate: Rectangle {
                                property string val: root.model[index] ? (root.model[index][propKey] || "—") : "—"
                                property bool differs: {
                                    if (root.model.length < 2) return false
                                    var v0 = root.model[0] ? (root.model[0][propKey] || "") : ""
                                    return val !== v0
                                }
                                width: Math.max(130, (root.width - 130) / Math.max(1, root.model.length))
                                height: 32
                                color: differs ? "#2a2000" : (parent.index % 2 === 0 ? Style.secondaryBackground : "transparent")
                                border.color: differs ? "#f0a000" : Style.border
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left; anchors.leftMargin: 6
                                    text: val
                                    color: differs ? "#f0c040" : Style.text
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    width: parent.width - 10
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
