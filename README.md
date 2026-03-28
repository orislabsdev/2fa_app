# 🔐 2FA Authenticator

A desktop Two-Factor Authentication app with encrypted vault storage, a modern dark GUI, and support for both **TOTP** (time-based) and **HOTP** (counter-based) codes.

---

## Features

| Feature | Details |
|---|---|
| **TOTP** | RFC 6238 — 30-second rotating codes with animated countdown ring |
| **HOTP** | RFC 4226 — counter-based codes with one-click counter advance |
| **QR Import** | From an image file **or** live webcam scan |
| **Manual Entry** | Full form with advanced options (digits, algorithm, period) |
| **Encrypted Vault** | AES-128-CBC via Fernet; key derived from master password using PBKDF2-HMAC-SHA256 (480 000 iterations) |
| **Search** | Real-time filtering across account names and issuers |
| **Copy to Clipboard** | One-click copy with visual confirmation flash |
| **Delete** | Confirmation-gated removal |

---

## Installation

### 1. Prerequisites

- **Python 3.10+**
- pip

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Linux only** — QR scanning via `pyzbar` also needs the native `zbar` library:
> ```bash
> sudo apt install libzbar0   # Debian / Ubuntu
> sudo dnf install zbar       # Fedora
> ```

### 3. Run

```bash
python main.py
```

---

## First Run

On first launch you will be prompted to **create a master password**.  
This password encrypts your entire vault — it **cannot be recovered** if lost.

Subsequent launches show the **Unlock** screen.

---

## Adding Accounts

### From a QR Code image

1. Click **+ Add Account** in the sidebar.
2. Click **📁 From File** and select a PNG / JPG containing the authenticator QR code.

### Via Webcam

1. Click **+ Add Account → 📷 Webcam**.
2. Hold the QR code in front of your camera.  The code is captured automatically.
3. Press **Q** or **Escape** to cancel.

### Manually

Fill in:
- **Account Name** (required)
- **Issuer** (e.g. "GitHub", "Google") — optional but recommended
- **Secret Key** — the Base32 string from your service's 2FA setup page
- **Type** — TOTP or HOTP
- **Advanced** — digits (6/8), hash algorithm (SHA1/256/512), period or initial counter

---

## Security Notes

| Item | Detail |
|---|---|
| Key derivation | PBKDF2-HMAC-SHA256, 480 000 iterations, 16-byte random salt |
| Encryption | Fernet (AES-128-CBC + HMAC-SHA256) |
| Storage | `~/.2fa_authenticator/vault.enc` (opaque ciphertext) |
| Salt file | `~/.2fa_authenticator/salt.bin` (not secret, needed for unlock) |
| In-memory secrets | Secrets exist in plaintext in RAM only while the app is running |

The vault uses **atomic writes** (write temp → rename) to prevent partial-write corruption.

---

## File Structure

```
2fa_app/
├── main.py          # Entry point — password dialog → MainApp
├── storage.py       # Encrypted vault (StorageManager)
├── otp_engine.py    # TOTP / HOTP generation + QR decoding
├── gui.py           # All CustomTkinter UI components
└── requirements.txt # Python dependencies
```

---

## Supported `otpauth://` URI Parameters

| Parameter | Supported values |
|---|---|
| `type` | `totp`, `hotp` |
| `secret` | Any valid Base32 string |
| `issuer` | Any string |
| `digits` | `6`, `8` |
| `algorithm` | `SHA1`, `SHA256`, `SHA512` |
| `period` | Any positive integer (TOTP only) |
| `counter` | Any non-negative integer (HOTP only) |

---

## License

MIT — use freely, no warranty.
