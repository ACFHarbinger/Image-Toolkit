import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import ".."

ApplicationWindow {
    id: window
    width: 400
    height: 500
    visible: true
    title: "Login"
    color: Style.background

    ColumnLayout {
        anchors.centerIn: parent
        width: parent.width * 0.8
        spacing: 20

        Text {
            text: "Authentication"
            color: Style.accent
            font.pixelSize: 28
            font.bold: true
            Layout.alignment: Qt.AlignHCenter
        }

        TextField {
            id: usernameField
            placeholderText: "Username"
            Layout.fillWidth: true
        }

        TextField {
            id: passwordField
            placeholderText: "Password"
            echoMode: TextInput.Password
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            
            AppButton {
                text: "Create Account"
                Layout.fillWidth: true
                onClicked: backend.create_account(usernameField.text, passwordField.text)
            }

            AppButton {
                text: "Login"
                Layout.fillWidth: true
                onClicked: backend.attempt_login(usernameField.text, passwordField.text)
            }
        }
    }
}
