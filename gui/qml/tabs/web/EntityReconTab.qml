/*!
    \qmltype EntityReconTab
    \inqmlmodule ImageToolkit.Tabs.Web
    \brief Entity Recon & Provenance — localized OSINT identity resolution.

    Three-pane layout:
      Left    source image with SAM-2 hover masking + manual bounding box
      Center  resolved identity card (name, confidence ring, method/origin)
      Right   provenance trail (local file paths or grouped web domains)

    Plus a Strict Privacy Mode toggle, provenance export, and a drag-and-drop
    Dataset Builder that bulk-suggests FirstName_LastName folder moves.

    Backend: \c mainBackend.entityReconTab (EntityReconTab).
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root
    property var backend: (mainBackend && mainBackend.entityReconTab)
                          ? mainBackend.entityReconTab : null

    property string sourcePath: ""
    property string maskOverlay: ""
    property bool bboxMode: false
    property real imgScale: 1.0

    Connections {
        target: root.backend
        function onSource_changed(path) {
            root.sourcePath = path
            root.maskOverlay = ""
        }
        function onMask_ready(path) {
            // cache-bust so the same temp filename reloads
            root.maskOverlay = path + "?t=" + Date.now()
        }
        function onStatus_changed(msg) { statusBar.text = msg }
        function onIndex_ready(images, labels) {
            indexInfo.text = images + " imgs · " + labels + " identities"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- top bar: privacy + dataset + export ----------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            color: Style.secondaryBackground
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                Text {
                    text: "Entity Recon"
                    color: Style.text
                    font.pixelSize: 16
                    font.bold: true
                }

                // Strict Privacy Mode
                Rectangle {
                    Layout.preferredWidth: privRow.width + 20
                    Layout.preferredHeight: 34
                    radius: 17
                    color: (root.backend && root.backend.privacyMode) ? "#1e7e4f" : "#7a2f2f"
                    RowLayout {
                        id: privRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            text: (root.backend && root.backend.privacyMode)
                                  ? "🔒 Privacy: ON (offline)" : "🌐 Privacy: OFF (web)"
                            color: "white"
                            font.bold: true
                        }
                        Switch {
                            checked: root.backend ? root.backend.privacyMode : true
                            onToggled: if (root.backend) root.backend.set_privacy_mode(checked)
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                Text { id: indexInfo; text: "no index"; color: Style.mutedText }

                AppButton {
                    text: "Select Dataset"
                    onClicked: if (root.backend) {
                        var d = root.backend.browse_dataset_qml("")
                        if (d) root.backend.build_index(d)
                    }
                }
                AppButton {
                    text: "Export JSON"
                    onClicked: if (root.backend) root.backend.export_report_qml("json")
                }
                AppButton {
                    text: "Export CSV"
                    onClicked: if (root.backend) root.backend.export_report_qml("csv")
                }
            }
        }

        // ---- three panes ---------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // ============ LEFT: source + segmentation =================
            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: parent.width * 0.4
                color: Style.background
                border.color: Style.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Source"; color: Style.text; font.bold: true; Layout.fillWidth: true }
                        AppButton {
                            text: "Open Image"
                            onClicked: if (root.backend) root.backend.browse_source_qml("")
                        }
                        AppButton {
                            text: root.bboxMode ? "Box: ON" : "Box: OFF"
                            onClicked: root.bboxMode = !root.bboxMode
                        }
                    }

                    // image viewport
                    Rectangle {
                        id: viewport
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: "black"
                        border.color: Style.border
                        clip: true

                        Image {
                            id: srcImage
                            anchors.fill: parent
                            fillMode: Image.PreserveAspectFit
                            source: root.sourcePath ? "file://" + root.sourcePath : ""
                            asynchronous: true
                        }
                        // translucent SAM mask overlay
                        Image {
                            anchors.fill: parent
                            fillMode: Image.PreserveAspectFit
                            source: root.maskOverlay ? "file://" + root.maskOverlay : ""
                            visible: root.maskOverlay.length > 0
                            cache: false
                        }

                        // map viewport coords → image pixel coords
                        function toImage(mx, my) {
                            if (srcImage.paintedWidth <= 0) return null
                            var offX = (srcImage.width - srcImage.paintedWidth) / 2
                            var offY = (srcImage.height - srcImage.paintedHeight) / 2
                            var ix = (mx - offX) / srcImage.paintedWidth * srcImage.sourceSize.width
                            var iy = (my - offY) / srcImage.paintedHeight * srcImage.sourceSize.height
                            if (ix < 0 || iy < 0 || ix > srcImage.sourceSize.width
                                || iy > srcImage.sourceSize.height) return null
                            return { x: Math.round(ix), y: Math.round(iy) }
                        }

                        property var boxStart: null
                        Rectangle {
                            id: boxRect
                            visible: false
                            color: "#335865f2"
                            border.color: Style.accent
                            border.width: 2
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            property double lastHover: 0
                            onPositionChanged: {
                                if (root.bboxMode) {
                                    if (pressed && viewport.boxStart) {
                                        boxRect.x = Math.min(viewport.boxStart.mx, mouse.x)
                                        boxRect.y = Math.min(viewport.boxStart.my, mouse.y)
                                        boxRect.width = Math.abs(mouse.x - viewport.boxStart.mx)
                                        boxRect.height = Math.abs(mouse.y - viewport.boxStart.my)
                                    }
                                    return
                                }
                                // throttle live hover segmentation
                                var now = Date.now()
                                if (now - lastHover < 180 || !root.sourcePath || !root.backend) return
                                lastHover = now
                                var p = viewport.toImage(mouse.x, mouse.y)
                                if (p) root.backend.segment_at(p.x, p.y)
                            }
                            onPressed: {
                                if (root.bboxMode) {
                                    viewport.boxStart = { mx: mouse.x, my: mouse.y }
                                    boxRect.x = mouse.x; boxRect.y = mouse.y
                                    boxRect.width = 0; boxRect.height = 0
                                    boxRect.visible = true
                                }
                            }
                            onReleased: {
                                if (root.bboxMode && viewport.boxStart && root.backend) {
                                    var a = viewport.toImage(boxRect.x, boxRect.y)
                                    var b = viewport.toImage(boxRect.x + boxRect.width,
                                                             boxRect.y + boxRect.height)
                                    if (a && b) root.backend.segment_bbox(a.x, a.y, b.x, b.y)
                                    viewport.boxStart = null
                                }
                            }
                            onClicked: {
                                if (root.bboxMode || !root.sourcePath || !root.backend) return
                                var p = viewport.toImage(mouse.x, mouse.y)
                                if (p) {
                                    root.backend.segment_at(p.x, p.y)
                                    root.backend.confirm_extract()
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: !root.sourcePath
                            text: "Open an image, then hover to mask\nand click to identify the subject."
                            color: Style.mutedText
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }

                    AppButton {
                        Layout.fillWidth: true
                        text: "Identify Subject"
                        enabled: root.sourcePath.length > 0
                        onClicked: if (root.backend) root.backend.confirm_extract()
                    }
                }
            }

            // ============ CENTER: identity card =======================
            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: parent.width * 0.26
                color: Style.secondaryBackground
                border.color: Style.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 16

                    Text {
                        text: "Identity Resolution"
                        color: Style.text
                        font.bold: true
                        Layout.alignment: Qt.AlignHCenter
                    }

                    ConfidenceRing {
                        Layout.alignment: Qt.AlignHCenter
                        value: root.backend ? root.backend.identityConfidence : 0
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.backend ? (root.backend.identityName || "—") : "—"
                        color: Style.text
                        font.pixelSize: 22
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                    }

                    // origin badge
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        visible: root.backend && root.backend.identityOrigin !== "none"
                        width: originText.width + 20
                        height: 26
                        radius: 13
                        color: (root.backend && root.backend.identityOrigin === "local")
                               ? "#2980b9" : "#8e44ad"
                        Text {
                            id: originText
                            anchors.centerIn: parent
                            text: (root.backend && root.backend.identityOrigin === "local")
                                  ? "LOCAL DB" : "WEB CONSENSUS"
                            color: "white"; font.bold: true; font.pixelSize: 11
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.backend ? ("Method: " + (root.backend.identityMethod || "—")) : ""
                        color: Style.mutedText
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                    }

                    BusyIndicator {
                        Layout.alignment: Qt.AlignHCenter
                        running: root.backend ? root.backend.busy : false
                    }

                    Item { Layout.fillHeight: true }
                }
            }

            // ============ RIGHT: provenance trail + batch =============
            Rectangle {
                Layout.fillHeight: true
                Layout.fillWidth: true
                color: Style.background
                border.color: Style.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Text { text: "Provenance Trail"; color: Style.text; font.bold: true }

                    ListView {
                        id: provList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 4
                        model: root.backend ? root.backend.provenanceModel : null
                        delegate: Rectangle {
                            width: provList.width
                            height: 58
                            radius: 4
                            color: Style.secondaryBackground
                            border.color: Style.border
                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 8
                                Rectangle {
                                    Layout.preferredWidth: 6
                                    Layout.fillHeight: true
                                    radius: 3
                                    color: model.kind === "local" ? "#2980b9" : "#8e44ad"
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        text: model.kind === "local"
                                              ? model.label
                                              : (model.domain + " (" + model.matchCount + " matches)")
                                        color: Style.text
                                        font.bold: true
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: model.source
                                        color: Style.mutedText
                                        font.pixelSize: 10
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }
                                Text {
                                    text: Math.round(model.score * 100) + "%"
                                    color: Style.mutedText
                                }
                                AppButton {
                                    text: model.kind === "local" ? "📂" : "↗"
                                    Layout.preferredWidth: 40
                                    onClicked: {
                                        if (!root.backend) return
                                        if (model.kind === "local")
                                            root.backend.open_in_file_manager(model.source)
                                        else
                                            root.backend.open_url(model.source)
                                    }
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: provList.count === 0
                            text: "No provenance yet."
                            color: Style.mutedText
                        }
                    }

                    // ---- Dataset Builder dropzone ------------------------
                    Text { text: "Dataset Builder (drop images)"; color: Style.text; font.bold: true }
                    Rectangle {
                        id: dropzone
                        Layout.fillWidth: true
                        Layout.preferredHeight: 90
                        radius: 6
                        color: dropArea.containsDrag ? Qt.darker(Style.accent, 2) : Style.secondaryBackground
                        border.color: dropArea.containsDrag ? Style.accent : Style.border
                        border.width: 2

                        Text {
                            anchors.centerIn: parent
                            text: "⇩ Drop a batch of images here to auto-tag"
                            color: Style.mutedText
                        }
                        DropArea {
                            id: dropArea
                            anchors.fill: parent
                            onDropped: {
                                if (drop.hasUrls && root.backend) {
                                    var urls = []
                                    for (var i = 0; i < drop.urls.length; ++i)
                                        urls.push(drop.urls[i].toString())
                                    root.backend.drop_batch(urls)
                                }
                            }
                        }
                    }

                    ListView {
                        id: batchList
                        Layout.fillWidth: true
                        Layout.preferredHeight: 120
                        clip: true
                        visible: count > 0
                        model: root.backend ? root.backend.batchModel : null
                        delegate: RowLayout {
                            width: batchList.width
                            spacing: 8
                            Text {
                                text: model.path.split("/").pop()
                                color: Style.text
                                elide: Text.ElideMiddle
                                Layout.preferredWidth: 140
                            }
                            Text {
                                text: model.suggestedLabel
                                      ? ("→ " + model.suggestedLabel + " (" + Math.round(model.score * 100) + "%)")
                                      : "→ no match"
                                color: model.suggestedLabel ? "#2ecc71" : Style.mutedText
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
                    }
                    AppButton {
                        Layout.fillWidth: true
                        visible: batchList.count > 0
                        text: "Approve All (move into identity folders)"
                        background: Rectangle { color: "#1e7e4f"; radius: Style.borderRadius }
                        onClicked: if (root.backend) root.backend.approve_all_batch()
                    }
                }
            }
        }

        // ---- status bar ----------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            color: Style.secondaryBackground
            Text {
                id: statusBar
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 12
                text: "Ready."
                color: Style.mutedText
                font.pixelSize: 11
            }
        }
    }
}
