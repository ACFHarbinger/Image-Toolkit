/*!
    \qmltype ConfidenceRing
    \inqmlmodule ImageToolkit.Components
    \brief Circular progress ring showing a 0–1 confidence as a percentage.
*/
import QtQuick 2.15
import "../"

Item {
    id: root
    property real value: 0.0        // 0..1
    property int ringWidth: 10
    property color ringColor: {
        if (value >= 0.85) return "#2ecc71"
        if (value >= 0.6) return "#f1c40f"
        if (value > 0) return "#e67e22"
        return Style.border
    }
    width: 120
    height: 120

    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var cx = width / 2, cy = height / 2
            var r = Math.min(cx, cy) - root.ringWidth
            // track
            ctx.beginPath()
            ctx.arc(cx, cy, r, 0, 2 * Math.PI)
            ctx.lineWidth = root.ringWidth
            ctx.strokeStyle = Style.border
            ctx.stroke()
            // value arc
            ctx.beginPath()
            ctx.arc(cx, cy, r, -Math.PI / 2,
                    -Math.PI / 2 + 2 * Math.PI * Math.max(0, Math.min(1, root.value)))
            ctx.lineWidth = root.ringWidth
            ctx.strokeStyle = root.ringColor
            ctx.lineCap = "round"
            ctx.stroke()
        }
    }
    onValueChanged: canvas.requestPaint()
    onRingColorChanged: canvas.requestPaint()

    Text {
        anchors.centerIn: parent
        text: Math.round(root.value * 100) + "%"
        color: Style.text
        font.pixelSize: 24
        font.bold: true
    }
}
