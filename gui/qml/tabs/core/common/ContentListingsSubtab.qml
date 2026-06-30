/*!
    \qmltype ContentListingsSubtab
    \inqmlmodule ImageToolkit.Tabs.Core.Common
    \brief Content listings sub-tab for media entry management.

    Displays a searchable list of media content entries (anime, films, etc.)
    with CRUD operations backed by \c mainBackend.listingsTab.contentListings.

    Key slots: \c add_entry(), \c edit_entry(id), \c delete_entry(id),
    \c search(query)
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../../../components"
import "../../../../"

Item {
    id: root

    readonly property var backend: mainBackend && mainBackend.listingsTab
                                   ? mainBackend.listingsTab.content_listings : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "Content Listings"
            color: Style.text
            font.pixelSize: 20
            font.bold: true
        }

        // Search bar
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: "Search titles, tags, status..."
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                color: Style.text
                onTextChanged: if (backend) backend.search(text)
            }
            AppButton {
                text: "Add Entry"
                onClicked: if (backend) backend.add_entry()
            }
        }

        // Listings table
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Style.secondaryBackground
            border.color: Style.border
            radius: Style.borderRadius
            clip: true

            ListView {
                id: listView
                anchors.fill: parent
                anchors.margins: 4
                model: backend ? backend.entries_model : null
                spacing: 2
                clip: true

                delegate: ItemDelegate {
                    width: listView.width
                    height: 56

                    background: Rectangle {
                        color: listView.currentIndex === index ? Style.accent + "33"
                             : (index % 2 === 0 ? Style.secondaryBackground : "transparent")
                        radius: 4
                    }

                    contentItem: RowLayout {
                        spacing: 12
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8

                        Column {
                            Layout.fillWidth: true
                            Text { text: model.title || ""; color: Style.text; font.bold: true }
                            Text { text: (model.status || "") + "  ·  " + (model.year || ""); color: Style.mutedText; font.pixelSize: 11 }
                        }

                        Text {
                            text: model.rating ? "★ " + model.rating : ""
                            color: Style.accent
                            font.pixelSize: 13
                        }

                        AppButton {
                            text: "Edit"
                            Layout.preferredWidth: 60
                            onClicked: if (backend) backend.edit_entry(model.id)
                        }
                        AppButton {
                            text: "Del"
                            Layout.preferredWidth: 50
                            background: Rectangle { color: "#c0392b"; radius: 4 }
                            onClicked: if (backend) backend.delete_entry(model.id)
                        }
                    }

                    onClicked: listView.currentIndex = index
                }
            }
        }

        // Status bar
        Text {
            text: backend ? backend.status_text : "Ready."
            color: Style.mutedText
            font.pixelSize: 11
        }
    }
}
