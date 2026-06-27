import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root

    // Shorthand reference — guard every access against null
    readonly property var tab: mainBackend && mainBackend.reverseSearchTab
                               ? mainBackend.reverseSearchTab
                               : null

    // Derived helpers
    readonly property bool isGoogle:   tab ? tab.engine_type === "google"      : true
    readonly property bool isTinEye:   tab ? tab.engine_type === "tineye"      : false
    readonly property bool isLocalCBIR: tab ? tab.engine_type === "local_cbir" : false

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 15

        Text {
            text: "Reverse Image Search"
            color: Style.text
            font.pixelSize: 22
            font.bold: true
        }

        // ── Directory row ─────────────────────────────────────────────
        RowLayout {
            spacing: 15
            Label { text: "Scan Directory:"; color: Style.text }
            TextField {
                id: scanDir
                Layout.fillWidth: true
                text: tab ? tab.scan_dir_path : ""
                placeholderText: "Select directory to scan for source images..."
                background: Rectangle {
                    color: Style.secondaryBackground
                    border.color: Style.border
                    radius: 4
                }
                color: Style.text
                readOnly: true
            }
            AppButton {
                text: "Browse"
                Layout.preferredWidth: 80
                onClicked: if (tab) tab.browse_scan_directory()
            }
        }

        // ── Engine selector row ───────────────────────────────────────
        GroupBox {
            title: "Search Configuration"
            Layout.fillWidth: true

            GridLayout {
                columns: 2
                columnSpacing: 20
                rowSpacing: 8
                width: parent.width

                // Engine selector — always visible
                Label { text: "Engine:"; color: Style.text }
                ComboBox {
                    id: engineSelect
                    model: ["Google Lens", "TinEye API", "Local AI Search"]
                    currentIndex: {
                        var e = tab ? tab.engine_type : "google"
                        if (e === "tineye")      return 1
                        if (e === "local_cbir")  return 2
                        return 0
                    }
                    onCurrentIndexChanged: {
                        if (!tab) return
                        if (currentIndex === 0) tab.engine_type = "google"
                        else if (currentIndex === 1) tab.engine_type = "tineye"
                        else tab.engine_type = "local_cbir"
                    }
                }

                // Resolution filter — Google only
                RowLayout {
                    visible: root.isGoogle
                    CheckBox {
                        id: filterResCheck
                        text: "Filter Res"
                        palette.windowText: Style.text
                        checked: tab ? tab.filter_res : false
                        onCheckedChanged: if (tab) tab.filter_res = checked
                    }
                    TextField {
                        placeholderText: "W"
                        Layout.preferredWidth: 55
                        text: tab ? tab.min_w : "1920"
                        onTextChanged: if (tab) tab.min_w = text
                        enabled: filterResCheck.checked
                        background: Rectangle {
                            color: Style.secondaryBackground
                            border.color: Style.border
                            radius: 4
                        }
                        color: Style.text
                    }
                    Label { text: "×"; color: Style.text }
                    TextField {
                        placeholderText: "H"
                        Layout.preferredWidth: 55
                        text: tab ? tab.min_h : "1080"
                        onTextChanged: if (tab) tab.min_h = text
                        enabled: filterResCheck.checked
                        background: Rectangle {
                            color: Style.secondaryBackground
                            border.color: Style.border
                            radius: 4
                        }
                        color: Style.text
                    }
                }

                // Browser + mode — Google only
                RowLayout {
                    visible: root.isGoogle
                    Label { text: "Browser:"; color: Style.text }
                    ComboBox {
                        id: browserSelect
                        model: ["brave", "chrome", "firefox", "edge"]
                        currentIndex: find(tab ? tab.browser : "brave")
                        onCurrentTextChanged: if (tab) tab.browser = currentText
                    }
                    Label { text: "Mode:"; color: Style.text }
                    ComboBox {
                        id: modeSelect
                        model: ["All", "Visual matches", "Exact matches"]
                        currentIndex: find(tab ? tab.search_mode : "All")
                        onCurrentTextChanged: if (tab) tab.search_mode = currentText
                    }
                    CheckBox {
                        text: "Keep Open"
                        palette.windowText: Style.text
                        checked: tab ? tab.keep_open : true
                        onCheckedChanged: if (tab) tab.keep_open = checked
                    }
                }

                // Top-k selector — TinEye + Local CBIR
                RowLayout {
                    visible: !root.isGoogle
                    Label { text: "Max results:"; color: Style.text }
                    TextField {
                        Layout.preferredWidth: 65
                        text: tab ? tab.top_k : "20"
                        onTextChanged: if (tab) tab.top_k = text
                        inputMethodHints: Qt.ImhDigitsOnly
                        background: Rectangle {
                            color: Style.secondaryBackground
                            border.color: Style.border
                            radius: 4
                        }
                        color: Style.text
                    }
                    // TinEye credentials hint
                    Label {
                        visible: root.isTinEye
                        text: "Credentials: TINEYE_API_KEY / TINEYE_API_SECRET env vars"
                        color: Style.mutedText
                        font.pixelSize: 11
                    }
                    // CBIR index hint
                    Label {
                        visible: root.isLocalCBIR
                        text: "Index: ~/.image-toolkit/cbir_index/  |  Model: CLIP ViT-B/32"
                        color: Style.mutedText
                        font.pixelSize: 11
                    }
                }
            }
        }

        // ── Gallery + Results split ───────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Left: local image gallery
            ColumnLayout {
                Layout.preferredWidth: parent.width * 0.4
                Layout.fillHeight: true
                Text {
                    text: "1. Select Source Image:"
                    color: Style.text
                    font.bold: true
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    radius: Style.borderRadius
                    border.color: Style.border
                    clip: true
                    GalleryView {
                        anchors.fill: parent
                        model: tab ? tab.gallery_model : null
                        onItemClicked: if (tab) tab.handle_image_selection(path)
                    }
                }
            }

            Rectangle {
                width: 1
                Layout.fillHeight: true
                color: Style.border
                Layout.leftMargin: 10
                Layout.rightMargin: 10
            }

            // Right: search action + results
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                Text {
                    text: "2. Search Options & Results:"
                    color: Style.text
                    font.bold: true
                }

                // Search / Cancel button
                AppButton {
                    text: (tab && tab.is_searching) ? "Cancel Search" : "Start Reverse Search"
                    Layout.fillWidth: true
                    background: Rectangle {
                        color: (text === "Cancel Search") ? "#e74c3c" : Style.accent
                        radius: Style.borderRadius
                    }
                    enabled: tab ? (tab.is_searching || tab.has_selection) : false
                    onClicked: {
                        if (!tab) return
                        if (tab.is_searching)
                            tab.cancel_search()
                        else
                            tab.start_search()
                    }
                }

                // Results / status display
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: Style.secondaryBackground
                    radius: Style.borderRadius
                    border.color: Style.border
                    clip: true
                    ScrollView {
                        anchors.fill: parent
                        Text {
                            padding: 10
                            text: tab ? tab.status_text
                                      : "Search results or status will appear here."
                            color: Style.text
                            wrapMode: Text.Wrap
                        }
                    }
                }

                Text {
                    text: "Selected: " + (tab ? tab.selected_image_filename : "None")
                    color: Style.mutedText
                    font.pixelSize: 11
                }
            }
        }
    }
}
