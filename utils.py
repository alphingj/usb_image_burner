"""
Small cross-platform helper utilities used across the app:
- platform detection
- admin/root privilege checks and elevation
- human-readable byte formatting

Author: AlphinGJ
GitHub: https://github.com/alphingj
"""
import sys
import os
import ctypes
import subprocess
import platform
from shutil import which


def get_platform() -> str:
    """Return a normalized platform string: 'windows', 'macos', or 'linux'."""
    sysname = platform.system().lower()
    if sysname.startswith("win"):
        return "windows"
    if sysname == "darwin":
        return "macos"
    return "linux"


def is_admin() -> bool:
    """Check whether the current process has administrator/root rights."""
    try:
        if get_platform() == "windows":
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        else:
            return os.geteuid() == 0
    except Exception:
        return False


def command_exists(cmd: str) -> bool:
    return which(cmd) is not None


def relaunch_as_admin() -> bool:
    """
    Attempt to relaunch the current script with elevated privileges.

    Returns True if a relaunch was successfully *initiated* (the caller
    should exit the current process afterwards), False if elevation could
    not be started automatically.
    """
    plat = get_platform()
    try:
        if plat == "windows":
            params = " ".join(f'"{a}"' for a in sys.argv)
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, params, None, 1
            )
            return True

        # Linux/macOS: there is no single portable "self elevate" API for a
        # running GUI process, so we shell out to a known privilege helper
        # and relaunch the script as a brand-new elevated process.
        script = os.path.abspath(sys.argv[0])
        if plat == "linux" and command_exists("pkexec"):
            subprocess.Popen(["pkexec", sys.executable, script, *sys.argv[1:]])
            return True

        if plat == "macos":
            quoted_args = " ".join(sys.argv[1:])
            cmd = (
                f'do shell script "{sys.executable} {script} {quoted_args}" '
                f'with administrator privileges'
            )
            subprocess.Popen(["osascript", "-e", cmd])
            return True
    except Exception:
        return False
    return False


def human_size(num_bytes: int) -> str:
    """Convert a byte count into a human readable string (e.g. '3.7 GB')."""
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(num_bytes)
    for unit in units:
        if size < step:
            return f"{size:.1f} {unit}"
        size /= step
    return f"{size:.1f} EB"
