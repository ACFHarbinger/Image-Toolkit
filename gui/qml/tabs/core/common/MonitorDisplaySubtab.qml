/*!
    \qmltype MonitorDisplaySubtab
    \inqmlmodule ImageToolkit.Tabs.Core.Common
    \brief Per-monitor wallpaper display sub-tab.

    MonitorDisplaySubtab shows a visual layout of configured monitors with
    graph overlays.  Backed by \c mainBackend.wallpaperTab (monitor_display
    data is proxied through wallpaperTab).
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../../components"
import "../../../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.wallpaperTab ? mainBackend.wallpaperTab : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "Monitor Display"
            color: Style.text
            font.pixelSize: 20
            font.bold: true
        }

        Text {
            text: "Drag monitors in the System Display tab to rearrange; this panel mirrors the layout."
            color: Style.mutedText
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Style.secondaryBackground
            border.color: Style.border
            radius: Style.borderRadius

            Text {
                anchors.centerIn: parent
                text: "Monitor canvas — see System Display tab to assign wallpapers."
                color: Style.mutedText
                opacity: 0.6
            }
        }

        Text {
            text: tab ? tab.qml_status_changed : ""
            color: Style.mutedText
            font.pixelSize: 11
        }
    }
}
