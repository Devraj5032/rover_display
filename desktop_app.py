import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDialog, QVBoxLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtCore import QUrl, Qt

PASSWORD = "1234"

class PasswordDialog(QDialog):
    def __init__(self, prompt="Enter Password"):
        super().__init__()
        self.setWindowTitle(prompt)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        layout = QVBoxLayout()
        self.label = QLabel(prompt)
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)
        self.btn = QPushButton("Submit")
        self.btn.clicked.connect(self.check_password)
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.btn)
        self.setLayout(layout)
        self.accepted = False

    def check_password(self):
        if self.input.text() == PASSWORD:
            self.accepted = True
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Incorrect Password")

class KioskApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure Kiosk App")
        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        # Enable JavaScript and WebSockets
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # Load the local Flask server
        self.browser.load(QUrl("http://127.0.0.1:5000/"))

        self.showFullScreen()

    def closeEvent(self, event):
        dialog = PasswordDialog("Enter Password to Exit")
        if dialog.exec_() and dialog.accepted:
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() in [Qt.Key_Escape, Qt.Key_Q]:
            self.close()

def main():
    app = QApplication(sys.argv)

    password_prompt = PasswordDialog("Enter Password to Start")
    if not (password_prompt.exec_() and password_prompt.accepted):
        sys.exit()

    window = KioskApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
