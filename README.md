# DRM File Protection System

A Windows desktop DRM (Digital Rights Management) suite built with **Python** and **PyQt5**. It packages documents into encrypted, self-expiring `.mylock` bundles and plays them back in a locked-down viewer.

The system has two independent applications:

| App | Purpose | Source |
| --- | --- | --- |
| **DRM Encryptor** | Select files, set access rules, and produce an encrypted `.mylock` package | `encryptor/` |
| **DRM Viewer** | Open a `.mylock` package, verify access rules, and view the content under restrictions | `viewer/` |

---

## How it works

### Encrypting (DRM Encryptor)

1. Select one or more files to include in a package.
2. Enter a package/folder name and an encryption password.
3. Optionally restrict the package to specific **MAC IDs** (semicolon-separated).
4. Set a **start** and **end** date/time (access window) and an optional watermark text.
5. The app zips the files, encrypts the archive, and writes a `.mylock` file next to the app in the `files/` folder.

### The `.mylock` format

A `.mylock` file is a JSON document:

```json
{
  "magic": "MYDRM01",
  "salt": "<urlsafe-base64>",
  "iv": "<urlsafe-base64>",
  "metadata": {
    "start": "2025-01-01T00:00:00",
    "end": "2025-01-08T00:00:00",
    "watermark_text": "DRM PROTECTED",
    "folder_name": "my-package",
    "original_names": ["a.pdf", "b.pdf"],
    "allowed_macs": ["AA:BB:CC:DD:EE:FF"]
  },
  "data": "<urlsafe-base64 encrypted zip>"
}
```

**Crypto pipeline**

- Key derivation: `PBKDF2-HMAC-SHA256`, 32-byte key, 100,000 iterations, random 16-byte salt.
- Encryption: `AES-256-CFB` with a random 16-byte IV.
- Payload: files are zipped (`ZIP_DEFLATED`) then encrypted; the result is stored base64-encoded alongside plaintext metadata.

### Viewing (DRM Viewer)

1. Pick a `.mylock` file.
2. The viewer checks the **MAC allowlist** (if present) and the **access window** (start/end).
3. It prompts for the password, decrypts the archive, and lists the contained files.
4. Double-click a file to view it. PDFs and videos are rendered page-by-page / frame-by-frame to watermarked JPEGs; images get a watermark overlay; `.txt`/`.md` render as text.

**Content protections (Windows)**

- `SetWindowDisplayAffinity` to block screen capture of the window.
- Hotkey suppression (e.g. Print Screen, Win+G).
- Periodic clipboard clearing.
- A background timer re-checks the access window every 5 seconds and locks the viewer the moment a package expires.

---

## Project structure

```
drm/
├── encryptor/                # DRM Encryptor app
│   ├── main.py               # Entry point (PyQt5 bootstrap)
│   ├── ui.py                 # Encryptor window / package building UI
│   ├── encryptor.py          # Zip + AES-CFB encryption, .mylock writer
│   ├── assets/               # logo.png, logo.ico, icons
│   └── files/                # Generated *.mylock packages
├── viewer/                   # DRM Viewer app
│   ├── main.py               # Entry point (PyQt5 bootstrap)
│   ├── ui.py                 # Viewer window, access rules, protections
│   ├── decryptor.py          # .mylock parsing + decryption + type dispatch
│   ├── converter.py          # Watermarking, PDF->images, video->frames
│   └── assets/               # logo.png, logo.ico
├── DRM Encryptor App.spec    # PyInstaller spec (encryptor)
├── DRM Viewer App.spec       # PyInstaller spec (viewer)
├── build/ , dist/            # PyInstaller output (git-ignored)
└── venv/                     # Local virtualenv (git-ignored)
```

---

## Requirements

- **Windows** (the viewer's protections use Win32 APIs: `win32gui`, `win32con`, `ctypes.windll`).
- **Python 3.11**

Python dependencies:

| Package | Used for |
| --- | --- |
| `PyQt5` | GUI for both apps |
| `cryptography` | PBKDF2 key derivation, AES-CFB encryption |
| `Pillow` | Image loading, watermarking, JPEG output |
| `PyMuPDF` (`fitz`) | Rendering PDF pages to images |
| `opencv-python` (`cv2`) | Extracting video frames |
| `filetype` | Detecting decrypted file types |
| `psutil` | Enumerating network interfaces / MAC addresses |
| `pywin32` | Clipboard, hotkeys, window display affinity |
| `pyinstaller` | Building the standalone `.exe`s |

Install them into a virtual environment:

```bat
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running from source

Run each app from **inside its own folder** so that its `assets/` and working directories resolve correctly.

Encryptor:

```bat
cd encryptor
python main.py
```

Viewer:

```bat
cd viewer
python main.py
```

Encrypted packages are written to and read from a `files/` folder beside the app. When running from source that is `encryptor/files/`; when running as a frozen `.exe` it is a `files/` folder next to the executable.

---

## Building standalone executables

The `.spec` files are pre-configured (windowed, custom icon, assets bundled). From the project root:

```bat
venv\Scripts\pyinstaller "DRM Encryptor App.spec"
venv\Scripts\pyinstaller "DRM Viewer App.spec"
```

Outputs land in `dist/`:

- `dist/DRM Encryptor App.exe`
- `dist/DRM Viewer App.exe`

---

## Security notes

This is a lightweight, self-contained protection scheme — not a hardened DRM platform. Keep in mind:

- The password protects content confidentiality, but **all metadata (access window, watermark text, MAC allowlist, original filenames) is stored in plaintext** inside the `.mylock` file.
- AES is used in **CFB mode**, which provides confidentiality but not authentication; a tampered file cannot be reliably detected.
- Viewer restrictions (anti-screenshot, hotkey blocking, clipboard clearing) rely on Windows APIs and are bypassable with sufficient effort.
- Password strength is critical: PBKDF2 with 100k iterations slows brute force but does not eliminate it.
