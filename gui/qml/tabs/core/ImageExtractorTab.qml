import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtMultimedia
import "../../components"
import "../../"

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Text {
            text: "Video Frame Extractor"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            // --- Video Player Area ---
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Rectangle {
                    id: playerContainer
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "black"
                    
                    Text {
                        anchors.centerIn: parent
                        text: "Video Output Placeholder\n(Requires QtMultimedia)"
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                    }
                    
                    MediaPlayer {
                        id: player
                        source: "" // Will be set via file dialog or backend signal
                        audioOutput: AudioOutput {}
                        videoOutput: videoOut
                    }
                    VideoOutput {
                         id: videoOut
                         anchors.fill: parent
                         fillMode: VideoOutput.PreserveAspectFit
                    }
                }

                // --- Controls ---
                RowLayout {
                    Layout.fillWidth: true
                    AppButton { 
                        text: player.playbackState === MediaPlayer.PlayingState ? "⏸" : "▶"
                        Layout.preferredWidth: 40 
                        onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play()
                    }
                    Slider { 
                        id: seekSlider
                        Layout.fillWidth: true 
                        from: 0
                        to: player.duration
                        value: player.position
                        onMoved: player.position = value
                    }
                    Text { 
                        text: {
                             var m = Math.floor(player.position / 60000)
                             var s = Math.floor((player.position % 60000) / 1000)
                             return (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s)
                        } 
                        color: Style.text 
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    AppButton { 
                        text: "Extract Current Frame"
                        Layout.fillWidth: true 
                        onClicked: {
                             if (mainBackend && mainBackend.imageExtractorTab && player.source) {
                                  // Convert QUrl to string path
                                  var path = player.source.toString().replace("file://", "")
                                  mainBackend.imageExtractorTab.extract_single_frame_qml(path, player.position)
                             }
                        }
                    }
                    AppButton { 
                         text: "Open Video..."
                         Layout.preferredWidth: 150
                         onClicked: {
                              if (mainBackend && mainBackend.imageExtractorTab) {
                                   // We use backend browser to pick DIR, but here we want single video maybe?
                                   // Actually tab is "Source Directory" based.
                                   // Let's reuse browse_source_qml which picks a dir and scans it. 
                                   // But QML player needs a file.
                                   // Let's implement a simple file picker in QML or rely on backend signal?
                                   // For simplicity, let's just pick a file locally or browse dir.
                                   
                                   mainBackend.imageExtractorTab.browse_source_qml("")
                              }
                         }
                    }
                    
                    // Connection to listen for new source path if backend sets it
                    Connections {
                         target: (mainBackend && mainBackend.imageExtractorTab) ? mainBackend.imageExtractorTab : null
                         function onQml_source_path_changed(path) {
                              // Backend scanned a DIR. We don't auto-load video.
                              // QML Gallery would list files.
                         }
                    }
                }
            }

            // --- Extracted Frames Sidebar ---
            Rectangle {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                color: Style.secondaryBackground
                radius: Style.borderRadius
                border.color: Style.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    
                    Text { text: "Extracted Frames"; color: Style.text; font.bold: true }

                    GalleryView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: ListModel {}
                    }

                    AppButton {
                        text: "Export Selected"
                        Layout.fillWidth: true
                        background: Rectangle { color: Style.accent; radius: Style.borderRadius }
                    }
                }
            }
        }
    }
}
