/*!
    \qmltype ComfyGenerateTab
    \inqmlmodule ImageToolkit.Tabs.Models.Gen
    \brief ComfyUI server management sub-tab.

    ComfyGenerateTab manages the ComfyUI server subprocess and opens the
    ComfyUI web interface in the system browser.

    \note QWebEngineView is intentionally NOT used here.  Chromium loads
    native libstdc++ symbols that conflict with JPype's JVM, causing a fatal
    SIGSEGV.  The URL is opened with \c QDesktopServices.openUrl() instead.

    Backend object: \c mainBackend.comfyTab

    Key slots: \c start_server(), \c stop_server(), \c open_in_browser()
    Key properties: \c is_running, \c server_url, \c port, \c log_output,
    \c status_text
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../components"
import "../../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.comfyTab ? mainBackend.comfyTab : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Text {
            text: "ComfyUI"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        // Server control
        GroupBox {
            title: "ComfyUI Server"
            Layout.fillWidth: true

            RowLayout {
                spacing: 12
                Layout.fillWidth: true

                AppButton {
                    text: "Start Server"
                    Layout.preferredWidth: 120
                    enabled: !(tab && tab.is_running)
                    background: Rectangle { color: "#27ae60"; radius: 4 }
                    onClicked: if (tab) tab.start_server()
                }

                AppButton {
                    text: "Stop Server"
                    Layout.preferredWidth: 120
                    enabled: tab ? tab.is_running : false
                    background: Rectangle { color: "#e74c3c"; radius: 4 }
                    onClicked: if (tab) tab.stop_server()
                }

                Label { text: "Port:"; color: Style.text }
                SpinBox {
                    id: portSpin
                    from: 1024; to: 65535; value: tab ? tab.port : 8188
                    editable: true
                    enabled: !(tab && tab.is_running)
                    onValueChanged: if (tab && !tab.is_running) tab.port = value
                }

                Item { Layout.fillWidth: true }

                AppButton {
                    text: "Open in Browser"
                    Layout.preferredWidth: 140
                    enabled: tab ? tab.is_running : false
                    onClicked: if (tab) tab.open_in_browser()
                }
            }
        }

        // Status
        GroupBox {
            title: "Status"
            Layout.fillWidth: true

            RowLayout {
                spacing: 12
                Rectangle {
                    width: 12; height: 12; radius: 6
                    color: (tab && tab.is_running) ? "#2ecc71" : "#e74c3c"
                }
                Label {
                    text: tab ? tab.status_text : "Server stopped."
                    color: Style.accent
                }
                Label {
                    text: (tab && tab.server_url) ? "URL: " + tab.server_url : ""
                    color: Style.mutedText
                    font.pixelSize: 11
                }
            }
        }

        // Log output
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "black"
            radius: Style.borderRadius
            border.color: Style.border

            ScrollView {
                anchors.fill: parent
                TextArea {
                    id: logArea
                    readOnly: true
                    text: tab ? tab.log_output : "ComfyUI server logs will appear here...\n"
                    color: "#00ff00"
                    font.family: "Monospace"
                    font.pixelSize: 12
                    background: null
                }
            }
        }
    }
}
