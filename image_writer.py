"""
Cross-platform raw image writer (DD/Etcher-style) with progress reporting.

This writes the image byte-for-byte onto the target device. It works well
for modern hybrid ISO/IMG files (Ubuntu, Fedora, Debian, Raspberry Pi OS,
etc.) the same way `dd`, Rufus's "DD image" mode, or balenaEtcher do.

Note: official Windows install ISOs (>4GB install.wim, needing a FAT32 +
NTFS dual-partition layout for old BIOS systems) are a special case that
Rufus handles with extra partitioning logic; that is out of scope here.
Raw DD-mode writing of a Windows ISO still works for UEFI-only boots.

Author: AlphinGJ
GitHub: https://github.com/alphingj
"""
import os
import subprocess
import time

from PyQt6.QtCore import QThread, pyqtSignal

from utils import get_platform, human_size
from device_manager import StorageDevice

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB


class WriteError(Exception):
    pass


class ImageWriterThread(QThread):
    progress_changed = pyqtSignal(int, str)   # percent, status text
    log_message = pyqtSignal(str)
    finished_ok = pyqtSignal()
    finished_error = pyqtSignal(str)

    def __init__(self, image_path: str, device: StorageDevice, verify: bool = False):
        super().__init__()
        self.image_path = image_path
        self.device = device
        self.verify = verify
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._unmount_device()
            self._write_image()
            if not self._cancelled and self.verify:
                self._verify_image()
            self._finalize_device()
            if self._cancelled:
                self.finished_error.emit("Cancelled by user.")
            else:
                self.finished_ok.emit()
        except WriteError as exc:
            self.finished_error.emit(str(exc))
        except PermissionError:
            self.finished_error.emit(
                "Permission denied. Re-run this app as Administrator (Windows) "
                "or with sudo (Linux/macOS)."
            )
        except Exception as exc:  # noqa: BLE001
            self.finished_error.emit(f"Unexpected error: {exc}")

    # ------------------------------------------------------------ unmount
    def _unmount_device(self):
        plat = get_platform()
        self.log_message.emit("Unmounting target device...")
        if plat == "linux":
            for part in self.device.partitions:
                subprocess.run(["umount", part], stderr=subprocess.DEVNULL)
        elif plat == "macos":
            subprocess.run(
                ["diskutil", "unmountDisk", self.device.device_path], check=False
            )
        elif plat == "windows":
            disk_number = self.device.display_id.replace("PhysicalDrive", "")
            self._run_diskpart(f"select disk {disk_number}\noffline disk\n")

    def _run_diskpart(self, script: str):
        tmp_path = os.path.join(os.environ.get("TEMP", "."), "_imgburn_diskpart.txt")
        with open(tmp_path, "w") as fh:
            fh.write(script)
        try:
            subprocess.run(["diskpart", "/s", tmp_path], check=False, capture_output=True)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    # -------------------------------------------------------------- write
    def _write_image(self):
        total_size = os.path.getsize(self.image_path)
        if self.device.size_bytes and total_size > self.device.size_bytes:
            raise WriteError(
                "Image is larger than the target device "
                f"({human_size(total_size)} > {human_size(self.device.size_bytes)})."
            )

        self.log_message.emit(f"Writing {human_size(total_size)} to {self.device.device_path} ...")

        written = 0
        start_time = time.time()
        last_emit = 0.0

        with open(self.image_path, "rb", buffering=0) as src, \
                open(self.device.device_path, "wb", buffering=0) as dst:
            while True:
                if self._cancelled:
                    return
                chunk = src.read(CHUNK_SIZE)
                if not chunk:
                    break
                dst.write(chunk)
                written += len(chunk)

                now = time.time()
                if now - last_emit > 0.25 or written == total_size:
                    last_emit = now
                    percent = int(written * 100 / total_size) if total_size else 0
                    elapsed = max(now - start_time, 0.001)
                    speed = written / elapsed
                    status = f"{human_size(written)} / {human_size(total_size)} @ {human_size(speed)}/s"
                    self.progress_changed.emit(percent, status)

            dst.flush()
            os.fsync(dst.fileno())

    # ------------------------------------------------------------- verify
    def _verify_image(self):
        self.log_message.emit("Verifying written data...")
        total_size = os.path.getsize(self.image_path)
        read_back = 0
        start_time = time.time()
        last_emit = 0.0

        with open(self.image_path, "rb", buffering=0) as src, \
                open(self.device.device_path, "rb", buffering=0) as dst:
            while read_back < total_size:
                if self._cancelled:
                    return
                a = src.read(CHUNK_SIZE)
                if not a:
                    break
                b = dst.read(len(a))
                if a != b:
                    raise WriteError(f"Verification mismatch at byte offset {read_back}.")
                read_back += len(a)

                now = time.time()
                if now - last_emit > 0.25 or read_back == total_size:
                    last_emit = now
                    percent = int(read_back * 100 / total_size) if total_size else 0
                    elapsed = max(now - start_time, 0.001)
                    speed = read_back / elapsed
                    status = f"Verifying: {human_size(read_back)} / {human_size(total_size)} @ {human_size(speed)}/s"
                    self.progress_changed.emit(percent, status)

    # ------------------------------------------------------------ finalize
    def _finalize_device(self):
        plat = get_platform()
        self.log_message.emit("Flushing buffers...")
        if plat == "linux":
            subprocess.run(["sync"], check=False)
            subprocess.run(
                ["udisksctl", "power-off", "-b", self.device.device_path],
                stderr=subprocess.DEVNULL,
            )
        elif plat == "macos":
            subprocess.run(["diskutil", "eject", self.device.device_path], check=False)
        elif plat == "windows":
            disk_number = self.device.display_id.replace("PhysicalDrive", "")
            self._run_diskpart(f"select disk {disk_number}\nonline disk\n")
        self.log_message.emit("Done.")
