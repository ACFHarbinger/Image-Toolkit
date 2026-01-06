import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "tabs"
import "tabs/core"
import "tabs/web"
import "tabs/database"
import "tabs/models"
import "."

ApplicationWindow {
    id: window
    visible: true
    width: 900
    height: 700
    title: "Image Database and Toolkit"
    color: Style.background

    // --- Header ---
    header: Rectangle {
        height: 60
        color: Style.secondaryBackground
        border.width: 0

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 2
            color: Style.accent
        }

        RowLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 15

            Text {
                text: "Image Toolkit"
                color: "white"
                font.pixelSize: Style.headerFontSize
                font.bold: true
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true } // Spacer

            Button {
                text: "⚙"
                background: Rectangle {
                    color: "transparent"
                    radius: 18
                    border.width: 0
                }
                contentItem: Text {
                    text: parent.text
                    color: "white"
                    font.pixelSize: 20
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

    // --- Main Content ---
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // --- Sidebar ---
        Rectangle {
            Layout.preferredWidth: 200
            Layout.fillHeight: true
            color: Style.secondaryBackground

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                TabBar {
                    id: navBar
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    
                    background: Rectangle { color: "transparent" }

                    contentItem: ListView {
                        model: navBar.contentModel
                        currentIndex: navBar.currentIndex
                        spacing: 2
                        orientation: ListView.Vertical
                        boundsBehavior: Flickable.StopAtBounds
                        flickableDirection: Flickable.AutoFlickIfNeeded
                    }
// ... [rest of the TabButtons]

                    TabButton {
                        text: "Convert"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Merge"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Delete Duplicates"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Video Extractor"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Wallpapers"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Web Crawler"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Reverse Search"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Cloud Sync"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Web Requests"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Rectangle { height: 1; width: parent.width; color: Style.border; Layout.margins: 10 }

                    TabButton {
                        text: "Database"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Scan Metadata"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Search"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Rectangle { height: 1; width: parent.width; color: Style.border; Layout.margins: 10 }

                    TabButton {
                        text: "Generate"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Train"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "Meta CLIP"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    TabButton {
                        text: "R3GAN Eval"
                        width: parent.width
                        background: Rectangle {
                            color: parent.checked ? Style.background : "transparent"
                            border.width: 0
                            Rectangle {
                                width: 3
                                height: parent.height
                                color: Style.accent
                                visible: parent.parent.checked
                            }
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.checked ? Style.accent : Style.text
                            font.bold: parent.checked
                            leftPadding: 15
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        // --- Content Stack ---
        StackLayout {
            currentIndex: navBar.currentIndex
            
            ConvertTab {}
            MergeTab {}
            DeleteTab {}
            ImageExtractorTab {}
            WallpaperTab {}
            ImageCrawlTab {}
            ReverseImageSearchTab {}
            DriveSyncTab {}
            WebRequestsTab {}
            DatabaseTab {}
            ScanMetadataTab {}
            SearchTab {}
            GenerateTab {}
            TrainTab {}
            MetaClipInferenceTab {}
            R3GANEvaluateTab {}
        }
    }
}
