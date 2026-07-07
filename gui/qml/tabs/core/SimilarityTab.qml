/*!
    \qmltype SimilarityTab
    \inqmlmodule ImageToolkit.Tabs.Core
    \brief Similarity Finder — the evolved Delete tab.

    Four-tier duplicate/similarity detection (exact xxHash64, consensus
    perceptual hashing, structural SSIM/ORB/SIFT, semantic CLIP embeddings)
    with cluster "albums", a live confidence-threshold regrouping slider,
    smart-triage auto-selection, visual comparators (blink / swipe /
    difference-mask / tethered zoom) and hardlink consolidation.

    Backend: \c mainBackend.similarityTab (SimilarityTab, extends DeleteTab).
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../../components"
import "../../"

Item {
    id: root

    property var backend: (mainBackend && mainBackend.similarityTab)
                          ? mainBackend.similarityTab : null

    // selection revision — bumped so delegates re-evaluate is_selected()
    property int selectionRev: 0
    property int clusterCount: 0
    property string currentClusterId: ""
    property var currentClusterPaths: []
    property string currentKeeper: ""

    // pair-compare state
    property bool pairSelectMode: false
    property string compareA: ""
    property string compareB: ""

    Connections {
        target: root.backend
        function onSelection_changed_qml() { root.selectionRev++ }
        function onClusters_changed() {
            root.clusterCount = root.backend ? root.backend.clusterModel.rowCount() : 0
            root.currentClusterId = ""
            root.currentClusterPaths = []
            root.currentKeeper = ""
        }
        function onScan_status_changed(msg) { statusText.text = msg }
        function onScan_progress(done, total) {
            progressBar.indeterminate = (total === 0)
            progressBar.to = Math.max(1, total)
            progressBar.value = done
        }
        function onConsolidation_done(summary) { statusText.text = summary }
        function onReference_dir_changed(path) { referenceInput.text = path }
        function onQml_input_path_changed(newPath) { targetInput.text = newPath }
    }

    function applySettings() {
        if (!backend) return
        backend.set_similarity_settings({
            "tiers": [
                tierExact.checked ? "exact" : "",
                tierPerceptual.checked ? "perceptual" : "",
                tierStructural.checked ? "structural" : "",
                tierSemantic.checked ? "semantic" : ""
            ].filter(function (t) { return t.length > 0 }),
            "reference_dir": referenceInput.text.length ? referenceInput.text : null,
            "hash_size": parseInt(hashSizeCombo.currentText),
            "hamming_threshold": hammingSpin.value,
            "feature_method": featureMethodCombo.currentText.toLowerCase(),
            "max_features": maxFeaturesSpin.value,
            "lowe_ratio": loweSlider.value,
            "ransac_threshold": ransacSpin.value,
            "embed_model": embedModelCombo.currentText,
            "similarity_threshold": semanticThresholdSlider.value,
            "confidence_threshold": confidenceSlider.value,
            "extensions": extensionsField.text.split(/[\s,]+/)
                .map(function (s) { return s.trim() })
                .filter(function (s) { return s.length > 0 })
                .map(function (s) { return s[0] === "." ? s : "." + s })
        })
        backend.set_triage_rules({
            "prefer_highest_resolution": ruleResolution.checked,
            "prefer_largest_file": ruleFileSize.checked,
            "prefer_lossless_format": ruleFormat.checked,
            "prefer_exif_metadata": ruleExif.checked,
            "path_priority": pathPriorityField.text.split(",")
                .map(function (s) { return s.trim() })
                .filter(function (s) { return s.length > 0 })
        })
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ==============================================================
        // LEFT: scan scope + engine hyperparameters + actions
        // ==============================================================
        Rectangle {
            Layout.preferredWidth: 340
            Layout.fillHeight: true
            color: Style.secondaryBackground

            ScrollView {
                anchors.fill: parent
                anchors.margins: 12
                contentWidth: availableWidth
                clip: true

                ColumnLayout {
                    width: parent.width
                    spacing: 10

                    Text {
                        text: "Similarity Finder"
                        color: Style.text
                        font.pixelSize: 18
                        font.bold: true
                    }

                    // ---- directories -------------------------------------
                    Text { text: "Target directory"; color: Style.mutedText; font.pixelSize: 11 }
                    RowLayout {
                        Layout.fillWidth: true
                        TextField {
                            id: targetInput
                            Layout.fillWidth: true
                            placeholderText: "Directory to scan..."
                            color: Style.text
                            background: Rectangle { color: Style.background; border.color: Style.border; radius: 4 }
                        }
                        AppButton {
                            text: "…"
                            Layout.preferredWidth: 34
                            onClicked: if (root.backend) root.backend.browse_target_qml(targetInput.text)
                        }
                    }

                    Text { text: "Reference directory (kept intact — cross-directory sync)"; color: Style.mutedText; font.pixelSize: 11 }
                    RowLayout {
                        Layout.fillWidth: true
                        TextField {
                            id: referenceInput
                            Layout.fillWidth: true
                            placeholderText: "Optional reference folder..."
                            color: Style.text
                            background: Rectangle { color: Style.background; border.color: Style.border; radius: 4 }
                        }
                        AppButton {
                            text: "…"
                            Layout.preferredWidth: 34
                            onClicked: if (root.backend) root.backend.browse_reference_qml(referenceInput.text)
                        }
                        AppButton {
                            text: "✕"
                            Layout.preferredWidth: 30
                            onClicked: {
                                referenceInput.text = ""
                                if (root.backend) root.backend.clear_reference_dir()
                            }
                        }
                    }

                    // ---- detection tiers ---------------------------------
                    Text { text: "Detection tiers"; color: Style.text; font.bold: true }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 4
                        CheckBox { id: tierExact;      text: "Exact";      checked: true }
                        CheckBox { id: tierPerceptual; text: "Perceptual"; checked: true }
                        CheckBox { id: tierStructural; text: "Structural"; checked: false }
                        CheckBox { id: tierSemantic;   text: "Semantic";   checked: false }
                    }

                    // ---- target file extensions --------------------------
                    Text { text: "Target extensions (blank = all images)"; color: Style.mutedText; font.pixelSize: 11 }
                    TextField {
                        id: extensionsField
                        Layout.fillWidth: true
                        placeholderText: "e.g. jpg png webp"
                        color: Style.text
                        background: Rectangle { color: Style.background; border.color: Style.border; radius: 4 }
                    }

                    // ---- hashing hyperparameters ---------------------------
                    OptionalField {
                        Layout.fillWidth: true
                        title: "Consensus hashing (pHash · dHash · wHash)"
                        content: ColumnLayout {
                            width: parent.width
                            RowLayout {
                                Text { text: "Hash size"; color: Style.text }
                                ComboBox {
                                    id: hashSizeCombo
                                    model: ["8", "16", "32"]
                                    currentIndex: 1
                                }
                                Text { text: "Hamming ≤"; color: Style.text }
                                SpinBox { id: hammingSpin; from: 0; to: 64; value: 10 }
                            }
                        }
                    }

                    // ---- feature matching ----------------------------------
                    OptionalField {
                        Layout.fillWidth: true
                        title: "Feature matching (ORB / SIFT + RANSAC)"
                        content: ColumnLayout {
                            width: parent.width
                            RowLayout {
                                Text { text: "Method"; color: Style.text }
                                ComboBox { id: featureMethodCombo; model: ["ORB", "SIFT"] }
                                Text { text: "Max features"; color: Style.text }
                                SpinBox { id: maxFeaturesSpin; from: 100; to: 10000; stepSize: 100; value: 1000 }
                            }
                            RowLayout {
                                Text { text: "Lowe's ratio " + loweSlider.value.toFixed(2); color: Style.text }
                                Slider { id: loweSlider; from: 0.5; to: 0.95; value: 0.75; Layout.fillWidth: true }
                            }
                            RowLayout {
                                Text { text: "RANSAC threshold"; color: Style.text }
                                SpinBox { id: ransacSpin; from: 1; to: 20; value: 5 }
                            }
                        }
                    }

                    // ---- semantic embeddings -------------------------------
                    OptionalField {
                        Layout.fillWidth: true
                        title: "Semantic embeddings (local CLIP)"
                        content: ColumnLayout {
                            width: parent.width
                            RowLayout {
                                Text { text: "Model"; color: Style.text }
                                ComboBox { id: embedModelCombo; model: ["mobileclip", "openclip", "resnet18"] }
                            }
                            RowLayout {
                                Text { text: "Similarity ≥ " + semanticThresholdSlider.value.toFixed(2); color: Style.text }
                                Slider { id: semanticThresholdSlider; from: 0.7; to: 0.99; value: 0.9; Layout.fillWidth: true }
                            }
                        }
                    }

                    // ---- triage rules --------------------------------------
                    OptionalField {
                        Layout.fillWidth: true
                        title: "Smart triage (auto-selection rules)"
                        content: ColumnLayout {
                            width: parent.width
                            CheckBox { id: ruleResolution; text: "Prefer highest resolution"; checked: true }
                            CheckBox { id: ruleFileSize;   text: "Prefer largest file";      checked: true }
                            CheckBox { id: ruleFormat;     text: "Prefer lossless formats";  checked: true }
                            CheckBox { id: ruleExif;       text: "Prefer EXIF metadata";     checked: true }
                            Text { text: "Path priority (comma-separated)"; color: Style.mutedText; font.pixelSize: 11 }
                            TextField {
                                id: pathPriorityField
                                Layout.fillWidth: true
                                text: "archive, pictures"
                                color: Style.text
                                background: Rectangle { color: Style.background; border.color: Style.border; radius: 4 }
                            }
                        }
                    }

                    // ---- actions -------------------------------------------
                    AppButton {
                        Layout.fillWidth: true
                        text: root.backend && root.backend.scanRunning
                              ? "Cancel Scan" : "Start Similarity Scan"
                        background: Rectangle {
                            color: root.backend && root.backend.scanRunning ? "#c0392b" : Style.accent
                            radius: Style.borderRadius
                        }
                        onClicked: {
                            if (!root.backend) return
                            if (root.backend.scanRunning) {
                                root.backend.cancel_similarity_scan()
                            } else {
                                root.applySettings()
                                root.backend.start_similarity_scan_qml(targetInput.text)
                            }
                        }
                    }

                    AppButton {
                        Layout.fillWidth: true
                        text: "Auto-Select Duplicates (Triage)"
                        onClicked: {
                            if (!root.backend) return
                            root.applySettings()
                            root.backend.auto_select_all()
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        AppButton {
                            Layout.fillWidth: true
                            text: "Delete Selected"
                            background: Rectangle { color: "#c0392b"; radius: Style.borderRadius }
                            onClicked: if (root.backend) root.backend.delete_selected_files_qml()
                        }
                        AppButton {
                            Layout.fillWidth: true
                            text: "Consolidate (" + linkModeCombo.currentText + ")"
                            onClicked: if (root.backend) root.backend.consolidate_selected(linkModeCombo.currentText)
                        }
                    }
                    ComboBox {
                        id: linkModeCombo
                        Layout.fillWidth: true
                        model: ["auto", "hardlink", "symlink"]
                    }

                    // ---- classic Delete-tab operations -------------------
                    OptionalField {
                        Layout.fillWidth: true
                        title: "Directory operations"
                        content: ColumnLayout {
                            width: parent.width
                            CheckBox {
                                id: confirmCheck
                                text: "Confirm before deleting"
                                checked: true
                                onCheckedChanged: if (root.backend) root.backend.set_require_confirm(checked)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                text: "List Directory Contents"
                                onClicked: if (root.backend) root.backend.list_directory_qml(targetInput.text)
                            }
                            AppButton {
                                Layout.fillWidth: true
                                text: "Delete Directory & Contents"
                                background: Rectangle { color: "#96281b"; radius: Style.borderRadius }
                                onClicked: if (root.backend) root.backend.delete_directory_qml(targetInput.text)
                            }
                        }
                    }

                    ProgressBar {
                        id: progressBar
                        Layout.fillWidth: true
                        visible: root.backend ? root.backend.scanRunning : false
                        indeterminate: true
                    }
                    Text {
                        id: statusText
                        Layout.fillWidth: true
                        text: "Ready."
                        color: Style.mutedText
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                }
            }
        }

        // ==============================================================
        // CENTER: confidence slider + cluster albums
        // ==============================================================
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "transparent"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "Confidence threshold  " + (confidenceSlider.value * 100).toFixed(0) + "%"
                        color: Style.text
                        font.bold: true
                    }
                    Slider {
                        id: confidenceSlider
                        Layout.fillWidth: true
                        from: 0.4; to: 1.0
                        value: 0.75
                        // live regroup of the cached edge graph — no rescan
                        onMoved: if (root.backend) root.backend.set_confidence_threshold(value)
                    }
                    Text {
                        text: root.clusterCount + " clusters"
                        color: Style.mutedText
                    }
                }

                GridView {
                    id: clusterGrid
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    cellWidth: 200
                    cellHeight: 232
                    model: root.backend ? root.backend.clusterModel : null
                    delegate: ClusterStack {
                        paths: model.paths
                        clusterId: model.clusterId
                        clusterSize: model.clusterSize
                        confidence: model.confidence
                        tier: model.tier
                        keeperPath: model.keeperPath
                        current: model.clusterId === root.currentClusterId
                        onClicked: {
                            root.currentClusterId = model.clusterId
                            root.currentClusterPaths = model.paths
                            root.currentKeeper = model.keeperPath
                            root.compareA = ""
                            root.compareB = ""
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: clusterGrid.count === 0
                        text: "No clusters — run a scan."
                        color: Style.mutedText
                    }
                }
            }
        }

        // ==============================================================
        // RIGHT: cluster detail (members + comparators)
        // ==============================================================
        Rectangle {
            Layout.preferredWidth: parent.width * 0.34
            Layout.fillHeight: true
            color: Style.secondaryBackground
            visible: root.currentClusterPaths.length > 0

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: root.currentClusterId + " — " + root.currentClusterPaths.length + " images"
                        color: Style.text
                        font.bold: true
                        elide: Text.ElideRight
                    }
                    AppButton {
                        text: "Triage"
                        Layout.preferredWidth: 70
                        onClicked: if (root.backend) root.backend.auto_select_cluster(root.currentClusterId)
                    }
                    AppButton {
                        text: root.pairSelectMode ? "Compare: pick A/B…" : "Compare"
                        Layout.preferredWidth: 130
                        onClicked: {
                            root.pairSelectMode = !root.pairSelectMode
                            root.compareA = ""
                            root.compareB = ""
                        }
                    }
                }

                // member grid
                GridView {
                    id: memberGrid
                    Layout.fillWidth: true
                    Layout.preferredHeight: parent.height * 0.42
                    clip: true
                    cellWidth: 116
                    cellHeight: 130
                    model: root.currentClusterPaths
                    delegate: Rectangle {
                        property bool isSelected: {
                            root.selectionRev   // dependency bump
                            return root.backend ? root.backend.is_selected(modelData) : false
                        }
                        width: 108
                        height: 122
                        radius: 4
                        color: "black"
                        border.width: 2
                        border.color: modelData === root.compareA ? "#2ecc71"
                                    : modelData === root.compareB ? "#e67e22"
                                    : isSelected ? "#c0392b"
                                    : modelData === root.currentKeeper ? Style.accent
                                    : Style.border

                        Image {
                            anchors.fill: parent
                            anchors.margins: 2
                            source: "file://" + modelData
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            sourceSize.width: 256
                        }
                        // keeper crown / delete mark
                        Text {
                            anchors.top: parent.top; anchors.left: parent.left; anchors.margins: 3
                            text: modelData === root.currentKeeper ? "★"
                                 : isSelected ? "✗" : ""
                            color: modelData === root.currentKeeper ? "#f1c40f" : "#c0392b"
                            font.pixelSize: 16
                            style: Text.Outline; styleColor: "black"
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                if (root.pairSelectMode) {
                                    if (!root.compareA) {
                                        root.compareA = modelData
                                    } else if (modelData !== root.compareA) {
                                        root.compareB = modelData
                                        root.pairSelectMode = false
                                    }
                                } else if (root.backend) {
                                    root.backend.select_file_qml(modelData)
                                }
                            }
                            onDoubleClicked: if (mainBackend) mainBackend.open_preview(modelData)
                        }
                    }
                }

                // comparator area
                TabBar {
                    id: compareTabs
                    Layout.fillWidth: true
                    visible: root.compareA.length > 0 && root.compareB.length > 0
                    TabButton { text: "Blink" }
                    TabButton { text: "Swipe" }
                    TabButton { text: "Diff" }
                    TabButton { text: "Tethered" }
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: compareTabs.visible
                    currentIndex: compareTabs.currentIndex

                    BlinkComparator { pathA: root.compareA; pathB: root.compareB }
                    SwipeCompare   { pathA: root.compareA; pathB: root.compareB }
                    DiffMaskView   { pathA: root.compareA; pathB: root.compareB; backend: root.backend }
                    TetheredViewport { paths: (root.compareA && root.compareB) ? [root.compareA, root.compareB] : [] }
                }

                Text {
                    visible: !compareTabs.visible
                    Layout.fillWidth: true
                    text: root.pairSelectMode
                          ? (root.compareA ? "Now pick image B…" : "Pick image A…")
                          : "Click Compare, then pick two images to open the visual comparators.\nClick a thumbnail to mark ✗ for deletion; ★ = triage keeper."
                    color: Style.mutedText
                    font.pixelSize: 11
                    wrapMode: Text.Wrap
                }
            }
        }
    }
}
