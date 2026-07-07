/*!
    \qmltype DiffMaskView
    \inqmlmodule ImageToolkit.Components
    \brief Difference-mask (XOR) viewer — asks the backend to render the
           neon-green pixel-alteration mask for a pair of images.
*/
import QtQuick 2.15
import "../"

Rectangle {
    id: root
    property string pathA: ""
    property string pathB: ""
    property var backend: null   // SimilarityTab backend object
    property string maskPath: ""
    property real changedRatio: -1

    color: "black"

    onPathAChanged: refresh()
    onPathBChanged: refresh()
    Component.onCompleted: refresh()

    function refresh() {
        maskPath = ""
        changedRatio = -1
        if (backend && pathA && pathB)
            maskPath = backend.generate_diff(pathA, pathB)
    }

    Connections {
        target: root.backend
        function onDiff_ready(path, ratio) {
            if (path === root.maskPath)
                root.changedRatio = ratio
        }
    }

    Image {
        anchors.fill: parent
        source: root.maskPath ? "file://" + root.maskPath : ""
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        cache: false
    }

    Text {
        anchors.centerIn: parent
        visible: !root.maskPath
        text: "Rendering difference mask..."
        color: Style.mutedText
    }

    Rectangle {
        visible: root.changedRatio >= 0
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.margins: 10
        width: ratioText.width + 20
        height: ratioText.height + 10
        radius: Style.borderRadius
        color: "#cc000000"
        Text {
            id: ratioText
            anchors.centerIn: parent
            text: (root.changedRatio * 100).toFixed(2) + "% of pixels differ"
            color: "#39FF66"
            font.bold: true
        }
    }
}
