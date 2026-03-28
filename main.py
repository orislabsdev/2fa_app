"""
main.py — Entry point for the 2FA Authenticator.

Usage
-----
    python main.py

Flow
----
1.  Configure CustomTkinter (dark mode, blue theme).
2.  Show :class:`PasswordDialog` — either first-run setup or vault unlock.
3.  Attempt to unlock :class:`StorageManager` with the supplied password.
4.  On success, reveal the main window and hand control to :class:`MainApp`.
5.  On wrong password, display an error and exit cleanly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from storage import StorageManager
from gui import PasswordDialog, MainApp


def main() -> None:
    """Application entry point."""
    # ── CustomTkinter global settings ──────────────────────────────────────
    ctk.set_appearance_mode("dark")       # Force dark mode regardless of OS setting
    ctk.set_default_color_theme("blue")   # Base colour palette for CTk widgets

    # ── Data directory setup ───────────────────────────────────────────────
    # Stored in the user's home directory so it survives OS updates / reinstalls
    data_dir = Path.home() / ".2fa_authenticator"
    data_dir.mkdir(parents=True, exist_ok=True)

    storage = StorageManager(data_dir)

    # ── Root window (hidden until after authentication) ────────────────────
    root = ctk.CTk()
    root.withdraw()   # Keep hidden during the password dialog

    # ── Password dialog ────────────────────────────────────────────────────
    is_new_setup = not storage.is_initialized()
    pwd_dialog   = PasswordDialog(root, is_new_setup=is_new_setup)
    root.wait_window(pwd_dialog)   # Block until dialog closes

    if pwd_dialog.password is None:
        # User closed the dialog without entering a password → exit
        root.destroy()
        sys.exit(0)

    # ── Unlock vault ───────────────────────────────────────────────────────
    try:
        storage.unlock(pwd_dialog.password)
    except ValueError as exc:
        messagebox.showerror(
            "Authentication Failed",
            f"Could not unlock the vault:\n\n{exc}\n\n"
            "Please re-launch and try again.",
        )
        root.destroy()
        sys.exit(1)

    # ── Launch main application ────────────────────────────────────────────
    root.deiconify()          # Make the root window visible
    MainApp(root, storage)    # Construct and bind the main UI
    root.mainloop()           # Enter the Tk event loop


if __name__ == "__main__":
    main()
