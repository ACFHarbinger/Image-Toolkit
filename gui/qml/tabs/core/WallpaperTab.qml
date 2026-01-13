import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Text {
            text: "Wallpaper Manager"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        // --- Monitor Visualization ---
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 300
            color: Style.secondaryBackground
            radius: Style.borderRadius
            border.color: Style.border

            RowLayout {
                anchors.centerIn: parent
                spacing: 20
                
                Repeater {
                    id: monitorRepeater
                    model: ListModel { id: monitorModel }
                    delegate: Rectangle {
                        width: 200; height: 120
                        color: Style.background
                        border.color: model.is_primary ? Style.accent : Style.border
                        border.width: 2
                        
                        Text { 
                            anchors.centerIn: parent
                            text: model.name + (model.is_primary ? "\n(Main)" : "")
                            color: Style.text
                            horizontalAlignment: Text.AlignHCenter 
                        }

                        DropArea {
                            anchors.fill: parent
                            onDropped: {
                                if (drop.hasUrls) {
                                    var path = drop.urls[0].toString().replace("file://", "")
                                    if (mainBackend && mainBackend.wallpaperTab) {
                                         // Target specific monitor by name
                                         mainBackend.wallpaperTab.set_wallpaper_qml(path, model.name)
                                    }
                                }
                            }
                        }
                    }
                }
                
                Connections {
                    target: (mainBackend && mainBackend.wallpaperTab) ? mainBackend.wallpaperTab : null
                    function onQml_monitors_changed(monitors) {
                        monitorModel.clear()
                        for (var i = 0; i < monitors.length; i++) {
                            monitorModel.append(monitors[i])
                        }
                    }
                }
                
                Component.onCompleted: {
                    if (mainBackend && mainBackend.wallpaperTab) {
                        mainBackend.wallpaperTab.request_monitors_qml()
                    }
                }
            }
            
            Text {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.margins: 10
                text: "Drop images here to set wallpaper"
                color: Style.mutedText
                font.italic: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 20

            // --- Slideshow Controls ---
            GroupBox {
                title: "Slideshow Settings"
                Layout.fillWidth: true
                
                GridLayout {
                    columns: 2
                    anchors.fill: parent
                    
                    Label { text: "Interval (min):"; color: Style.text }
                    SpinBox { from: 1; to: 1440; value: 5 }
                    
                    Label { text: "Style:"; color: Style.text }
                    ComboBox { model: ["Fill", "Fit", "Stretch", "Tile", "Center"]; Layout.fillWidth: true }
                    
                    CheckBox { text: "Random Order"; palette.windowText: Style.text }
                    CheckBox { text: "Include Subdirectories"; palette.windowText: Style.text }
                }
            }

            // --- Status & Actions ---
            ColumnLayout {
                Layout.preferredWidth: 250
                spacing: 10

                AppButton {
                    text: "Start Slideshow"
                    Layout.fillWidth: true
                    background: Rectangle { color: "#2ecc71"; radius: Style.borderRadius }
                    onClicked: {
                        if (mainBackend && mainBackend.wallpaperTab) {
                            mainBackend.wallpaperTab.start_slideshow() // Existing slot
                        }
                    }
                }

                AppButton {
                    text: "Stop Slideshow"
                    Layout.fillWidth: true
                    background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                    onClicked: {
                         if (mainBackend && mainBackend.wallpaperTab) {
                            mainBackend.wallpaperTab.stop_slideshow() // Existing slot
                        }
                    }
                }

                AppButton {
                    text: "Open Slideshow Window"
                    Layout.fillWidth: true
                    background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                    onClicked: {
                        if (mainBackend && mainBackend.wallpaperTab) {
                             mainBackend.wallpaperTab.start_window_slideshow()
                        }
                    }
                }

                AppButton {
                    text: "Clear All Monitor Queues"
                    Layout.fillWidth: true
                    onClicked: {
                        // TODO: Add backend slot for clearing queues if not exists
                    }
                }
            }
        }

        // --- Recent Wallpapers Gallery ---
        Text { text: "Recently Used:"; color: Style.text; font.bold: true }
        GalleryView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: ListModel {}
        }
    }
}
