/*!
    \qmltype WallpaperCommon
    \inqmlmodule ImageToolkit.Tabs.Core.Common
    \brief Shared wallpaper card component used by both wallpaper sub-tabs.

    WallpaperCommon displays a thumbnail of the assigned wallpaper for a
    given monitor, along with a "Set Wallpaper" action button.

    \qmlproperty string WallpaperCommon::imagePath
    Absolute file system path of the current wallpaper image.

    \qmlproperty string WallpaperCommon::monitorId
    Unique identifier of the monitor this card represents.

    \qmlsignal WallpaperCommon::setWallpaperRequested(string monitorId)
    Emitted when the user clicks "Set Wallpaper".
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../../components"
import "../../../../"

Rectangle {
    id: root

    property string imagePath: ""
    property string monitorId: ""

    signal setWallpaperRequested(string monitorId)

    width: 200
    height: 140
    color: Style.secondaryBackground
    border.color: Style.border
    border.width: 2
    radius: 8

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#111"
            radius: 4
            clip: true

            Image {
                anchors.fill: parent
                source: root.imagePath ? "file://" + root.imagePath : ""
                fillMode: Image.PreserveAspectCrop
                visible: root.imagePath !== ""
            }

            Text {
                anchors.centerIn: parent
                text: "No wallpaper"
                color: Style.mutedText
                font.pixelSize: 11
                visible: root.imagePath === ""
            }
        }

        Text {
            text: root.imagePath ? root.imagePath.split("/").pop() : "—"
            color: Style.text
            font.pixelSize: 10
            elide: Text.ElideMiddle
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignHCenter
        }

        AppButton {
            text: "Set Wallpaper"
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            onClicked: root.setWallpaperRequested(root.monitorId)
        }
    }
}
