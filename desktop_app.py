import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDialog, QVBoxLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtCore import QUrl, Qt

# Set your desired password here
PASSWORD = "1234"

class PasswordDialog(QDialog):
    def __init__(self, prompt="Enter Password"):
        super().__init__()
        self.setWindowTitle(prompt)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.accepted = False

        # Layout
        layout = QVBoxLayout()
        self.label = QLabel(prompt)
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)
        self.button = QPushButton("Submit")
        self.button.clicked.connect(self.check_password)

        # Add widgets
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.button)
        self.setLayout(layout)

    def check_password(self):
        if self.input.text() == PASSWORD:
            self.accepted = True
            self.accept()
        else:
            QMessageBox.warning(self, "Incorrect", "Incorrect password. Please try again.")

class KioskApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # Restrict window features (no close button)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowMinimizeButtonHint)

        self.setWindowTitle("Secure Kiosk App")
        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        # Enable JavaScript, Local Storage, etc.
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # Load the local server
        self.browser.load(QUrl("http://127.0.0.1:5000/"))

        # Show in full screen
        self.showFullScreen()

    def closeEvent(self, event):
        # Prompt for password on close attempt
        dialog = PasswordDialog("Enter Password to Exit")
        if dialog.exec_() and dialog.accepted:
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        # Optional: allow exiting with Esc or Q (with password prompt)
        if event.key() in [Qt.Key_Escape, Qt.Key_Q]:
            self.close()

def main():
    app = QApplication(sys.argv)

    # Prompt for password before launching the app
    login = PasswordDialog("Enter Password to Start")
    if not (login.exec_() and login.accepted):
        sys.exit()

    # Launch main window
    window = KioskApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
