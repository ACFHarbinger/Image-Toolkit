/*!
    \qmltype EntityListingsSubtab
    \inqmlmodule ImageToolkit.Tabs.Core.Common
    \brief Entity listings sub-tab for people and character management.

    Displays a searchable list of entities (people, characters) with links to
    related content entries.  Backed by
    \c mainBackend.listingsTab.entity_listings.

    Key slots: \c add_entity(), \c edit_entity(id), \c delete_entity(id),
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
                                   ? mainBackend.listingsTab.entity_listings : null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: "Entity Listings"
            color: Style.text
            font.pixelSize: 20
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: "Search names, roles, aliases..."
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                color: Style.text
                onTextChanged: if (backend) backend.search(text)
            }
            AppButton {
                text: "Add Entity"
                onClicked: if (backend) backend.add_entity()
            }
        }

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
                model: backend ? backend.entities_model : null
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

                        Column {
                            Layout.fillWidth: true
                            Text { text: model.name || ""; color: Style.text; font.bold: true }
                            Text { text: model.role || ""; color: Style.mutedText; font.pixelSize: 11 }
                        }

                        Text {
                            text: model.linked_titles || ""
                            color: Style.accent
                            font.pixelSize: 11
                            Layout.preferredWidth: 180
                            elide: Text.ElideRight
                        }

                        AppButton {
                            text: "Edit"
                            Layout.preferredWidth: 60
                            onClicked: if (backend) backend.edit_entity(model.id)
                        }
                        AppButton {
                            text: "Del"
                            Layout.preferredWidth: 50
                            background: Rectangle { color: "#c0392b"; radius: 4 }
                            onClicked: if (backend) backend.delete_entity(model.id)
                        }
                    }

                    onClicked: listView.currentIndex = index
                }
            }
        }

        Text {
            text: backend ? backend.status_text : "Ready."
            color: Style.mutedText
            font.pixelSize: 11
        }
    }
}
