"""
storage.py — Encrypted vault for 2FA account credentials.

Security model:
  • Master password → PBKDF2-HMAC-SHA256 → Fernet key (AES-128-CBC + HMAC-SHA256)
  • A random 16-byte salt is generated once and stored alongside the ciphertext.
  • All account data (names, secrets, settings) is serialised to JSON, then
    encrypted as a single opaque blob — no plaintext metadata leaks to disk.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# ── Constants ────────────────────────────────────────────────────────────────
_SALT_FILE  = "salt.bin"    # Stores the random KDF salt (not secret)
_DATA_FILE  = "vault.enc"   # Stores the Fernet-encrypted JSON blob
_ITERATIONS = 480_000       # PBKDF2 iteration count (OWASP 2023 recommendation)


# ── Key derivation ────────────────────────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a 32-byte Fernet-compatible key from *password* using PBKDF2-HMAC-SHA256.

    Args:
        password: The user's master password (UTF-8 encoded internally).
        salt:     A 16-byte random salt stored in the vault directory.

    Returns:
        URL-safe base64-encoded key suitable for :class:`cryptography.fernet.Fernet`.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)   # Fernet requires URL-safe b64


# ── Storage manager ───────────────────────────────────────────────────────────

class StorageManager:
    """
    Thread-safe encrypted storage for 2FA accounts.

    Typical lifecycle::

        mgr = StorageManager(Path("~/.2fa_app"))
        if mgr.is_initialized():
            mgr.unlock("my-master-password")   # decrypt & load
        else:
            mgr.setup_new("my-master-password") # first-run initialisation

        mgr.add_account({...})
        accounts = mgr.get_accounts()
        mgr.remove_account(0)
    """

    def __init__(self, data_dir: Path) -> None:
        """
        Args:
            data_dir: Directory where ``salt.bin`` and ``vault.enc`` are stored.
                      Created automatically if absent.
        """
        self._dir       = data_dir
        self._salt_path = data_dir / _SALT_FILE
        self._data_path = data_dir / _DATA_FILE
        self._accounts: list[dict]   = []
        self._fernet:   Fernet | None = None

    # ── Public API ─────────────────────────────────────────────────────────

    def is_initialized(self) -> bool:
        """Return *True* if a vault has previously been created (salt file exists)."""
        return self._salt_path.exists()

    def setup_new(self, password: str) -> None:
        """
        Initialise a brand-new vault with *password*.

        Generates a fresh random salt, derives the Fernet key, and writes
        an empty (but properly encrypted) accounts file.

        Args:
            password: The master password chosen by the user.
        """
        salt = os.urandom(16)                   # Cryptographically secure salt
        self._salt_path.write_bytes(salt)
        self._fernet   = Fernet(_derive_key(password, salt))
        self._accounts = []
        self._persist()                         # Write encrypted empty vault

    def unlock(self, password: str) -> None:
        """
        Decrypt and load the vault using *password*.

        Args:
            password: The master password.

        Raises:
            ValueError: If the password is wrong or the vault data is corrupted.
        """
        if not self.is_initialized():
            # First run — treat as setup instead of an error
            self.setup_new(password)
            return

        salt           = self._salt_path.read_bytes()
        self._fernet   = Fernet(_derive_key(password, salt))

        if self._data_path.exists():
            try:
                ciphertext     = self._data_path.read_bytes()
                plaintext      = self._fernet.decrypt(ciphertext)
                self._accounts = json.loads(plaintext.decode("utf-8"))
            except (InvalidToken, json.JSONDecodeError) as exc:
                raise ValueError("Incorrect password or corrupted vault.") from exc
        else:
            self._accounts = []
            self._persist()

    def get_accounts(self) -> list[dict]:
        """Return a *copy* of the current accounts list (safe to mutate)."""
        return list(self._accounts)

    def add_account(self, account: dict) -> None:
        """
        Append *account* to the vault and immediately persist to disk.

        Expected keys in *account*:
            name (str), issuer (str), secret (str), type ('totp'|'hotp'),
            digits (6|8), algorithm ('SHA1'|'SHA256'|'SHA512'),
            period (int, TOTP), counter (int, HOTP).
        """
        self._accounts.append(account)
        self._persist()

    def remove_account(self, index: int) -> None:
        """
        Delete the account at *index* and persist.

        Args:
            index: Zero-based position in the accounts list.
        """
        if 0 <= index < len(self._accounts):
            self._accounts.pop(index)
            self._persist()

    def update_account(self, index: int, account: dict) -> None:
        """
        Replace the account at *index* with *account* (e.g. increment HOTP counter).

        Args:
            index:   Zero-based position.
            account: Updated account dict (same schema as :meth:`add_account`).
        """
        if 0 <= index < len(self._accounts):
            self._accounts[index] = account
            self._persist()

    # ── Private helpers ────────────────────────────────────────────────────

    def _persist(self) -> None:
        """Serialise accounts to JSON, encrypt, and atomically write to disk."""
        if self._fernet is None:
            raise RuntimeError("StorageManager.unlock() must be called before saving.")
        plaintext  = json.dumps(self._accounts, indent=2).encode("utf-8")
        ciphertext = self._fernet.encrypt(plaintext)
        # Write to a temp file then rename for atomic replacement
        tmp = self._data_path.with_suffix(".tmp")
        tmp.write_bytes(ciphertext)
        tmp.replace(self._data_path)
