# USB Image Burner

A cross-platform (Windows / macOS / Linux) PyQt6 GUI for writing OS images
(`.iso`, `.img`, `.raw`) onto USB drives — the same "DD/raw write" approach
used by Rufus's *DD Image* mode or balenaEtcher.

**Author:** AlphinGJ
**GitHub:** [https://github.com/alphingj](https://github.com/alphingj)


## ⚠️ Important safety warning

This tool writes **directly to a physical disk device**, overwriting
**everything** on it — partition table included. There is no undo.
Always double-check the device you select before clicking **Burn**. The app
will not let you proceed without ticking an explicit confirmation checkbox
and confirming a final warning dialog, but the responsibility to pick the
right drive is still yours.

## Features

- Detects connected removable/USB drives on Windows, macOS, and any Linux
  distro
- Lets you pick an `.iso`/`.img`/`.raw` file and a target device
- Writes in 4 MiB chunks with a live progress bar, transfer speed, and ETA
- Optional post-write verification (byte-for-byte re-read comparison)
- Automatically unmounts/offlines the device before writing and re-mounts
  it (or ejects it) afterward
- Prompts to relaunch elevated (admin/root) if not already running with
  sufficient privileges, since raw disk access requires it on every OS

## Project layout

```
usb_image_burner/
├── main.py                  # entry point, privilege check
├── utils.py               # platform detection, elevation, formatting
├── device_manager.py      # cross-platform USB device discovery
├── image_writer.py        # background QThread that does the actual write
├── main_window.py         # PyQt6 window/widgets
└── requirements.txt
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Running

Raw disk access needs elevated privileges on every platform.

**Linux / macOS:**
```bash
sudo python3 main.py
```
(or let the app prompt you to relaunch elevated via `pkexec`/`osascript`)

**Windows:**
Run from an **Administrator** PowerShell/Command Prompt:
```powershell
python main.py
```
(or accept the relaunch prompt, which triggers the standard UAC dialog)

## How device detection works per OS

| OS      | Mechanism                                                              |
|---------|-------------------------------------------------------------------------|
| Linux   | `lsblk -J` — filters disks flagged removable or with `TRAN=usb`        |
| macOS   | `diskutil list -plist` + `diskutil info -plist <disk>` — filters non-internal USB/Thunderbolt media |
| Windows | PowerShell `Get-Disk \| Where BusType -eq 'USB'`                       |

Internal/system disks are filtered out by design so they can never appear
in the picker.

## How writing works per OS

1. **Unmount/offline the target** so the OS releases its file handle on the
   raw device:
   - Linux: `umount` each partition
   - macOS: `diskutil unmountDisk`
   - Windows: `diskpart` → `offline disk`
2. **Raw copy** the image file to the device path in 4 MiB chunks
   (`/dev/sdX`, `/dev/diskN`, or `\\.\PhysicalDriveN`)
3. **Optional verify** pass: re-read the device and compare against the
   source image
4. **Finalize**:
   - Linux: `sync` + `udisksctl power-off`
   - macOS: `diskutil eject`
   - Windows: `diskpart` → `online disk`

## Known limitations

- This implements **raw/DD-mode writing only**. It works great for modern
  hybrid Linux/BSD ISOs (Ubuntu, Fedora, Debian, Raspberry Pi OS, etc.) and
  raw `.img` files, exactly like `dd` or Etcher.
- It does **not** replicate Rufus's special-case logic for official Windows
  installation ISOs (FAT32+NTFS dual-partition layout needed for legacy
  BIOS boot when `install.wim`/`install.esd` exceeds the 4 GB FAT32 file
  size limit). A Windows ISO written in raw mode here will still boot fine
  on UEFI-only systems.
- Windows raw writes to `\\.\PhysicalDriveN` can occasionally hit a sharing
  violation if Explorer or another process has the disk open; the
  `offline disk` step via `diskpart` mitigates this but isn't bulletproof.
  If a write fails with a permission/sharing error, eject the drive in
  Explorer first, then retry.
- No GPT/MBR partition scheme picker, no persistent-storage partition for
  live Linux USBs, no checksum-based image verification before writing —
  all things Rufus offers as extra options. These could be added later as
  enhancements on top of this base.

## Tested

The GUI, device-detection logic, and import paths were syntax-checked and
smoke-tested in a headless Linux container (no display, no USB hardware
attached). The Windows- and macOS-specific code paths (PowerShell/`Get-Disk`,
`diskutil`, `diskpart`) are written following each platform's documented
behavior but have **not** been run on real Windows or macOS hardware —
test carefully with a spare/non-critical USB drive before relying on this
for anything important.
