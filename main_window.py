"""
Main application window for USB Image Burner.

Author: AlphinGJ
GitHub: https://github.com/alphingj
"""
import os
from typing import List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QProgressBar, QPlainTextEdit, QCheckBox,
    QFileDialog, QMessageBox, QGroupBox, QSizePolicy,
)

from device_manager import DeviceManager, StorageDevice
from image_writer import ImageWriterThread
from utils import human_size, get_platform


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("USB Image Burner")
        self.resize(640, 560)

        self.device_manager = DeviceManager()
        self.devices: List[StorageDevice] = []
        self.writer_thread: Optional[ImageWriterThread] = None

        self._build_ui()
        self.refresh_devices()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Image selection -------------------------------------------------
        image_box = QGroupBox("OS image")
        image_layout = QHBoxLayout(image_box)
        self.image_path_edit = QLineEdit()
        self.image_path_edit.setReadOnly(True)
        self.image_path_edit.setPlaceholderText("Select an .iso/.img file...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_image)
        image_layout.addWidget(self.image_path_edit)
        image_layout.addWidget(browse_btn)
        layout.addWidget(image_box)

        # --- Device selection --------------------------------------------------
        device_box = QGroupBox("Target device")
        device_layout = QHBoxLayout(device_box)
        self.device_combo = QComboBox()
        self.device_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(refresh_btn)
        layout.addWidget(device_box)

        # --- Options -------------------------------------------------------
        options_box = QGroupBox("Options")
        options_layout = QVBoxLayout(options_box)
        self.verify_checkbox = QCheckBox("Verify written data after burning (slower)")
        self.confirm_checkbox = QCheckBox(
            "I understand this will permanently erase all data on the selected device"
        )
        options_layout.addWidget(self.verify_checkbox)
        options_layout.addWidget(self.confirm_checkbox)
        layout.addWidget(options_box)

        # --- Progress --------------------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready.")
        layout.addWidget(self.status_label)

        # --- Log -------------------------------------------------------------
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        layout.addWidget(self.log_view)

        # --- Action buttons ----------------------------------------------------
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Burn")
        self.start_btn.clicked.connect(self.start_burn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_burn)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        platform_note = QLabel(f"Running on: {get_platform().capitalize()}")
        platform_note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(platform_note)

    # --------------------------------------------------------------- logic
    def browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OS image",
            "",
            "Disk images (*.iso *.img *.raw);;All files (*)",
        )
        if path:
            self.image_path_edit.setText(path)
            self.log(f"Selected image: {path} ({human_size(os.path.getsize(path))})")

    def refresh_devices(self):
        self.device_combo.clear()
        self.devices = self.device_manager.list_devices()
        if not self.devices:
            self.device_combo.addItem("No removable USB devices found")
            self.log("No removable USB devices detected. Plug in a USB drive and click Refresh.")
            return
        for dev in self.devices:
            self.device_combo.addItem(dev.label, dev)
        self.log(f"Found {len(self.devices)} removable device(s).")

    def log(self, message: str):
        self.log_view.appendPlainText(message)

    def start_burn(self):
        image_path = self.image_path_edit.text().strip()
        if not image_path or not os.path.isfile(image_path):
            QMessageBox.warning(self, "No image selected", "Please select a valid image file.")
            return

        device = self.device_combo.currentData()
        if device is None:
            QMessageBox.warning(self, "No device selected", "Please select a target USB device.")
            return

        if not self.confirm_checkbox.isChecked():
            QMessageBox.warning(
                self,
                "Confirmation required",
                "Please check the confirmation box acknowledging data loss before burning.",
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm erase",
            f"This will ERASE ALL DATA on:\n\n{device.label}\n\n"
            "This action cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting...")

        self.writer_thread = ImageWriterThread(
            image_path, device, verify=self.verify_checkbox.isChecked()
        )
        self.writer_thread.progress_changed.connect(self.on_progress)
        self.writer_thread.log_message.connect(self.log)
        self.writer_thread.finished_ok.connect(self.on_finished_ok)
        self.writer_thread.finished_error.connect(self.on_finished_error)
        self.writer_thread.start()

    def cancel_burn(self):
        if self.writer_thread:
            self.log("Cancelling...")
            self.writer_thread.cancel()
            self.cancel_btn.setEnabled(False)

    def on_progress(self, percent: int, status: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(status)

    def on_finished_ok(self):
        self.status_label.setText("Burn completed successfully.")
        self.log("Burn completed successfully.")
        self._reset_buttons()
        QMessageBox.information(self, "Done", "The image was written successfully.")

    def on_finished_error(self, message: str):
        self.status_label.setText(f"Failed: {message}")
        self.log(f"ERROR: {message}")
        self._reset_buttons()
        QMessageBox.critical(self, "Error", message)

    def _reset_buttons(self):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.writer_thread = None
