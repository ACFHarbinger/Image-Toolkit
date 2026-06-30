/*!
    \qmltype ListingsTab
    \inqmlmodule ImageToolkit.Tabs.Core
    \brief Media tracking and entity listing tab.

    ListingsTab contains two sub-tabs:
    \list
      \li \b {Content Listings} — media entries with metadata, ratings, and tags.
      \li \b {Entity Listings} — people/characters linked to content entries.
    \endlist

    Backend object: \c mainBackend.listingsTab
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "common"
import "../../../components"
import "../../../"

Item {
    id: root

    readonly property var tab: mainBackend && mainBackend.listingsTab ? mainBackend.listingsTab : null

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TabBar {
            id: tabBar
            Layout.fillWidth: true

            TabButton {
                text: "Content Listings"
                width: implicitWidth
            }
            TabButton {
                text: "Entity Listings"
                width: implicitWidth
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            ContentListingsSubtab { id: contentListings }
            EntityListingsSubtab  { id: entityListings }
        }
    }
}
