import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import ".."

ApplicationWindow {
    id: window
    width: 900
    height: 700
    visible: true
    title: "Application Settings"
    color: Style.background

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Sidebar Categories
        Rectangle {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            color: Style.secondaryBackground
            border.color: Style.border
            border.width: 0
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Style.border }

            ListView {
                id: categoryList
                anchors.fill: parent
                anchors.margins: 15
                spacing: 5
                model: ["General", "User Interface", "Database", "Model APIs", "Web Crawlers", "Cloud Sync"]
                
                delegate: ItemDelegate {
                    width: parent.width
                    height: 45
                    background: Rectangle {
                        color: categoryList.currentIndex === index ? Style.accent : "transparent"
                        opacity: categoryList.currentIndex === index ? 0.15 : 1.0
                        radius: 6
                        Rectangle {
                            width: 3; height: parent.height * 0.6; anchors.left: parent.left; 
                            anchors.verticalCenter: parent.verticalCenter; color: Style.accent; 
                            visible: categoryList.currentIndex === index
                        }
                    }
                    contentItem: Text {
                        text: modelData
                        color: categoryList.currentIndex === index ? Style.accent : Style.text
                        font.bold: categoryList.currentIndex === index
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 15
                    }
                    onClicked: categoryList.currentIndex = index
                }
            }
        }

        // Main Content Area
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            anchors.margins: 30
            spacing: 25

            Text {
                text: categoryList.model[categoryList.currentIndex]
                font.pixelSize: 24
                font.bold: true
                color: Style.text
            }

            StackLayout {
                currentIndex: categoryList.currentIndex
                Layout.fillWidth: true
                Layout.fillHeight: true

                // General
                ColumnLayout {
                    spacing: 20
                    GroupBox {
                        title: "Application Profile"
                        Layout.fillWidth: true
                        RowLayout {
                            spacing: 15
                            ComboBox { model: ["Default", "Work", "Personal"]; Layout.fillWidth: true }
                            AppButton { text: "Save As"; Layout.preferredWidth: 100 }
                            AppButton { text: "Delete"; Layout.preferredWidth: 80 }
                        }
                    }
                    GroupBox {
                        title: "Startup"
                        Layout.fillWidth: true
                        CheckBox { text: "Launch at system startup"; palette.windowText: Style.text }
                        CheckBox { text: "Check for updates automatically"; palette.windowText: Style.text }
                    }
                }

                // UI
                ColumnLayout {
                    spacing: 20
                    GroupBox {
                        title: "Appearance"
                        Layout.fillWidth: true
                        RowLayout {
                            Label { text: "Theme:"; color: Style.text }
                            ComboBox { model: ["System Default", "Dark Mode", "Light Mode"]; Layout.fillWidth: true }
                        }
                    }
                }
                
                // Placeholder for other categories
                Repeater {
                    model: 4
                    Item {
                        Text { text: "Settings for " + categoryList.model[index + 2] + " are coming soon."; color: Style.text; opacity: 0.5; anchors.centerIn: parent }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // Footer Actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 15
                AppButton { text: "Reset to Defaults"; Layout.preferredWidth: 150 }
                Item { Layout.fillWidth: true }
                AppButton { text: "Cancel"; Layout.preferredWidth: 100 }
                AppButton { 
                    text: "Apply Settings"
                    Layout.preferredWidth: 150
                    background: Rectangle { color: Style.accent; radius: 6 }
                }
            }
        }
    }
}

