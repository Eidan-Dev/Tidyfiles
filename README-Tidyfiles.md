# tidyfiles

A Python script that automatically tidies your Downloads folder: it sorts files by type and archives those older than 30 days.

A single file, no external dependencies. Compatible with Python 3.9+ on Windows, macOS and Linux.

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Options](#options)
- [Detailed behavior](#detailed-behavior)
- [Customization](#customization)
- [Automation](#automation)
- [Troubleshooting](#troubleshooting)

## Features

- **Sorting by type**: images, PDFs, archives, videos, audio, documents, installers, and an "Other" category.
- **Automatic archiving**: files older than N days are grouped by month into a ZIP file.
- **Dry-run mode**: see what would be done before anything is modified.
- **Safety**: no overwritten files, partial downloads ignored, symbolic links ignored.

## Installation

1. Check that Python 3.9 or newer is installed:

   ```bash
   python --version
   # or on macOS/Linux:
   python3 --version
   ```

   If Python is not installed, download it from [python.org](https://www.python.org/downloads/).

2. Place the `tidyfiles.py` file wherever you like, for example in your home folder.

No other installation is required.

## Usage

### Step 1: simulate first

Always start with a dry run. No files are modified:

```bash
python tidyfiles.py --dry-run
```

The script prints what it would do, for example:

```
Dry-run mode: no files will be modified.
Folder: /home/alice/Downloads
TRI   invoice.pdf -> PDF/invoice.pdf
TRI   photo.jpg -> Images/photo.jpg
ARCH  3 file(s) -> _Archives/2026-01.zip
Done: 2 sorted, 3 archived, 0 error(s).
```

### Step 2: run for real

```bash
python tidyfiles.py
```

This command sorts recent files and archives those older than 30 days.

### Examples

```bash
# Custom folder
python tidyfiles.py --source ~/Documents/Receipts

# Archive after 60 days instead of 30
python tidyfiles.py --days 60

# Sort only, without archiving anything
python tidyfiles.py --days 0

# Detailed output for debugging
python tidyfiles.py --verbose --dry-run
```

On Windows, replace `python3` with `py` if needed, and use paths like `C:\Users\Alice\Downloads`.

## Options

| Option | Short | Default | Description |
|---|---|---|---|
| `--source PATH` | `-s` | Downloads / Téléchargements | Folder to tidy |
| `--days N` | `-d` | `30` | Archive files older than N days. `0` disables archiving. |
| `--dry-run` | `-n` | off | Simulate without modifying anything |
| `--verbose` | `-v` | off | Show details (debug level) |
| `--version` | | | Show the version |
| `--help` | `-h` | | Show help |

The default folder is detected automatically: `Téléchargements` if it exists, otherwise `Downloads`.

## Detailed behavior

### Sorting

Recent files placed at the root of the folder are moved into a subfolder based on their extension:

| Category | Main extensions |
|---|---|
| `Images/` | jpg, jpeg, png, gif, webp, svg, heic, tiff, avif… |
| `PDF/` | pdf |
| `Archives/` | zip, rar, 7z, tar, gz, bz2, xz… |
| `Vidéos/` | mp4, mkv, avi, mov, webm… |
| `Audio/` | mp3, wav, flac, aac, ogg, m4a… |
| `Documents/` | doc, docx, odt, txt, md, xls, xlsx, csv, ppt, pptx… |
| `Installeurs/` | exe, msi, dmg, pkg, deb, rpm, appimage |
| `Autres/` | any other extension |

If a file with the same name already exists in the destination, the new one gets a suffix: `invoice (1).pdf`.

Note: category folder names are in French (`Vidéos/`, `Installeurs/`, `Autres/`) to match the script.

### Archiving

Files whose modification date is older than the threshold are grouped by modification month into `_Archives/YYYY-MM.zip`. Inside the ZIP, each file keeps its category:

```
_Archives/2026-01.zip
├── PDF/invoice.pdf
└── Images/photo.jpg
```

Original files are only deleted after they have been successfully written to the ZIP.

### What is ignored

- Hidden files (names starting with `.`)
- Downloads in progress: `.crdownload`, `.part`, `.tmp`, `.download`
- System files: `desktop.ini`, `Thumbs.db`, `.DS_Store`
- Symbolic links
- Subfolders that are not part of the managed categories

## Customization

To add an extension or a category, edit the `CATEGORIES` dictionary at the top of the file:

```python
CATEGORIES: dict[str, frozenset[str]] = {
    # ...
    "Code": frozenset({".py", ".js", ".ts", ".json"}),
}
```

To change the archive folder name, edit the `ARCHIVE_DIR` constant.

## Automation

### Windows: Task Scheduler

1. Open **Task Scheduler** and click **Create Basic Task**.
2. Give it a name (for example "tidyfiles") and choose a **Daily** trigger.
3. For **Action**, choose **Start a program**:
   - Program: `py` (or the full path to `python.exe`)
   - Arguments: `C:\path\to\tidyfiles.py`

### macOS and Linux: crontab

Open the crontab with `crontab -e` and add the following line to run every day at 9 a.m.:

```
0 9 * * * /usr/bin/python3 /path/to/tidyfiles.py
```

To find the path to Python, use `which python3`.

### macOS: launchd (alternative to cron)

On macOS, `launchd` is the recommended method. Create a file at `~/Library/LaunchAgents/com.tidyfiles.plist` containing the program to run and a `StartCalendarInterval`, then load it with `launchctl load`.

## Troubleshooting

**"Folder not found"**
Check the path passed to `--source`. Quotes are required if the path contains spaces: `--source "C:\Users\Alice\My Downloads"`.

**"Python is not recognized" (Windows)**
Reinstall Python and check **Add python.exe to PATH**, or use the `py` command instead of `python`.

**A file was not moved**
Run with `--verbose` to see details. Common causes are a file open in another application (Windows then prevents moving it) or insufficient permissions.

**The script returns an error code**
A non-zero code means at least one operation failed. Run again with `--verbose` to identify the file concerned.

**I want to undo changes**
Sorted files remain in their subfolders: just move them back to the root. Archived files are in the ZIPs inside `_Archives/`, which can be opened normally.

**Tip**: keep a backup of important files before the first real run.
