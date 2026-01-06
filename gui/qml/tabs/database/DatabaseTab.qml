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
        spacing: 20

        // --- Connection Section ---
        GroupBox {
            title: "Database Connection"
            Layout.fillWidth: true
            
            RowLayout {
                anchors.fill: parent
                spacing: 15
                
                TextField {
                    id: envPathField
                    placeholderText: "Path to .env file"
                    text: "env/vars.env"
                    Layout.fillWidth: true
                    background: Rectangle {
                        color: Style.secondaryBackground
                        border.color: Style.border
                        radius: 4
                    }
                    color: Style.text
                }
                
                AppButton {
                    text: "Connect"
                    onClicked: console.log("Connecting...")
                }
                
                AppButton {
                    text: "Disconnect"
                    enabled: false
                }

                AppButton {
                    text: "Reset DB"
                    // Reddish style if possible
                }
            }
        }

        // --- Statistics Section ---
        GroupBox {
            title: "Statistics"
            Layout.fillWidth: true
            
            GridLayout {
                anchors.fill: parent
                columns: 4
                columnSpacing: 20
                
                ColumnLayout {
                    Text { text: "Images"; color: Style.text; font.bold: true }
                    Text { text: "0"; color: Style.accent; font.pixelSize: 20 }
                }
                ColumnLayout {
                    Text { text: "Groups"; color: Style.text; font.bold: true }
                    Text { text: "0"; color: Style.accent; font.pixelSize: 20 }
                }
                ColumnLayout {
                    Text { text: "Subgroups"; color: Style.text; font.bold: true }
                    Text { text: "0"; color: Style.accent; font.pixelSize: 20 }
                }
                ColumnLayout {
                    Text { text: "Tags"; color: Style.text; font.bold: true }
                    Text { text: "0"; color: Style.accent; font.pixelSize: 20 }
                }
            }
        }

        // --- Management Tables Section ---
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            // Groups Table
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Text { text: "Groups"; color: Style.text; font.bold: true }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    border.color: Style.border
                    radius: 4
                    ListView {
                        anchors.fill: parent
                        clip: true
                        model: ListModel {
                            ListElement { name: "Sample Group" }
                        }
                        delegate: ItemDelegate {
                            width: parent.width
                            text: model.name
                            contentItem: Text {
                                text: parent.text
                                color: Style.text
                                leftPadding: 10
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
                RowLayout {
                    TextField { placeholderText: "New Group"; Layout.fillWidth: true }
                    AppButton { text: "+"; Layout.preferredWidth: 40 }
                }
            }

            // Subgroups Table
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Text { text: "Subgroups"; color: Style.text; font.bold: true }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    border.color: Style.border
                    radius: 4
                    ListView {
                        anchors.fill: parent
                        clip: true
                        model: ListModel {
                            ListElement { name: "Sample Subgroup" }
                        }
                        delegate: ItemDelegate {
                            width: parent.width
                            text: model.name
                            contentItem: Text {
                                text: parent.text
                                color: Style.text
                                leftPadding: 10
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
                RowLayout {
                    TextField { placeholderText: "New Subgroup"; Layout.fillWidth: true }
                    AppButton { text: "+"; Layout.preferredWidth: 40 }
                }
            }

            // Tags Table
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Text { text: "Tags"; color: Style.text; font.bold: true }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    border.color: Style.border
                    radius: 4
                    ListView {
                        anchors.fill: parent
                        clip: true
                        model: ListModel {
                            ListElement { name: "Sample Tag" }
                        }
                        delegate: ItemDelegate {
                            width: parent.width
                            text: model.name
                            contentItem: Text {
                                text: parent.text
                                color: Style.text
                                leftPadding: 10
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
                RowLayout {
                    TextField { placeholderText: "New Tag"; Layout.fillWidth: true }
                    AppButton { text: "+"; Layout.preferredWidth: 40 }
                }
            }
        }

        // --- Actions Section ---
        RowLayout {
            Layout.fillWidth: true
            spacing: 15
            
            AppButton {
                text: "Import Tags (JSON)"
                Layout.fillWidth: true
            }
            
            AppButton {
                text: "Auto-Populate from Source"
                Layout.fillWidth: true
            }
        }
    }
}
