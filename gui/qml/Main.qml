/*!
    \qmltype Main
    \inqmlmodule ImageToolkit
    \brief Root application window with collapsible sidebar and tab host.

    Main is the top-level \l ApplicationWindow for Image Toolkit.  It renders a
    collapsible left sidebar organised into five sections — Core, Database, Web,
    Models, and Animation — and a \c StackLayout (\c mainStack) that hosts all
    19 feature tabs.

    Auxiliary windows (\l SettingsWindow, \l LogWindow, \l ImagePreviewWindow,
    \l SlideshowWindow) are created on demand via \c Qt.createComponent and
    are destroyed when closed.

    \c mainStack.currentIndex mapping:
    \list
      \li 0–5   Core tabs (Convert, Delete, Merge, ImageExtractor, Wallpaper, Listings)
      \li 6–8   Database tabs (Database, Search, ScanMetadata)
      \li 9–12  Web tabs (ImageCrawl, DriveSync, WebRequests, ReverseSearch)
      \li 13–16 Model tabs (Train, Generate, R3GANEvaluate, MetaClipInference)
      \li 17–18 Animation tabs (Stitch, StitchFeedback)
    \endlist
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "tabs/core"
import "tabs/database"
import "tabs/web"
import "tabs/models"
import "tabs/animation"
import "."

ApplicationWindow {
    id: window
    width: 1280
    height: 800
    visible: true
    title: "Image Toolkit - " + (mainBackend ? mainBackend.accountName : "Loading...")
    color: Style.background

    Connections {
        target: mainBackend
        function onRequestShowSettings() {
            var component = Qt.createComponent("windows/SettingsWindow.qml");
            if (component.status === Component.Ready) {
                var win = component.createObject(window, {backend: mainBackend.settingsBackend});
                win.show();
            } else {
                console.error("Error loading SettingsWindow.qml: " + component.errorString());
            }
        }
        function onRequestShowLog(tabName) {
            var component = Qt.createComponent("windows/LogWindow.qml");
             if (component.status === Component.Ready) {
                var win = component.createObject(window, {backend: mainBackend.logBackend, title: tabName + " Logs"});
                win.show();
            } else {
                console.error("Error loading LogWindow.qml: " + component.errorString());
            }
        }
        function onRequestShowPreview(path) {
             var component = Qt.createComponent("windows/ImagePreviewWindow.qml");
             if (component.status === Component.Ready) {
                var win = component.createObject(window, {imagePath: path});
                win.show();
            } else {
                console.error("Error loading ImagePreviewWindow.qml: " + component.errorString());
            }
        }
        function onRequestShowSlideshow() {
             var component = Qt.createComponent("windows/SlideshowWindow.qml");
             if (component.status === Component.Ready) {
                var win = component.createObject(window, {backend: mainBackend.slideshowBackend});
                win.showMaximized();
            } else {
                console.error("Error loading SlideshowWindow.qml: " + component.errorString());
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Sidebar
        Rectangle {
            Layout.preferredWidth: Style.sidebarWidth
            Layout.fillHeight: true
            color: Style.secondaryBackground
            border.color: Style.border

            ScrollView {
                anchors.fill: parent
                clip: true

                ColumnLayout {
                    width: parent.width
                    spacing: 5
                    
                    Text {
                        text: "Image Toolkit"
                        color: Style.accent
                        font.pixelSize: 20
                        font.bold: true
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 15
                    }
                    
                    Text {
                        text: mainBackend ? mainBackend.accountName : "Loading..."
                        color: Style.text
                        opacity: 0.7
                        font.pixelSize: 12
                        Layout.alignment: Qt.AlignHCenter
                        Layout.bottomMargin: 10
                    }

                    // Section: Core
                    Text {
                        text: "CORE"
                        color: Style.text
                        opacity: 0.5
                        font.pixelSize: 10
                        font.bold: true
                        Layout.leftMargin: 10
                        Layout.topMargin: 5
                    }

                    Repeater {
                        model: ["Convert", "Similarity", "Merge", "Image Extractor", "Wallpaper", "Listings"]
                        
                        Button {
                            text: modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            Layout.leftMargin: 5
                            Layout.rightMargin: 5
                            font.bold: mainStack.currentIndex === index
                            checked: mainStack.currentIndex === index
                            checkable: true
                            
                            background: Rectangle {
                                color: parent.checked ? Style.accent : (parent.hovered ? Style.border : "transparent")
                                radius: 4
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: parent.checked ? "#ffffff" : Style.text
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            
                            onClicked: mainStack.currentIndex = index
                        }
                    }

                    // Section: Database
                    Text {
                        text: "DATABASE"
                        color: Style.text
                        opacity: 0.5
                        font.pixelSize: 10
                        font.bold: true
                        Layout.leftMargin: 10
                        Layout.topMargin: 10
                    }

                    Repeater {
                        model: ["Database", "Search", "Scan Metadata"]

                        Button {
                            property int tabIndex: 6 + index
                            text: modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            Layout.leftMargin: 5
                            Layout.rightMargin: 5
                            font.bold: mainStack.currentIndex === tabIndex
                            checked: mainStack.currentIndex === tabIndex
                            checkable: true
                            
                            background: Rectangle {
                                color: parent.checked ? Style.accent : (parent.hovered ? Style.border : "transparent")
                                radius: 4
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: parent.checked ? "#ffffff" : Style.text
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            
                            onClicked: mainStack.currentIndex = tabIndex
                        }
                    }

                    // Section: Web
                    Text {
                        text: "WEB"
                        color: Style.text
                        opacity: 0.5
                        font.pixelSize: 10
                        font.bold: true
                        Layout.leftMargin: 10
                        Layout.topMargin: 10
                    }

                    Repeater {
                        model: ["Image Crawler", "Drive Sync", "Web Requests", "Reverse Search"]

                        Button {
                            property int tabIndex: 9 + index
                            text: modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            Layout.leftMargin: 5
                            Layout.rightMargin: 5
                            font.bold: mainStack.currentIndex === tabIndex
                            checked: mainStack.currentIndex === tabIndex
                            checkable: true
                            
                            background: Rectangle {
                                color: parent.checked ? Style.accent : (parent.hovered ? Style.border : "transparent")
                                radius: 4
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: parent.checked ? "#ffffff" : Style.text
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            
                            onClicked: mainStack.currentIndex = tabIndex
                        }
                    }

                    // Section: Models
                    Text {
                        text: "MODELS"
                        color: Style.text
                        opacity: 0.5
                        font.pixelSize: 10
                        font.bold: true
                        Layout.leftMargin: 10
                        Layout.topMargin: 10
                    }

                    Repeater {
                        model: ["Train", "Generate", "R3GAN Evaluate", "MetaCLIP Inference"]

                        Button {
                            property int tabIndex: 13 + index
                            text: modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            Layout.leftMargin: 5
                            Layout.rightMargin: 5
                            font.bold: mainStack.currentIndex === tabIndex
                            checked: mainStack.currentIndex === tabIndex
                            checkable: true
                            
                            background: Rectangle {
                                color: parent.checked ? Style.accent : (parent.hovered ? Style.border : "transparent")
                                radius: 4
                            }
                            
                            contentItem: Text {
                                text: parent.text
                                color: parent.checked ? "#ffffff" : Style.text
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            
                            onClicked: mainStack.currentIndex = tabIndex
                        }
                    }
                    
                    // Section: Animation
                    Text {
                        text: "ANIMATION"
                        color: Style.text
                        opacity: 0.5
                        font.pixelSize: 10
                        font.bold: true
                        Layout.leftMargin: 10
                        Layout.topMargin: 10
                    }

                    Repeater {
                        model: ["Stitch", "Stitch Feedback"]

                        Button {
                            property int tabIndex: 17 + index
                            text: modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            Layout.leftMargin: 5
                            Layout.rightMargin: 5
                            font.bold: mainStack.currentIndex === tabIndex
                            checked: mainStack.currentIndex === tabIndex
                            checkable: true

                            background: Rectangle {
                                color: parent.checked ? Style.accent : (parent.hovered ? Style.border : "transparent")
                                radius: 4
                            }

                            contentItem: Text {
                                text: parent.text
                                color: parent.checked ? "#ffffff" : Style.text
                                font: parent.font
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }

                            onClicked: mainStack.currentIndex = tabIndex
                        }
                    }

                    Item { Layout.fillHeight: true } // Spacer

                    Button {
                        text: "Settings"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        Layout.leftMargin: 5
                        Layout.rightMargin: 5
                        Layout.bottomMargin: 10
                        
                        background: Rectangle {
                            color: parent.hovered ? Style.border : "transparent"
                            radius: 4
                            border.color: Style.border
                        }
                        
                        contentItem: Text {
                            text: parent.text
                            color: Style.text
                            font: parent.font
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        
                        onClicked: mainBackend.open_settings()
                    }
                }
            }
        }

        // Content
        StackLayout {
            id: mainStack
            currentIndex: 0
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Core Tabs (0-5)
            ConvertTab {}
            SimilarityTab {}
            MergeTab {}
            ImageExtractorTab {}
            WallpaperTab {}
            ListingsTab {}

            // Database Tabs (6-8)
            DatabaseTab {}
            SearchTab {}
            ScanMetadataTab {}

            // Web Tabs (9-12)
            ImageCrawlTab {}
            DriveSyncTab {}
            WebRequestsTab {}
            ReverseImageSearchTab {}

            // Models Tabs (13-16)
            TrainTab {}
            GenerateTab {}
            R3GANEvaluateTab {}
            MetaClipInferenceTab {}

            // Animation Tabs (17-18)
            StitchTab {}
            StitchFeedbackTab {}
        }
    }
}
