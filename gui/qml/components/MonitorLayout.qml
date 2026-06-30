/*!
    \qmltype MonitorLayout
    \inqmlmodule ImageToolkit.Components
    \brief Responsive flow container of MonitorWidget instances.

    MonitorLayout is a \l ScrollView containing a \l Flow of \l MonitorWidget
    elements.  Add and move transitions are animated so that widgets reflow
    smoothly when the window is resized.

    \note The current implementation hard-codes three example monitors
    (MON1–MON3).  A future version will accept a dynamic model exposed by the
    wallpaper backend.
*/
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../"

ScrollView {
    id: root
    clip: true
    Layout.fillWidth: true
    Layout.fillHeight: true
    
    Flow {
        id: flow
        width: root.width - 20
        anchors.margins: 10
        spacing: 20
        
        // Example monitors
        Repeater {
            model: 3
            MonitorWidget {
                monitorId: "MON" + (index + 1)
                monitorName: "Monitor " + (index + 1)
            }
        }
        
        add: Transition {
            NumberAnimation { properties: "opacity,scale"; from: 0; to: 1; duration: 200 }
        }
        
        move: Transition {
            NumberAnimation { properties: "x,y"; duration: 200; easing.type: Easing.OutBounce }
        }
    }
}

