import sys
from PySide2.QtWidgets import QApplication
from PySide2.QtQml import QQmlApplicationEngine
from PySide2.QtWebEngineWidgets import QWebEngineView
from PySide2 import QtWebEngine

if __name__ == "__main__":
    QtWebEngine.QtWebEngine.initialize()
    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()
    engine.load("main.qml")

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec_())  # Note: `exec_()` in Qt5
