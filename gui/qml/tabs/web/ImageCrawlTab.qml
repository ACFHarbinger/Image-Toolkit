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
            text: "Web Image Crawler"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 20

            ColumnLayout {
                Layout.preferredWidth: 350
                spacing: 15

                GroupBox {
                    title: "Crawler Type"
                    Layout.fillWidth: true
                    ComboBox {
                        id: crawlerType
                        model: [
                            "General Web Crawler",
                            "Image Board Crawler (Danbooru API)",
                            "Image Board Crawler (Gelbooru API)",
                            "Image Board Crawler (Sankaku Complex API)"
                        ]
                        Layout.fillWidth: true
                        currentIndex: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.crawler_type_index : 0
                        onCurrentIndexChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.crawler_type_index = currentIndex
                    }
                }

                StackLayout {
                    currentIndex: crawlerType.currentIndex == 0 ? 0 : 1
                    Layout.fillWidth: true

                    // General Selenium Page
                    ColumnLayout {
                        spacing: 10
                        Label { text: "Search URL:"; color: Style.text }
                        TextField {
                            id: urlInput
                            placeholderText: "https://example.com/search?q=..."
                            Layout.fillWidth: true
                            background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                            color: Style.text
                            text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.gen_target_url : ""
                            onTextChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.gen_target_url = text
                        }
                        
                        GroupBox {
                            title: "Actions"
                            Layout.fillWidth: true
                            ColumnLayout {
                                ListView {
                                    id: actionListView
                                    height: 120
                                    Layout.fillWidth: true
                                    clip: true
                                    model: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.actions_model : null
                                    delegate: ItemDelegate {
                                        width: actionListView.width
                                        text: model.display_text
                                        background: Rectangle { color: highlighted ? Style.accent : "transparent" }
                                    }
                                }
                                RowLayout {
                                    AppButton { 
                                        text: "Add Action"
                                        Layout.fillWidth: true 
                                        onClicked: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.add_action()
                                    }
                                    AppButton { 
                                        text: "Remove Selected"
                                        Layout.fillWidth: true 
                                        onClicked: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.remove_action(actionListView.currentIndex)
                                    }
                                }
                            }
                        }
                    }

                    // Image Board Page
                    ColumnLayout {
                        spacing: 10
                        Label { text: "Tags:"; color: Style.text }
                        TextField {
                            id: tagsInput
                            placeholderText: "large_files high_resolution..."
                            Layout.fillWidth: true
                            background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                            color: Style.text
                            text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.board_tags : ""
                            onTextChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.board_tags = text
                        }
                        
                        Label { text: "API URL:"; color: Style.text }
                        TextField {
                            id: boardUrlInput
                            placeholderText: "https://danbooru.donmai.us"
                            Layout.fillWidth: true
                            background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                            color: Style.text
                            text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.board_url : ""
                            onTextChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.board_url = text
                        }

                        RowLayout {
                            spacing: 10
                            ColumnLayout {
                                Label { text: "Limit:"; color: Style.text }
                                TextField {
                                    text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.board_limit : "20"
                                    onTextChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.board_limit = text
                                }
                            }
                            ColumnLayout {
                                Label { text: "Max Pages:"; color: Style.text }
                                TextField {
                                    text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.board_max_pages : "5"
                                    onTextChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.board_max_pages = text
                                }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 15

                GroupBox {
                    title: "Download Settings"
                    Layout.fillWidth: true
                    GridLayout {
                        columns: 2
                        Label { text: "Download Dir:"; color: Style.text }
                        RowLayout {
                            TextField { 
                                id: downloadDirInput
                                Layout.fillWidth: true 
                                text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.download_dir : ""
                            }
                            AppButton { 
                                text: "Browse"
                                Layout.preferredWidth: 80 
                                onClicked: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.browse_download_directory()
                            }
                        }
                        
                        Label { text: "Screenshot Dir:"; color: Style.text }
                        RowLayout {
                            TextField { 
                                id: screenshotDirInput
                                Layout.fillWidth: true 
                                text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.screenshot_dir : ""
                            }
                            AppButton { 
                                text: "Browse"
                                Layout.preferredWidth: 80 
                                onClicked: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.browse_screenshot_directory()
                            }
                        }
                        
                        CheckBox { 
                            text: "Headless Mode"
                            palette.windowText: Style.text 
                            checked: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.gen_headless : true
                            onCheckedChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.gen_headless = checked
                        }
                        CheckBox { 
                            text: "Save Screenshots"
                            palette.windowText: Style.text 
                            checked: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.save_screenshots : false
                            onCheckedChanged: if (mainBackend && mainBackend.imageCrawlTab) mainBackend.imageCrawlTab.save_screenshots = checked
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    radius: Style.borderRadius
                    border.color: Style.border
                    
                    ScrollView {
                        anchors.fill: parent
                        TextArea {
                            readOnly: true
                            text: mainBackend && mainBackend.imageCrawlTab ? mainBackend.imageCrawlTab.log_output : "Log Output...\n"
                            color: "#00ff00"
                            font.family: "Monospace"
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    AppButton {
                        text: (mainBackend && mainBackend.imageCrawlTab && mainBackend.imageCrawlTab.is_crawling) ? "Cancel" : "Start Crawling"
                        Layout.fillWidth: true
                        background: Rectangle { color: (parent.text == "Cancel" ? "#e74c3c" : Style.accent); radius: Style.borderRadius }
                        onClicked: {
                            if (mainBackend && mainBackend.imageCrawlTab) {
                                if (mainBackend.imageCrawlTab.is_crawling)
                                    mainBackend.imageCrawlTab.cancel_crawl()
                                else
                                    mainBackend.imageCrawlTab.start_crawl()
                            }
                        }
                    }
                }
            }
        }
    }
}
