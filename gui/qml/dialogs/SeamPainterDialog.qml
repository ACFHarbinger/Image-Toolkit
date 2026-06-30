/*!
    \qmltype SeamPainterDialog
    \inqmlmodule ImageToolkit.Dialogs
    \brief HITL checkpoint 4.5 — post-composite seam painter.

    SeamPainterDialog shows the finished composite canvas with an interactive
    paint brush.  The user paints over seam regions that look wrong; the
    painted area becomes a hard cost barrier in the DP seam map, forcing the
    seam to re-route around the marked zone.

    \list
      \li "Re-Composite" sends the paint mask back to the worker, which
          re-runs Stage 11 with the mask as an additional exclusion zone.
      \li "Accept Output" accepts the current composite without re-routing.
      \li "Cancel" aborts the pipeline.
    \endlist

    Backend (\l backend) must expose:
    \list
      \li \c canvasImage — string URL of the canvas composite.
      \li \c brushSize — int (read/write), brush radius in display pixels.
      \li \c isPainting — bool, true while re-compositing.
      \li \c addStroke(points) — slot; \a points is a list of \c {x,y} objects
          (normalised 0–1).
      \li \c clearMask() — slot.
      \li \c reComposite() — slot.
      \li \c accept() — slot.
      \li \c cancel() — slot.
    \endlist

    \qmlproperty var SeamPainterDialog::backend
    Pipeline HITL backend.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"
import "../components"

Rectangle {
    id: root

    property var backend: null
    signal reComposited()
    signal accepted()
    signal cancelled()

    // Active stroke accumulator
    property var _stroke: []

    color: Style.background
    border.color: Style.border
    radius: Style.borderRadius
    implicitWidth: 700
    implicitHeight: 620

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        Text { text: "Seam Painter"; color: Style.text; font.pixelSize: 18; font.bold: true }
        Text {
            text: "Paint over seam artefacts to force the DP seam to re-route around marked regions."
            color: Style.mutedText; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true
        }

        // Brush size control
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text { text: "Brush Size:"; color: Style.text }
            Slider {
                id: brushSlider
                Layout.fillWidth: true
                from: 5; to: 80; stepSize: 1
                value: backend ? backend.brushSize : 18
                onMoved: if (backend) backend.brushSize = Math.round(value)
            }
            Text { text: Math.round(brushSlider.value) + " px"; color: Style.mutedText; Layout.preferredWidth: 50 }
            AppButton {
                text: "Clear Mask"
                Layout.preferredWidth: 100
                onClicked: if (backend) backend.clearMask()
            }
        }

        // Canvas + paint overlay
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#000000"
            border.color: Style.border
            clip: true

            Image {
                id: canvasImg
                anchors.fill: parent
                source: backend ? backend.canvasImage : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }

            // Paint strokes rendered as Canvas overlay
            Canvas {
                id: paintCanvas
                anchors.fill: parent
                opacity: 0.6

                property var _pendingStrokes: []

                function drawStroke(points, brushPx) {
                    var ctx = getContext("2d")
                    ctx.strokeStyle = "rgba(255,60,60,0.8)"
                    ctx.lineWidth = brushPx
                    ctx.lineCap = "round"
                    ctx.lineJoin = "round"
                    if (points.length < 2) return
                    ctx.beginPath()
                    ctx.moveTo(points[0].x, points[0].y)
                    for (var i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y)
                    ctx.stroke()
                    requestPaint()
                }

                onPaint: {
                    for (var i = 0; i < _pendingStrokes.length; i++) {
                        drawStroke(_pendingStrokes[i].pts, _pendingStrokes[i].brush)
                    }
                    _pendingStrokes = []
                }
            }

            MouseArea {
                id: paintArea
                anchors.fill: parent
                cursorShape: Qt.CrossCursor
                property var _pts: []

                onPressed: _pts = [{ x: mouse.x, y: mouse.y }]
                onPositionChanged: {
                    if (_pts.length === 0) return
                    _pts.push({ x: mouse.x, y: mouse.y })
                    paintCanvas._pendingStrokes.push({ pts: _pts.slice(-2), brush: brushSlider.value })
                    paintCanvas.requestPaint()
                }
                onReleased: {
                    // Normalise and send stroke to backend
                    if (backend && _pts.length > 0) {
                        var norm = _pts.map(function(p) {
                            return {
                                x: (p.x - (canvasImg.width - canvasImg.paintedWidth) / 2) / canvasImg.paintedWidth,
                                y: (p.y - (canvasImg.height - canvasImg.paintedHeight) / 2) / canvasImg.paintedHeight
                            }
                        })
                        backend.addStroke(norm)
                    }
                    _pts = []
                }
            }

            ProgressBar {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                indeterminate: true
                visible: backend ? backend.isPainting : false
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Item { Layout.fillWidth: true }
            AppButton {
                text: "Cancel"
                background: Rectangle { color: "#e74c3c"; radius: Style.borderRadius }
                onClicked: { if (backend) backend.cancel(); root.cancelled() }
            }
            AppButton {
                text: "Accept Output"
                onClicked: { if (backend) backend.accept(); root.accepted() }
            }
            AppButton {
                text: "Re-Composite"
                background: Rectangle { color: "#27ae60"; radius: Style.borderRadius }
                enabled: !(backend && backend.isPainting)
                onClicked: { if (backend) backend.reComposite(); root.reComposited() }
            }
        }
    }
}
