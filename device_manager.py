"""
Cross-platform removable/USB storage device detection.

Each OS exposes disk information very differently, so this module dispatches
to a platform-specific implementation but always returns a normalized list
of StorageDevice objects.

Author: AlphinGJ
GitHub: https://github.com/alphingj
"""
import json
import plistlib
import subprocess
from dataclasses import dataclass, field
from typing import List

from utils import get_platform, human_size


@dataclass
class StorageDevice:
    device_path: str                       # e.g. /dev/sdb, /dev/disk2, \\.\PhysicalDrive1
    display_id: str                        # short id (sdb, disk2, PhysicalDrive1)
    model: str = "Unknown device"
    vendor: str = ""
    size_bytes: int = 0
    is_removable: bool = True
    bus: str = ""
    partitions: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        size = human_size(self.size_bytes) if self.size_bytes else "Unknown size"
        name = f"{self.vendor} {self.model}".strip()
        return f"{name} — {size} ({self.device_path})"


class DeviceManager:
    """Detects connected removable/USB storage devices on the current OS."""

    def list_devices(self) -> List[StorageDevice]:
        plat = get_platform()
        if plat == "linux":
            return self._list_linux()
        if plat == "macos":
            return self._list_macos()
        if plat == "windows":
            return self._list_windows()
        return []

    # ---------------------------------------------------------------- Linux
    def _list_linux(self) -> List[StorageDevice]:
        devices = []
        try:
            out = subprocess.check_output(
                [
                    "lsblk", "-J", "-b", "-o",
                    "NAME,PATH,SIZE,MODEL,VENDOR,TRAN,TYPE,RM,RO,MOUNTPOINT",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(out)
        except Exception:
            return devices

        for entry in data.get("blockdevices", []):
            if entry.get("type") != "disk":
                continue
            removable = entry.get("rm") in (True, "1", 1)
            tran = (entry.get("tran") or "").lower()
            # Only offer disks that are flagged removable and/or USB attached,
            # so internal system drives never show up in the picker.
            if not (removable or tran == "usb"):
                continue
            if entry.get("ro") in (True, "1", 1):
                continue  # skip read-only media

            children = entry.get("children", []) or []
            partitions = [c.get("path") for c in children if c.get("path")]

            devices.append(
                StorageDevice(
                    device_path=entry.get("path"),
                    display_id=entry.get("name"),
                    model=(entry.get("model") or "Unknown device").strip(),
                    vendor=(entry.get("vendor") or "").strip(),
                    size_bytes=int(entry.get("size") or 0),
                    is_removable=True,
                    bus=tran or "removable",
                    partitions=partitions,
                )
            )
        return devices

    # ---------------------------------------------------------------- macOS
    def _list_macos(self) -> List[StorageDevice]:
        devices = []
        try:
            out = subprocess.check_output(
                ["diskutil", "list", "-plist", "physical"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            plist = plistlib.loads(out.encode("utf-8"))
        except Exception:
            return devices

        for disk_id in plist.get("WholeDisks", []):
            try:
                info_out = subprocess.check_output(
                    ["diskutil", "info", "-plist", disk_id],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                info = plistlib.loads(info_out.encode("utf-8"))
            except Exception:
                continue

            # Only list external, physically removable USB-class media so
            # the internal boot disk can never be selected by mistake.
            is_internal = info.get("Internal", True)
            protocol = (info.get("BusProtocol") or "").lower()
            if is_internal:
                continue
            if protocol not in ("usb", "thunderbolt", "secure digital", "card reader"):
                continue

            devices.append(
                StorageDevice(
                    device_path=f"/dev/{disk_id}",
                    display_id=disk_id,
                    model=info.get("MediaName") or info.get("IORegistryEntryName") or "Unknown device",
                    vendor="",
                    size_bytes=int(info.get("TotalSize") or 0),
                    is_removable=True,
                    bus=protocol,
                )
            )
        return devices

    # -------------------------------------------------------------- Windows
    def _list_windows(self) -> List[StorageDevice]:
        devices = []
        ps_cmd = (
            "Get-Disk | Where-Object {$_.BusType -eq 'USB'} | "
            "Select-Object Number, FriendlyName, Size, BusType | ConvertTo-Json"
        )
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if not out:
                return devices
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
        except Exception:
            return devices

        for entry in data:
            number = entry.get("Number")
            devices.append(
                StorageDevice(
                    device_path=rf"\\.\PhysicalDrive{number}",
                    display_id=f"PhysicalDrive{number}",
                    model=entry.get("FriendlyName") or "Unknown device",
                    vendor="",
                    size_bytes=int(entry.get("Size") or 0),
                    is_removable=True,
                    bus="usb",
                )
            )
        return devices
