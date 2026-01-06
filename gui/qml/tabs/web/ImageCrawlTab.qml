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
                        model: ["General Selenium", "Image board (Danbooru/Gelbooru)"]
                        Layout.fillWidth: true
                    }
                }

                StackLayout {
                    currentIndex: crawlerType.currentIndex
                    Layout.fillWidth: true

                    // General Selenium Page
                    ColumnLayout {
                        spacing: 10
                        Label { text: "Search URL:"; color: Style.text }
                        TextField {
                            placeholderText: "https://example.com/search?q=..."
                            Layout.fillWidth: true
                            background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                            color: Style.text
                        }
                        
                        GroupBox {
                            title: "Actions"
                            Layout.fillWidth: true
                            ColumnLayout {
                                ListView {
                                    model: ListModel {
                                        ListElement { action: "Scroll Down"; param: "3 times" }
                                    }
                                    height: 100
                                    Layout.fillWidth: true
                                    delegate: ItemDelegate {
                                        text: model.action + ": " + model.param
                                        width: parent.width
                                    }
                                }
                                RowLayout {
                                    AppButton { text: "Add Action"; Layout.fillWidth: true }
                                    AppButton { text: "Remove Selected"; Layout.fillWidth: true }
                                }
                            }
                        }
                    }

                    // Image Board Page
                    ColumnLayout {
                        spacing: 10
                        Label { text: "Tags:"; color: Style.text }
                        TextField {
                            placeholderText: "large_files high_resolution..."
                            Layout.fillWidth: true
                            background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                            color: Style.text
                        }
                        
                        Label { text: "API URL:"; color: Style.text }
                        TextField {
                            placeholderText: "https://danbooru.donmai.us"
                            Layout.fillWidth: true
                            background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                            color: Style.text
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
                            TextField { Layout.fillWidth: true }
                            AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                        }
                        
                        Label { text: "Screenshot Dir:"; color: Style.text }
                        RowLayout {
                            TextField { Layout.fillWidth: true }
                            AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                        }
                        
                        CheckBox { text: "Headless Mode"; palette.windowText: Style.text }
                        CheckBox { text: "Save Screenshots"; palette.windowText: Style.text }
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
                            text: "Log Output...\n"
                            color: "#00ff00"
                            font.family: "Monospace"
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    AppButton {
                        text: "Start Crawling"
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                    }
                    AppButton {
                        text: "Cancel"
                        Layout.preferredWidth: 100
                        background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                    }
                }
            }
        }
    }
}
