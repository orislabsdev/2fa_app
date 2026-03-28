"""
otp_engine.py — TOTP (RFC 6238) and HOTP (RFC 4226) code generation,
plus QR-code decoding and otpauth:// URI parsing.

Public API
----------
generate_totp(secret, digits, period, algorithm)  -> (code, remaining_secs)
generate_hotp(secret, counter, digits, algorithm) -> code
parse_otpauth_uri(uri)                            -> account dict | None
decode_qr_from_image(path)                        -> uri string | None
scan_qr_from_webcam()                             -> uri string | None
"""

from __future__ import annotations

import hashlib
import time
from urllib.parse import urlparse, parse_qs, unquote

import pyotp


# ── Digest helper ─────────────────────────────────────────────────────────────

def _digest(algorithm: str):
    """
    Map an algorithm name string to the corresponding :mod:`hashlib` constructor.

    Supported values: ``'SHA1'`` (default), ``'SHA256'``, ``'SHA512'``.
    Unknown strings fall back to SHA1 for maximum compatibility with
    authenticator apps in the wild.
    """
    return {
        "SHA1":   hashlib.sha1,
        "SHA256": hashlib.sha256,
        "SHA512": hashlib.sha512,
    }.get(algorithm.upper(), hashlib.sha1)


# ── TOTP ──────────────────────────────────────────────────────────────────────

def generate_totp(
    secret:    str,
    digits:    int = 6,
    period:    int = 30,
    algorithm: str = "SHA1",
) -> tuple[str, int]:
    """
    Generate the current TOTP code and the number of seconds left in this window.

    The code is zero-padded to *digits* characters (e.g. ``'007890'`` for 6 digits).

    Args:
        secret:    Base32-encoded shared secret.
        digits:    OTP length — 6 or 8.
        period:    Time-step size in seconds (commonly 30).
        algorithm: Hash algorithm — ``'SHA1'``, ``'SHA256'``, or ``'SHA512'``.

    Returns:
        ``(code, remaining_seconds)`` where *remaining_seconds* is
        how long the code stays valid (1 … period).
    """
    totp      = pyotp.TOTP(secret, digits=digits, interval=period, digest=_digest(algorithm))
    code      = totp.now()
    remaining = period - (int(time.time()) % period)   # Seconds left in this window
    return code, remaining


# ── HOTP ──────────────────────────────────────────────────────────────────────

def generate_hotp(
    secret:    str,
    counter:   int,
    digits:    int = 6,
    algorithm: str = "SHA1",
) -> str:
    """
    Generate an HOTP code for the given *counter* value.

    The caller is responsible for incrementing the counter after each
    successful authentication and persisting the new value.

    Args:
        secret:    Base32-encoded shared secret.
        counter:   Current counter value (non-negative integer).
        digits:    OTP length — 6 or 8.
        algorithm: Hash algorithm.

    Returns:
        Zero-padded OTP code string.
    """
    hotp = pyotp.HOTP(secret, digits=digits, digest=_digest(algorithm))
    return hotp.at(counter)


# ── otpauth URI parser ────────────────────────────────────────────────────────

