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

        GroupBox {
            title: "Request Configuration"
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 12
                Label { text: "Base URL:"; color: Style.text; font.bold: true }
                TextField {
                    id: baseUrlField
                    text: mainBackend && mainBackend.webRequestsTab ? mainBackend.webRequestsTab.base_url : ""
                    placeholderText: "https://api.example.com/data"
                    Layout.fillWidth: true
                    background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                    color: Style.text
                    onTextChanged: if (mainBackend && mainBackend.webRequestsTab) mainBackend.webRequestsTab.base_url = text
                }
            }
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
                        RowLayout {
                            ComboBox {
                                id: reqTypeCombo
                                model: ["GET", "POST"]
                                Layout.preferredWidth: 80
                            }
                            TextField {
                                id: reqParamField
                                placeholderText: "Suffix/Data"
                                Layout.fillWidth: true
                            }
                            AppButton {
                                text: "Add"
                                onClicked: if (mainBackend && mainBackend.webRequestsTab) mainBackend.webRequestsTab.add_request(reqTypeCombo.currentText, reqParamField.text)
                            }
                        }
                        ListView {
                            id: requestListView
                            model: mainBackend && mainBackend.webRequestsTab ? mainBackend.webRequestsTab.requests_model : null
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            delegate: ItemDelegate {
                                width: requestListView.width
                                text: model.display_text
                                background: Rectangle { color: highlighted ? Style.accent : (index % 2 == 0 ? Style.secondaryBackground : "transparent") }
                                onClicked: requestListView.currentIndex = index
                            }
                        }
                        AppButton { 
                            text: "Remove Selected"; 
                            Layout.fillWidth: true 
                            onClicked: if (mainBackend && mainBackend.webRequestsTab) mainBackend.webRequestsTab.remove_request(requestListView.currentIndex)
                        }
                    }
                }

                GroupBox {
                    title: "Response Actions"
                    Layout.fillWidth: true
                    height: 200
                    ColumnLayout {
                        RowLayout {
                            ComboBox {
                                id: actionCombo
                                model: ["Print Status", "Print Headers", "Print Content", "Save Content"]
                                Layout.preferredWidth: 120
                            }
                            TextField {
                                id: actionParamField
                                placeholderText: "Param"
                                Layout.fillWidth: true
                            }
                            AppButton {
                                text: "Add"
                                onClicked: if (mainBackend && mainBackend.webRequestsTab) mainBackend.webRequestsTab.add_action(actionCombo.currentText, actionParamField.text)
                            }
                        }
                        ListView {
                            id: actionListView
                            model: mainBackend && mainBackend.webRequestsTab ? mainBackend.webRequestsTab.actions_model : null
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            delegate: ItemDelegate {
                                width: actionListView.width
                                text: model.display_text
                                background: Rectangle { color: highlighted ? Style.accent : "transparent" }
                                onClicked: actionListView.currentIndex = index
                            }
                        }
                        AppButton { 
                            text: "Remove Selected"; 
                            Layout.fillWidth: true 
                            onClicked: if (mainBackend && mainBackend.webRequestsTab) mainBackend.webRequestsTab.remove_action(actionListView.currentIndex)
                        }
                    }
                }
            }

            // Results & Execution Center
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 15

                GroupBox {
                    title: "Status"
                    Layout.fillWidth: true
                    ColumnLayout {
                        Label { 
                            text: mainBackend && mainBackend.webRequestsTab ? mainBackend.webRequestsTab.status_text : "Ready."
                            color: Style.accent 
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
                            text: mainBackend && mainBackend.webRequestsTab ? mainBackend.webRequestsTab.log_output : "Execution logs will appear here...\n"
                            color: "#00ff00"
                            font.family: "Monospace"
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    AppButton {
                        text: (mainBackend && mainBackend.webRequestsTab && mainBackend.webRequestsTab.is_running) ? "Cancel All" : "Execute Requests"
                        Layout.fillWidth: true
                        background: Rectangle { color: (parent.text == "Cancel All" ? "#e74c3c" : Style.accent); radius: Style.borderRadius }
                        onClicked: {
                            if (mainBackend && mainBackend.webRequestsTab) {
                                if (mainBackend.webRequestsTab.is_running)
                                    mainBackend.webRequestsTab.cancel_requests()
                                else
                                    mainBackend.webRequestsTab.start_requests()
                            }
                        }
                    }
                }
            }
        }
    }
}
