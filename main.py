#!/usr/bin/env python3
"""
USB Image Burner - cross-platform OS image flashing tool (Windows/macOS/Linux)
Entry point for the application.

Author: AlphinGJ
GitHub: https://github.com/alphingj
"""
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from main_window import MainWindow
from utils import is_admin, relaunch_as_admin


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("USB Image Burner")
    app.setStyle("Fusion")

    if not is_admin():
        choice = QMessageBox.question(
            None,
            "Administrator privileges required",
            "Writing raw images to USB devices requires administrator/root "
            "privileges.\n\nDo you want to relaunch with elevated privileges now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if choice == QMessageBox.StandardButton.Yes:
            if relaunch_as_admin():
                sys.exit(0)
            else:
                QMessageBox.warning(
                    None,
                    "Could not elevate automatically",
                    "Please restart this application manually as Administrator "
                    "(Windows) or with sudo (Linux/macOS).",
                )

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
