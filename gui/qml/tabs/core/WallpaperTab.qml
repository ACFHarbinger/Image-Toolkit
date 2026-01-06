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
                
                // Monitor 1 Placeholder
                Rectangle {
                    width: 200; height: 120
                    color: Style.background
                    border.color: Style.accent
                    border.width: 2
                    Text { anchors.centerIn: parent; text: "Monitor 1\n(Main)"; color: Style.text; horizontalAlignment: Text.AlignHCenter }
                }

                // Monitor 2 Placeholder
                Rectangle {
                    width: 200; height: 120
                    color: Style.background
                    border.color: Style.border
                    Text { anchors.centerIn: parent; text: "Monitor 2"; color: Style.text; horizontalAlignment: Text.AlignHCenter }
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
                }

                AppButton {
                    text: "Stop Slideshow"
                    Layout.fillWidth: true
                    background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                }

                AppButton {
                    text: "Clear All Monitor Queues"
                    Layout.fillWidth: true
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
