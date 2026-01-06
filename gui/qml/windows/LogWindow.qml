import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import ".."

ApplicationWindow {
    id: window
    width: 800
    height: 500
    visible: true
    title: "System Logs"
    color: Style.background

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 15
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Text { text: "Logs:"; color: Style.text; font.bold: true; font.pixelSize: 18 }
            Item { Layout.fillWidth: true }
            TextField {
                placeholderText: "Search logs..."
                Layout.preferredWidth: 250
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                color: Style.text
            }
            AppButton { text: "Clear"; Layout.preferredWidth: 80 }
            AppButton { text: "Save to File"; Layout.preferredWidth: 120 }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }

            TextArea {
                id: logDisplay
                readOnly: true
                font.family: "Monospace"
                font.pixelSize: 13
                color: Style.text
                text: "[INFO] Application started.\n[DEBUG] Initializing QML engine...\n[INFO] Connected to PostgreSQL.\n[WARNING] Drive Sync: Offline.\n[INFO] Loading tabs...\n[INFO] UI Ready."
                wrapMode: TextEdit.WrapAnywhere
            }
        }
    }
}

