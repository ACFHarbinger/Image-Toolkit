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
            text: "Cloud Drive Synchronization"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 20

            // Configuration Panel
            ColumnLayout {
                Layout.preferredWidth: 350
                spacing: 15

                GroupBox {
                    title: "Service Provider"
                    Layout.fillWidth: true
                    ComboBox {
                        model: ["Google Drive", "Dropbox", "OneDrive"]
                        Layout.fillWidth: true
                    }
                }

                GroupBox {
                    title: "Authentication"
                    Layout.fillWidth: true
                    ColumnLayout {
                        spacing: 10
                        Label { text: "Credentials File:"; color: Style.text }
                        RowLayout {
                            TextField { Layout.fillWidth: true }
                            AppButton { text: "Browse"; Layout.preferredWidth: 80 }
                        }
                        AppButton { text: "Authenticate / Refresh Token"; Layout.fillWidth: true }
                    }
                }

                GroupBox {
                    title: "Sync Options"
                    Layout.fillWidth: true
                    ColumnLayout {
                        CheckBox { text: "Dry Run (Simulate Only)"; palette.windowText: Style.text }
                        CheckBox { text: "Overwrite Existing Files"; palette.windowText: Style.text }
                        CheckBox { text: "Verify Integrity (Checksum)"; palette.windowText: Style.text }
                    }
                }
            }

            // Status & Progress Panel
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 15

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
                            text: "Sync Statistics:\n- Total Files: 0\n- Uploaded: 0\n- Errors: 0\n"
                            color: Style.text
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    AppButton {
                        text: "Start Sync"
                        Layout.fillWidth: true
                        background: Rectangle { color: "#2ecc71"; radius: Style.borderRadius }
                    }
                    AppButton {
                        text: "Stop Sync"
                        Layout.preferredWidth: 100
                        background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                    }
                }

                ProgressBar {
                    Layout.fillWidth: true
                    value: 0.3
                    background: Rectangle { color: Style.secondaryBackground; radius: 4; height: 10 }
                    contentItem: Item {
                        Rectangle {
                            width: parent.visualPosition * parent.width
                            height: 10
                            radius: 4
                            color: "#2ecc71"
                        }
                    }
                }
            }
        }
    }
}
