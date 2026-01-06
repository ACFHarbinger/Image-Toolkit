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
            text: "Advanced Web Requests"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            // Requests Configuration
            ColumnLayout {
                Layout.preferredWidth: 400
                spacing: 10

                GroupBox {
                    title: "Request List"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ColumnLayout {
                        ListView {
                            model: ListModel {
                                ListElement { method: "GET"; url: "https://api.example.com/data" }
                                ListElement { method: "POST"; url: "https://api.example.com/v1/auth" }
                            }
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            delegate: ItemDelegate {
                                width: parent.width
                                text: "[" + model.method + "] " + model.url
                                background: Rectangle { color: index % 2 == 0 ? Style.secondaryBackground : "transparent" }
                            }
                        }
                        RowLayout {
                            AppButton { text: "Add Request"; Layout.fillWidth: true }
                            AppButton { text: "Remove Selected"; Layout.fillWidth: true }
                        }
                    }
                }

                GroupBox {
                    title: "Headers / Parameters"
                    Layout.fillWidth: true
                    height: 150
                    ColumnLayout {
                        ListView {
                            model: ListModel {
                                ListElement { key: "Content-Type"; value: "application/json" }
                            }
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            delegate: ItemDelegate {
                                text: model.key + ": " + model.value
                                width: parent.width
                            }
                        }
                        AppButton { text: "Add Action/Header"; Layout.fillWidth: true }
                    }
                }
            }

            // Results & Execution Center
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 15

                GroupBox {
                    title: "Status & Progress"
                    Layout.fillWidth: true
                    ColumnLayout {
                        Label { text: "Current Status: Idle"; color: Style.mutedText }
                        ProgressBar {
                            Layout.fillWidth: true
                            value: 0
                            background: Rectangle { color: Style.secondaryBackground; radius: 4; height: 10 }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "black"
                    radius: Style.borderRadius
                    border.color: Style.border
                    
                    ScrollView {
                        anchors.fill: parent
                        TextArea {
                            readOnly: true
                            text: "> HTTP/1.1 200 OK\n> Content-Type: application/json\n\n{\n  \"status\": \"success\"\n}"
                            color: "#00ff00"
                            font.family: "Monospace"
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    AppButton {
                        text: "Execute Requests"
                        Layout.fillWidth: true
                        background: Rectangle { color: (control.pressed ? Style.accentPressed : Style.accent); radius: Style.borderRadius }
                    }
                    AppButton {
                        text: "Cancel All"
                        Layout.preferredWidth: 100
                        background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                    }
                }
            }
        }
    }
}
