import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"
import ".."

ApplicationWindow {
    id: window
    width: 450
    height: 600
    visible: true
    title: "Image Toolkit - Login"
    color: Style.background

    ColumnLayout {
        anchors.centerIn: parent
        width: parent.width * 0.85
        spacing: 25

        // Header
        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 5
            Text {
                text: "IMAGE TOOLKIT"
                font.pixelSize: 28
                font.bold: true
                color: Style.accent
                Layout.alignment: Qt.AlignHCenter
            }
            Text {
                text: isLoginMode ? "Welcome Back" : "Create Account"
                font.pixelSize: 16
                color: Style.text
                opacity: 0.7
                Layout.alignment: Qt.AlignHCenter
            }
        }

        // Form
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 15

            TextField {
                id: usernameField
                placeholderText: "Username"
                Layout.fillWidth: true
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 8 }
                color: Style.text
                padding: 12
            }

            TextField {
                id: passwordField
                placeholderText: "Password"
                echoMode: TextInput.Password
                Layout.fillWidth: true
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 8 }
                color: Style.text
                padding: 12
            }

            TextField {
                id: confirmPasswordField
                placeholderText: "Confirm Password"
                echoMode: TextInput.Password
                visible: !isLoginMode
                Layout.fillWidth: true
                background: Rectangle { color: Style.secondaryBackground; border.color: Style.border; radius: 8 }
                color: Style.text
                padding: 12
            }
        }

        // Actions
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 15

            AppButton {
                text: isLoginMode ? "Login" : "Register"
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                background: Rectangle {
                    color: Style.accent
                    radius: 8
                }
            }

            Text {
                text: isLoginMode ? "Don't have an account? <b>Sign Up</b>" : "Already have an account? <b>Login</b>"
                color: Style.text
                Layout.alignment: Qt.AlignHCenter
                font.pixelSize: 14
                
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: isLoginMode = !isLoginMode
                }
            }
        }
    }

    property bool isLoginMode: true

    footer: RowLayout {
        width: parent.width
        height: 40
        anchors.margins: 10
        Item { Layout.fillWidth: true }
        Text {
            text: "v1.2.0"
            color: Style.text
            opacity: 0.4
            font.pixelSize: 12
        }
    }
}
