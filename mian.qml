import QtQuick 2.12
import QtQuick.Window 2.12
import QtWebEngine 1.7

Window {
    visible: true
    width: 1200
    height: 800
    title: qsTr("Web Viewer App")

    WebEngineView {
        id: webview
        anchors.fill: parent
        url: "http://localhost:5000/"
    }
}
