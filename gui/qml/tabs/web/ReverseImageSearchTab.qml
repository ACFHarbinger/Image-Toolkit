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
            text: "Reverse Image Search"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            spacing: 15
            Label { text: "Scan Directory:"; color: Style.text }
            TextField {
                id: scanDir
                Layout.fillWidth: true
                text: mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.scan_dir_path : ""
                placeholderText: "Select directory to scan for source images..."
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                color: Style.text
                readOnly: true
            }
            AppButton { 
                text: "Browse"
                Layout.preferredWidth: 80 
                onClicked: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.browse_scan_directory()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Local Gallery
            ColumnLayout {
                Layout.preferredWidth: parent.width * 0.4
                Layout.fillHeight: true
                Text { text: "1. Select Source Image:"; color: Style.text; font.bold: true }
                
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    radius: Style.borderRadius
                    border.color: Style.border
                    clip: true

                    GalleryView {
                        anchors.fill: parent
                        model: mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.gallery_model : null
                        onItemClicked: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.handle_image_selection(path)
                        onItemDoubleClicked: if (mainBackend) mainBackend.open_preview(path)
                    }
                }
            }

            Rectangle { width: 1; Layout.fillHeight: true; color: Style.border; Layout.leftMargin: 10; Layout.rightMargin: 10 }

            // Results Area
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10
                Text { text: "2. Search Options & Results:"; color: Style.text; font.bold: true }
                
                GroupBox {
                    title: "Search Configuration"
                    Layout.fillWidth: true
                    GridLayout {
                        columns: 2
                        columnSpacing: 10
                        
                        RowLayout {
                            CheckBox { 
                                id: filterResCheck
                                text: "Filter Res"
                                palette.windowText: Style.text 
                                checked: mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.filter_res : false
                                onCheckedChanged: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.filter_res = checked
                            }
                            TextField {
                                placeholderText: "W"
                                Layout.preferredWidth: 50
                                text: mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.min_w : "1920"
                                onTextChanged: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.min_w = text
                                enabled: filterResCheck.checked
                            }
                            TextField {
                                placeholderText: "H"
                                Layout.preferredWidth: 50
                                text: mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.min_h : "1080"
                                onTextChanged: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.min_h = text
                                enabled: filterResCheck.checked
                            }
                        }

                        ComboBox { 
                            id: browserSelect
                            model: ["brave", "chrome", "firefox", "edge"]
                            currentIndex: find(mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.browser : "brave")
                            onCurrentTextChanged: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.browser = currentText
                        }
                        
                        ComboBox {
                            id: modeSelect
                            model: ["All", "Visual matches", "Exact matches"]
                            currentIndex: find(mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.search_mode : "All")
                            onCurrentTextChanged: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.search_mode = currentText
                        }

                        CheckBox { 
                            text: "Keep Open"
                            palette.windowText: Style.text 
                            checked: mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.keep_open : true
                            onCheckedChanged: if (mainBackend && mainBackend.reverseSearchTab) mainBackend.reverseSearchTab.keep_open = checked
                        }
                    }
                }

                AppButton {
                    text: (mainBackend && mainBackend.reverseSearchTab && mainBackend.reverseSearchTab.is_searching) ? "Cancel Search" : "Start Reverse Search"
                    Layout.fillWidth: true
                    background: Rectangle { color: (parent.text == "Cancel Search" ? "#e74c3c" : Style.accent); radius: Style.borderRadius }
                    enabled: mainBackend && mainBackend.reverseSearchTab ? (mainBackend.reverseSearchTab.is_searching || mainBackend.reverseSearchTab.has_selection) : false
                    onClicked: {
                        if (mainBackend && mainBackend.reverseSearchTab) {
                            if (mainBackend.reverseSearchTab.is_searching)
                                mainBackend.reverseSearchTab.cancel_search()
                            else
                                mainBackend.reverseSearchTab.start_search()
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    radius: Style.borderRadius
                    border.color: Style.border
                    clip: true
                    
                    ScrollView {
                        anchors.fill: parent
                        Text {
                            padding: 10
                            text: mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.status_text : "Search results or status will appear here."
                            color: Style.text
                            wrapMode: Text.Wrap
                        }
                    }
                }
                
                Text {
                    text: "Selected: " + (mainBackend && mainBackend.reverseSearchTab ? mainBackend.reverseSearchTab.selected_image_filename : "None")
                    color: Style.mutedText
                    font.pixelSize: 11
                }
            }
        }
    }
}