def parse_otpauth_uri(uri: str) -> dict | None:
    """
    Parse an ``otpauth://`` URI (typically encoded in a QR code) into an
    account dict compatible with :class:`storage.StorageManager`.

    URI format (RFC / Google Authenticator Key URI spec)::

        otpauth://TYPE/LABEL?secret=SECRET&issuer=ISSUER[&digits=N][&period=N][&counter=N][&algorithm=ALG]

    Args:
        uri: Raw string decoded from a QR code.

    Returns:
        Account dict with keys ``name``, ``issuer``, ``secret``, ``type``,
        ``digits``, ``algorithm``, ``period``, ``counter`` — or ``None`` if
        the URI is malformed or unsupported.
    """
    uri = uri.strip()
    if not uri.startswith("otpauth://"):
        return None

    try:
        parsed   = urlparse(uri)
        otp_type = parsed.netloc.lower()   # 'totp' or 'hotp'
        if otp_type not in ("totp", "hotp"):
            return None

        # Label may be "Issuer:AccountName" or just "AccountName"
        label = unquote(parsed.path.lstrip("/"))
        if ":" in label:
            issuer_label, name = label.split(":", 1)
        else:
            issuer_label, name = "", label

        params = parse_qs(parsed.query)

        def _p(key: str, default: str) -> str:
            """Extract first value from a parse_qs dict, falling back to *default*."""
            return params.get(key, [default])[0]

        secret    = _p("secret",    "").upper().replace(" ", "")
        issuer    = _p("issuer",    issuer_label).strip() or issuer_label.strip()
        digits    = int(_p("digits",    "6"))
        algorithm = _p("algorithm", "SHA1").upper()
        period    = int(_p("period",    "30"))
        counter   = int(_p("counter",   "0"))

        if not secret:
            return None   # Secret is mandatory

        return {
            "name":      name.strip() or "Unknown",
            "issuer":    issuer,
            "secret":    secret,
            "type":      otp_type,
            "digits":    digits    if digits    in (6, 8)                        else 6,
            "algorithm": algorithm if algorithm in ("SHA1", "SHA256", "SHA512")  else "SHA1",
            "period":    period    if period    > 0                              else 30,
            "counter":   counter   if counter   >= 0                             else 0,
        }
    except Exception:
        return None


# ── QR decoding ───────────────────────────────────────────────────────────────

def decode_qr_from_image(image_path: str) -> str | None:
    """
    Decode a QR code from an image file on disk.

    Attempts two strategies in order:

    1. **OpenCV** built-in :class:`cv2.QRCodeDetector` — no extra system
       libraries required, works on Windows / macOS / Linux out of the box.
    2. **pyzbar** — a higher-accuracy fallback that requires the native
       ``zbar`` shared library (``apt install libzbar0`` on Debian/Ubuntu).

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        Decoded string (the QR payload) or ``None`` if detection failed.
    """
    # ── Strategy 1: OpenCV ──────────────────────────────────────────────────
    try:
        import cv2
        import numpy as np

        img = cv2.imread(image_path)
        if img is None:
            # OpenCV may fail on certain formats (WebP, HEIC) — try Pillow
            from PIL import Image as _PilImage
            pil = _PilImage.open(image_path).convert("RGB")
            img = np.array(pil)[:, :, ::-1]   # RGB → BGR for OpenCV

        detector = cv2.QRCodeDetector()
        data, _pts, _straight = detector.detectAndDecode(img)
        if data:
            return data
    except ImportError:
        pass   # OpenCV not installed; fall through to pyzbar

    # ── Strategy 2: pyzbar ─────────────────────────────────────────────────
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        from PIL import Image as _PilImage

        img     = _PilImage.open(image_path)
        results = pyzbar_decode(img)
        if results:
            return results[0].data.decode("utf-8")
    except ImportError:
        pass   # pyzbar not installed either

    return None   # Both strategies failed


def scan_qr_from_webcam() -> str | None:
    """
    Open the default system webcam and scan for a QR code in real time.

    Displays a live OpenCV preview window.  The function returns as soon as
    a QR code is detected (with a short confirmation pause) or when the user
    presses **Q** / **Escape** to cancel.

    Returns:
        Decoded QR payload string, or ``None`` if cancelled / webcam unavailable.
    """
    try:
        import cv2
    except ImportError:
        return None   # OpenCV not available

    cap = cv2.VideoCapture(0)   # Default camera (index 0)
    if not cap.isOpened():
        return None

    detector = cv2.QRCodeDetector()
    result   = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            data, bbox, _ = detector.detectAndDecode(frame)

            if data and bbox is not None:
                # Draw a green polygon around the detected QR code
                pts = bbox.astype(int).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True, color=(0, 220, 80), thickness=3)
                cv2.putText(
                    frame, "QR Detected — press any key",
                    (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 220, 80), 2,
                )
                result = data

            cv2.imshow("Scan QR Code  (Q = cancel)", frame)
            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), ord("Q"), 27):   # Q or Escape → cancel
                result = None
                break
            if result:                             # Any other key OR auto-close
                time.sleep(0.4)                    # Brief pause so user sees the highlight
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    return result
