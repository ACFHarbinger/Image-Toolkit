import QtQuick 2.15

// Draggable, resizable bounding-box overlay for the reverse-search preview.
// Emits normalized [x, y, width, height] (0.0-1.0 relative to the source
// image) whenever the selection changes, plus the pixel-space rect the C++
// core actually needs.
Item {
    id: root

    // The Image element this selector is overlaid on. Needed to translate
    // between displayed (possibly letterboxed) coordinates and the source
    // image's native pixel dimensions.
    property Image targetImage: null

    // Emitted with pixel-space coordinates in the *source* image, ready to
    // hand to base.crop_roi(imagePath, x, y, w, h).
    signal roiChanged(int x, int y, int width, int height)
    signal roiCommitted(int x, int y, int width, int height)

    property real minSize: 24 // minimum marquee side, in view pixels

    // Current selection in view-local coordinates.
    property rect selection: Qt.rect(0, 0, 0, 0)
    property bool hasSelection: selection.width > minSize && selection.height > minSize

    anchors.fill: parent

    // --- Drawing surface ------------------------------------------------
    // Dim everything outside the selection using four border rectangles
    // (version-safe; avoids QtQuick.Shapes PathRectangle which needs Qt 6.5+).
    Item {
        anchors.fill: parent
        visible: root.hasSelection
        property color dim: "#00000066"

        Rectangle {  // top
            color: parent.dim
            x: 0; y: 0; width: root.width; height: root.selection.y
        }
        Rectangle {  // bottom
            color: parent.dim
            x: 0; y: root.selection.y + root.selection.height
            width: root.width
            height: Math.max(0, root.height - (root.selection.y + root.selection.height))
        }
        Rectangle {  // left
            color: parent.dim
            x: 0; y: root.selection.y
            width: root.selection.x; height: root.selection.height
        }
        Rectangle {  // right
            color: parent.dim
            x: root.selection.x + root.selection.width; y: root.selection.y
            width: Math.max(0, root.width - (root.selection.x + root.selection.width))
            height: root.selection.height
        }
    }

    // Selection border
    Rectangle {
        visible: root.hasSelection
        x: root.selection.x; y: root.selection.y
        width: root.selection.width; height: root.selection.height
        color: "transparent"
        border.color: "#00d1ff"
        border.width: 2
    }

    // --- Interaction: draw a new box -----------------------------------
    MouseArea {
        id: drawArea
        anchors.fill: parent
        enabled: !root.hasSelection
        property point start

        onPressed: (mouse) => { start = Qt.point(mouse.x, mouse.y) }
        onPositionChanged: (mouse) => {
            if (pressed) {
                root.selection = Qt.rect(
                    Math.min(start.x, mouse.x), Math.min(start.y, mouse.y),
                    Math.abs(mouse.x - start.x), Math.abs(mouse.y - start.y))
                root._emitLive()
            }
        }
        onReleased: root._commit()
    }

    // --- Interaction: move/resize existing box --------------------------
    Rectangle {
        id: handle
        visible: root.hasSelection
        x: root.selection.x; y: root.selection.y
        width: root.selection.width; height: root.selection.height
        color: "transparent"
        border.width: 0

        MouseArea {
            anchors.fill: parent
            drag.target: parent
            drag.axis: Drag.XAndYAxis
            onPositionChanged: {
                root.selection = Qt.rect(handle.x, handle.y,
                                          root.selection.width, root.selection.height)
                root._emitLive()
            }
            onReleased: root._commit()
        }

        // Corner resize handle (bottom-right); duplicate for other corners
        // in a full implementation.
        Rectangle {
            width: 12; height: 12
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            color: "#00d1ff"
            radius: 2
            MouseArea {
                anchors.fill: parent
                drag.target: parent
                onPositionChanged: {
                    root.selection = Qt.rect(
                        root.selection.x, root.selection.y,
                        Math.max(root.minSize, handle.x + handle.width - root.selection.x),
                        Math.max(root.minSize, handle.y + handle.height - root.selection.y))
                    root._emitLive()
                }
                onReleased: root._commit()
            }
        }
    }

    function clearSelection() {
        selection = Qt.rect(0, 0, 0, 0)
    }

    // Translate a view-space rect into source-image pixel coordinates,
    // accounting for Image.fillMode letterboxing (assumes PreserveAspectFit).
    function _toSourcePixels(r) {
        if (!targetImage || targetImage.sourceSize.width <= 0)
            return Qt.rect(0, 0, 0, 0)

        var iw = targetImage.sourceSize.width
        var ih = targetImage.sourceSize.height
        var scale = Math.min(targetImage.width / iw, targetImage.height / ih)
        var dispW = iw * scale
        var dispH = ih * scale
        var offX = targetImage.x + (targetImage.width - dispW) / 2
        var offY = targetImage.y + (targetImage.height - dispH) / 2

        var sx = Math.max(0, (r.x - offX) / scale)
        var sy = Math.max(0, (r.y - offY) / scale)
        var sw = Math.min(iw - sx, r.width / scale)
        var sh = Math.min(ih - sy, r.height / scale)

        return Qt.rect(Math.round(sx), Math.round(sy), Math.round(sw), Math.round(sh))
    }

    function _emitLive() {
        var px = _toSourcePixels(selection)
        roiChanged(px.x, px.y, px.width, px.height)
    }

    function _commit() {
        drawArea.enabled = !hasSelection
        if (hasSelection) {
            var px = _toSourcePixels(selection)
            roiCommitted(px.x, px.y, px.width, px.height)
        }
    }
}
