/*!
    \qmltype SystemDisplaySubtab
    \inqmlmodule ImageToolkit.Tabs.Core.Common
    \brief System-level wallpaper management sub-tab.

    SystemDisplaySubtab scans connected monitors and lets the user assign
    wallpaper images and a display style to each one.

    Backend object: \c mainBackend.wallpaperTab

    \qmlsignal SystemDisplaySubtab::qml_monitors_changed
    Forwarded from \c wallpaperTab.qml_monitors_changed — fires when the
    detected monitor list changes.

    \qmlsignal SystemDisplaySubtab::qml_status_changed(string status)
    Forwarded status updates from the wallpaper worker.

    Key slots: \c apply_wallpaper_qml(), \c stop_slideshow_qml(),
    \c browse_wallpaper_qml(monitorId)
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../../components"
import "../../../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.wallpaperTab ? mainBackend.wallpaperTab : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "System Display(s)"
            color: Style.text
            font.pixelSize: 20
            font.bold: true
        }

        // Monitor grid
        GroupBox {
            title: "Monitors"
            Layout.fillWidth: true
            Layout.preferredHeight: 260

            Rectangle {
                anchors.fill: parent
                anchors.margins: 8
                color: Style.secondaryBackground
                border.color: Style.border
                radius: 4

                GridView {
                    id: monitorGrid
                    anchors.fill: parent
                    anchors.margins: 8
                    cellWidth: 200
                    cellHeight: 130
                    model: tab ? tab.monitors_model : null
                    clip: true

                    delegate: Rectangle {
                        width: 190
                        height: 120
                        color: Style.secondaryBackground
                        border.color: Style.border
                        border.width: 2
                        radius: 6

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 4

                            Text {
                                text: model.name || ("Monitor " + (index + 1))
                                color: Style.text
                                font.bold: true
                                Layout.alignment: Qt.AlignHCenter
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                color: model.image_path ? "transparent" : "#1a1a1a"
                                radius: 4
                                border.color: Style.border

                                Image {
                                    anchors.fill: parent
                                    source: model.image_path ? "file://" + model.image_path : ""
                                    fillMode: Image.PreserveAspectCrop
                                    visible: model.image_path !== ""
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: "No wallpaper"
                                    color: Style.mutedText
                                    font.pixelSize: 10
                                    visible: !model.image_path
                                }
                            }

                            AppButton {
                                text: "Set Wallpaper"
                                Layout.fillWidth: true
                                Layout.preferredHeight: 24
                                onClicked: if (tab) tab.browse_wallpaper_qml(model.monitor_id)
                            }
                        }
                    }
                }
            }
        }

        // Style + options
        GroupBox {
            title: "Display Settings"
            Layout.fillWidth: true

            GridLayout {
                columns: 2
                columnSpacing: 16
                rowSpacing: 8

                Label { text: "Wallpaper Style:"; color: Style.text }
                ComboBox {
                    id: styleCombo
                    model: ["fill", "fit", "stretch", "center", "tile", "span"]
                    onCurrentTextChanged: if (tab) tab.wallpaper_style = currentText
                }

                CheckBox {
                    id: randomizeCheck
                    text: "Randomize order in slideshow"
                    palette.windowText: Style.text
                    Layout.columnSpan: 2
                    onCheckedChanged: if (tab) tab.randomize = checked
                }
            }
        }

        // Status + buttons
        Text {
            text: tab ? tab.qml_status : "Ready."
            color: Style.mutedText
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            AppButton {
                text: "Apply Wallpaper"
                Layout.fillWidth: true
                background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                onClicked: if (tab) tab.apply_wallpaper_qml()
            }
            AppButton {
                text: "Stop Slideshow"
                Layout.fillWidth: true
                background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                onClicked: if (tab) tab.stop_slideshow_qml()
            }
        }
    }
}
