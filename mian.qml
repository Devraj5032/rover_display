import QtQuick 2.15
import QtQuick.Window 2.15
import QtWebEngine 1.15

Window {
    visible: true
    width: 1200
    height: 800
    title: qsTr("Web Viewer App")

    WebEngineView {
        id: webview
        anchors.fill: parent
        url: "http://localhost:5000/"  // 🔁 Replace this with your URL
    }
}
