import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // --- Left Panel: Scan Results ---
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "transparent"
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 15
                
                Text {
                    text: "Scan Results"
                    color: Style.text
                    font.pixelSize: 18
                    font.bold: true
                }

                RowLayout {
                    spacing: 10
                    TextField {
                        id: targetPathInput
                        placeholderText: "Enter directory to scan..."
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 4 }
                        color: Style.text
                    }
                     Connections {
                        target: (mainBackend && mainBackend.deleteTab) ? mainBackend.deleteTab : null
                        function onQml_input_path_changed(newPath) {
                            targetPathInput.text = newPath
                        }
                    }
                    AppButton { 
                        text: "Browse"
                        Layout.preferredWidth: 80 
                        onClicked: {
                            if (mainBackend && mainBackend.deleteTab) {
                                mainBackend.deleteTab.browse_target_qml(targetPathInput.text)
                            }
                        }
                    }
                }

                AppButton {
                    text: "Start Duplicate Scan"
                    Layout.fillWidth: true
                    background: Rectangle {
                        color: Style.accent
                        radius: Style.borderRadius
                    }
                    onClicked: {
                        if (mainBackend && mainBackend.deleteTab) {
                             mainBackend.deleteTab.start_duplicate_scan_qml(
                                 targetPathInput.text,
                                 "Exact Match" // TODO: Add combo box for method
                             )
                        }
                    }
                }

                GalleryView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {} // To be populated
                }
            }
        }

        // --- Right Panel: Selected for Deletion ---
        Rectangle {
            Layout.preferredWidth: parent.width * 0.4
            Layout.fillHeight: true
            color: Style.secondaryBackground
            opacity: 0.5
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 15

                Text {
                    text: "Selected for Deletion"
                    color: Style.text
                    font.pixelSize: 18
                    font.bold: true
                }

                GalleryView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {} // To be populated
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    
                    AppButton {
                        text: "Delete Selected"
                        Layout.fillWidth: true
                        onClicked: {
                            if (mainBackend && mainBackend.deleteTab) {
                                mainBackend.deleteTab.delete_selected_files_qml()
                            }
                        }
                    }
                    
                    AppButton {
                        text: "Clear Selection"
                        Layout.preferredWidth: 120
                    }
                }
            }
        }
    }
}
