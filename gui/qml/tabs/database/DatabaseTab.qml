import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../.."

Item {
    id: root
    Layout.fillWidth: true
    Layout.fillHeight: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 20

        Text {
            text: "Database Management"
            color: Style.text
            font.pixelSize: 24
            font.bold: true
        }

        GroupBox {
            title: "Registry Info"
            Layout.fillWidth: true
            ColumnLayout {
                Text { text: "Status: Connected"; color: Style.text }
                Text { text: "Images Indexed: 0"; color: Style.text }
            }
        }

        Text {
            text: (mainBackend && mainBackend.databaseTab) ? mainBackend.databaseTab.statsText : "Loading stats..."
            color: Style.accent
            font.pixelSize: 14
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }

        AppButton {
            text: "Sync Database"
            Layout.fillWidth: true
        }

        GroupBox {
            title: "Database Maintenance"
            Layout.fillWidth: true
            RowLayout {
                spacing: 10
                AppButton {
                    text: "Vacuum"
                    onClicked: if (mainBackend && mainBackend.databaseTab) mainBackend.databaseTab.run_vacuum()
                }
                AppButton {
                    text: "Reindex"
                    onClicked: if (mainBackend && mainBackend.databaseTab) mainBackend.databaseTab.run_reindex()
                }
            }
        }
        
        Item { Layout.fillHeight: true }
    }
}

