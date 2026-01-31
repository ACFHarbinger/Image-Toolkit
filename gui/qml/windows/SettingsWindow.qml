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
                model: ["General", "User Interface", "Tab Configs", "Database", "Model APIs", "Web Crawlers", "Cloud Sync"]
                
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
                id: stackLayout
                currentIndex: categoryList.currentIndex
                Layout.fillWidth: true
                Layout.fillHeight: true

                // 1. General (Profiles)
                ColumnLayout {
                    spacing: 20
                    GroupBox {
                        title: "Application Profile"
                        Layout.fillWidth: true
                        
                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 10
                            
                            RowLayout {
                                spacing: 15
                                Label { text: "Active Profile:"; color: Style.text }
                                ComboBox { 
                                    id: profileCombo
                                    model: backend.profileList
                                    Layout.fillWidth: true 
                                }
                                AppButton { 
                                    text: "Load"
                                    onClicked: backend.loadProfile(profileCombo.currentText)
                                    Layout.preferredWidth: 80
                                }
                                AppButton { 
                                    text: "Delete"
                                    onClicked: backend.deleteProfile(profileCombo.currentText)
                                    Layout.preferredWidth: 80
                                }
                            }
                            
                            Rectangle { height: 1; Layout.fillWidth: true; color: Style.border }
                            
                            RowLayout {
                                spacing: 15
                                Label { text: "Save Current State As:"; color: Style.text }
                                TextField { 
                                    id: newProfileName
                                    placeholderText: "New Profile Name"
                                    Layout.fillWidth: true
                                    color: Style.text
                                    background: Rectangle { color: Style.inputBackground; radius: 4; border.color: Style.inputBorder }
                                }
                                AppButton { 
                                    text: "Save"
                                    onClicked: backend.saveCurrentAsProfile(newProfileName.text, themeCombo.currentText)
                                    Layout.preferredWidth: 80
                                }
                            }
                        }
                    }
                    
                    GroupBox {
                        title: "Account"
                        Layout.fillWidth: true
                        RowLayout {
                            Label { text: "Logged in as:"; color: Style.text }
                            Text { text: backend.accountName; font.bold: true; color: Style.accent }
                        }
                    }
                }

                // 2. User Interface (Here we put Themes)
                ColumnLayout {
                    spacing: 20
                    GroupBox {
                        title: "Appearance"
                        Layout.fillWidth: true
                        RowLayout {
                            Label { text: "Theme:"; color: Style.text }
                            ComboBox { 
                                id: themeCombo
                                model: ["Dark", "Light"]
                                Layout.fillWidth: true 
                                onCurrentTextChanged: backend.setTheme(currentText)
                                Component.onCompleted: currentIndex = find(backend.currentTheme === "light" ? "Light" : "Dark")
                            }
                        }
                    }
                }
                
                // 3. Tab Configs (Complex Logic)
                ColumnLayout {
                    spacing: 15
                    
                    RowLayout {
                        Label { text: "Select Tab:"; color: Style.text; Layout.preferredWidth: 100 }
                        ComboBox {
                            model: backend.tabList
                            Layout.fillWidth: true
                            onCurrentTextChanged: backend.setTabSelection(currentText)
                        }
                    }
                    
                    RowLayout {
                        Label { text: "Saved Configs:"; color: Style.text; Layout.preferredWidth: 100 }
                        ComboBox {
                            id: configSelector
                            model: backend.configListForTab
                            Layout.fillWidth: true
                            onCurrentTextChanged: backend.setConfigSelection(currentText)
                        }
                        AppButton {
                            text: "Apply to Active Tab"
                            onClicked: backend.setConfigForTab(configSelector.currentText)
                        }
                        AppButton {
                            text: "Delete"
                            onClicked: backend.deleteCurrentConfig(configSelector.currentText)
                            background: Rectangle { color: "#e74c3c"; radius: 4 }
                        }
                    }
                    
                    Label { text: "Configuration (JSON):"; color: Style.text }
                    
                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        TextArea {
                            id: jsonEditor
                            text: backend.configContent
                            color: Style.text
                            font.family: "Monospace"
                            background: Rectangle { color: Style.inputBackground; border.color: Style.inputBorder }
                        }
                    }
                    
                    RowLayout {
                        TextField {
                            id: newConfigName
                            placeholderText: "Config Name (for saving)"
                            Layout.fillWidth: true
                            color: Style.text
                            background: Rectangle { color: Style.inputBackground; radius: 4; border.color: Style.inputBorder }
                        }
                        AppButton {
                            text: "Save/Create Config"
                            onClicked: backend.createConfigFromEditor(newConfigName.text, jsonEditor.text)
                        }
                    }
                }
                
                // Placeholders for others
                Repeater {
                    model: 4
                    Item {
                        Text { text: "Settings for " + categoryList.model[index + 3] + " are coming soon."; color: Style.text; opacity: 0.5; anchors.centerIn: parent }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // Footer Actions
            RowLayout {
                Layout.fillWidth: true
                spacing: 15
                AppButton { text: "Reset to Defaults"; Layout.preferredWidth: 150; onClicked: backend.resetToDefaults() }
                
                AppButton { 
                    text: "Relaunch App"
                    Layout.preferredWidth: 150
                    background: Rectangle { color: "#f1c40f"; radius: 6 }
                    onClicked: backend.refreshApplication()
                }
                
                Item { Layout.fillWidth: true }
                AppButton { text: "Close"; Layout.preferredWidth: 100; onClicked: window.close() }
                AppButton { 
                    text: "Apply All Settings"
                    Layout.preferredWidth: 150
                    background: Rectangle { color: Style.accent; radius: 6 }
                    onClicked: backend.applySettings()
                }
            }
        }
    }
}

