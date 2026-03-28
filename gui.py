"""
gui.py — All UI components for the 2FA Authenticator.

Built with CustomTkinter for a modern, dark-glass aesthetic.

Components (top-level)
----------------------
PasswordDialog   : Full-screen vault unlock / first-run setup.
AddAccountDialog : Modal form to add a new TOTP/HOTP account.
AccountCard      : Per-account widget (code, progress ring, actions).
MainApp          : Root application window and update loop.
"""

from __future__ import annotations

import math
import time
import tkinter as tk
from tkinter import filedialog, messagebox, StringVar
from pathlib import Path
from typing import Callable

import customtkinter as ctk
import pyotp

from storage import StorageManager
from otp_engine import (
    decode_qr_from_image,
    generate_hotp,
    generate_totp,
    parse_otpauth_uri,
    scan_qr_from_webcam,
)

# ── Design tokens ─────────────────────────────────────────────────────────────
# Palette: deep-space dark with electric cyan/blue accents
BG_DEEP    = "#0D1117"   # Window background
BG_PANEL   = "#161B22"   # Sidebar / card background
BG_CARD    = "#1C2333"   # Individual account card
BG_HOVER   = "#21293D"   # Card hover tint
ACCENT     = "#58A6FF"   # Primary accent (electric blue)
ACCENT2    = "#3FB950"   # TOTP progress / success (green)
ORANGE     = "#F78166"   # HOTP / danger
BORDER     = "#30363D"   # Subtle border
TEXT_PRI   = "#E6EDF3"   # Primary text
TEXT_SEC   = "#8B949E"   # Secondary / dim text
TEXT_DIM   = "#484F58"   # Very dim text

# Typography (fall back gracefully if font unavailable)
F_DISPLAY  = ("SF Pro Display",  22, "bold")
F_TITLE    = ("SF Pro Display",  14, "bold")
F_CODE     = ("Courier New",     30, "bold")
F_BODY     = ("SF Pro Text",     12)
F_SMALL    = ("SF Pro Text",     10)
F_BTN      = ("SF Pro Text",     11, "bold")
F_MICRO    = ("SF Pro Text",      9)


# ── Utility ───────────────────────────────────────────────────────────────────

def _clipboard_copy(root: tk.Tk, text: str) -> None:
    """Copy *text* to the system clipboard using tkinter's cross-platform API."""
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()   # Required on some platforms to flush the clipboard


def _icon_label(parent, text: str, **kw) -> ctk.CTkLabel:
    """Convenience: create a label whose text is a Unicode icon / emoji."""
    return ctk.CTkLabel(parent, text=text, **kw)


# ── Password dialog ───────────────────────────────────────────────────────────

class PasswordDialog(ctk.CTkToplevel):
    """
    Full-screen modal shown on launch.

    On first run (*is_new_setup=True*) the user chooses a master password
    and confirms it.  On subsequent runs they simply unlock the vault.

    After the dialog closes, check :attr:`password` — ``None`` means the
    user cancelled and the application should exit.
    """

    def __init__(self, parent: ctk.CTk, is_new_setup: bool = False) -> None:
        super().__init__(parent)
        self.password: str | None = None
        self._is_new  = is_new_setup

        self.title("2FA Authenticator")
        self.geometry("460x560")
        self.resizable(False, False)
        self.configure(fg_color=BG_DEEP)
        self.grab_set()                              # Modal behaviour
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._build()
        self.after(80, self._center_on_screen)

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Construct all widgets in the password dialog."""
        # ── Hero area ──────────────────────────────────────────────────────
        hero = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=180)
        hero.pack(fill="x")
        hero.pack_propagate(False)

        # Large lock icon rendered on a canvas for a glowing effect
        hero_canvas = tk.Canvas(
            hero, width=80, height=80,
            bg=BG_PANEL, highlightthickness=0,
        )
        hero_canvas.pack(pady=(28, 6))
        # Outer glow ring
        hero_canvas.create_oval(4, 4, 76, 76, outline=ACCENT, width=1, fill="")
        # Icon
        hero_canvas.create_text(40, 40, text="🔐", font=("", 32))

        ctk.CTkLabel(
            hero, text="2FA Authenticator",
            font=F_DISPLAY, text_color=TEXT_PRI,
        ).pack()
        ctk.CTkLabel(
            hero,
            text="Vault Setup" if self._is_new else "Unlock Vault",
            font=F_SMALL, text_color=ACCENT,
        ).pack(pady=(2, 0))

        # ── Form area ──────────────────────────────────────────────────────
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=36, pady=20)

        if self._is_new:
            ctk.CTkLabel(
                form,
                text="Choose a master password to protect your vault.\n"
                     "This cannot be recovered if lost.",
                font=F_SMALL, text_color=TEXT_SEC, justify="center",
            ).pack(pady=(0, 16))
        else:
            ctk.CTkLabel(
                form, text="Enter your master password to continue.",
                font=F_SMALL, text_color=TEXT_SEC,
            ).pack(pady=(0, 16))

        # Password field
        self._pwd_var = StringVar()
        self._pwd_entry = self._field(form, "Master Password", self._pwd_var, show="•")

        # Confirm field (new setup only)
        self._confirm_var   = StringVar()
        self._confirm_entry = None
        if self._is_new:
            self._confirm_entry = self._field(form, "Confirm Password", self._confirm_var, show="•")

        # Error message (hidden until needed)
        self._err_var = StringVar()
        ctk.CTkLabel(
            form, textvariable=self._err_var,
            text_color=ORANGE, font=F_SMALL,
        ).pack(pady=4)

        # Submit button
        btn_label = "Create Vault" if self._is_new else "Unlock"
        ctk.CTkButton(
            form, text=btn_label, height=46,
            font=F_BTN, fg_color=ACCENT, hover_color="#3880CC",
            text_color="#0D1117", corner_radius=10,
            command=self._submit,
        ).pack(fill="x")

        self.bind("<Return>", lambda _e: self._submit())
        self._pwd_entry.focus()

    def _field(
        self,
        parent:    ctk.CTkFrame,
        label_txt: str,
        var:       StringVar,
        show:      str = "",
    ) -> ctk.CTkEntry:
        """Helper: labelled entry field."""
        ctk.CTkLabel(
            parent, text=label_txt,
            font=F_MICRO, text_color=TEXT_SEC, anchor="w",
        ).pack(fill="x", pady=(4, 1))
        entry = ctk.CTkEntry(
            parent, textvariable=var, show=show,
            height=42, font=F_BODY,
            fg_color=BG_CARD, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI,
        )
        entry.pack(fill="x", pady=(0, 8))
        return entry

    # ── Actions ───────────────────────────────────────────────────────────

    def _submit(self) -> None:
        """Validate the entered password(s) and close the dialog."""
        pwd = self._pwd_var.get()
        if len(pwd) < 4:
            self._err_var.set("Password must be at least 4 characters.")
            return
        if self._is_new and self._confirm_entry:
            if pwd != self._confirm_var.get():
                self._err_var.set("Passwords do not match.")
                return
        self.password = pwd
        self.destroy()

    def _cancel(self) -> None:
        """User dismissed the dialog — signal that the app should exit."""
        self.password = None
        self.destroy()

    def _center_on_screen(self) -> None:
        """Move the dialog to the centre of the primary monitor."""
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w,  h  = self.winfo_width(),       self.winfo_height()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ── Add-account dialog ────────────────────────────────────────────────────────

class AddAccountDialog(ctk.CTkToplevel):
    """
    Modal dialog for adding a new 2FA account.

    Supports three entry methods:
      1. Import from an image file containing a QR code.
      2. Live webcam QR scan (requires OpenCV).
      3. Manual entry of all fields.

    After the dialog closes, check :attr:`result` — a complete account dict
    (same schema as :meth:`StorageManager.add_account`) or ``None`` if cancelled.
    """

    def __init__(self, parent: ctk.CTk) -> None:
        super().__init__(parent)
        self.result: dict | None = None

        self.title("Add Account")
        self.geometry("520x680")
        self.resizable(False, False)
        self.configure(fg_color=BG_DEEP)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build()
        self.after(80, self._center_on_screen)

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Build the Add Account form."""
        # Header strip
        header = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="➕  Add 2FA Account",
            font=F_TITLE, text_color=TEXT_PRI,
        ).pack(side="left", padx=20, pady=14)

        # Scrollable body
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=12)

        # ── QR import section ──────────────────────────────────────────────
        qr_card = ctk.CTkFrame(body, fg_color=BG_PANEL, corner_radius=12)
        qr_card.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            qr_card, text="Import from QR Code",
            font=F_TITLE, text_color=TEXT_PRI,
        ).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            qr_card, text="Scan a QR code image or use your webcam",
            font=F_SMALL, text_color=TEXT_SEC,
        ).pack(anchor="w", padx=16)

        btn_row = ctk.CTkFrame(qr_card, fg_color="transparent")
        btn_row.pack(padx=14, pady=12, anchor="w")

        ctk.CTkButton(
            btn_row, text="📁  From File",
            width=145, height=36, font=F_BTN,
            fg_color=ACCENT, hover_color="#3880CC",
            text_color="#0D1117", corner_radius=8,
            command=self._import_file,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="📷  Webcam",
            width=130, height=36, font=F_BTN,
            fg_color=BG_CARD, hover_color=BG_HOVER,
            border_color=BORDER, border_width=1,
            text_color=TEXT_PRI, corner_radius=8,
            command=self._import_webcam,
        ).pack(side="left")

        # ── Divider ────────────────────────────────────────────────────────
        div = ctk.CTkFrame(body, fg_color="transparent")
        div.pack(fill="x", pady=6)
        ctk.CTkFrame(div, height=1, fg_color=BORDER).pack(
            fill="x", side="left", expand=True, pady=8,
        )
        ctk.CTkLabel(div, text=" or enter manually ", font=F_MICRO,
                     text_color=TEXT_DIM).pack(side="left")
        ctk.CTkFrame(div, height=1, fg_color=BORDER).pack(
            fill="x", side="left", expand=True, pady=8,
        )

        # ── OTP type selector ──────────────────────────────────────────────
        self._type_var = StringVar(value="totp")
        type_row = ctk.CTkFrame(body, fg_color="transparent")
        type_row.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(type_row, text="Type", font=F_SMALL,
                     text_color=TEXT_SEC).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(
            type_row, text="TOTP  (time-based)",
            variable=self._type_var, value="totp",
            font=F_SMALL, text_color=TEXT_PRI,
            radiobutton_width=14, radiobutton_height=14,
            fg_color=ACCENT, command=self._on_type_change,
        ).pack(side="left", padx=6)
        ctk.CTkRadioButton(
            type_row, text="HOTP  (counter-based)",
            variable=self._type_var, value="hotp",
            font=F_SMALL, text_color=TEXT_PRI,
            radiobutton_width=14, radiobutton_height=14,
            fg_color=ORANGE, command=self._on_type_change,
        ).pack(side="left", padx=6)

        # ── Core fields ────────────────────────────────────────────────────
        self._name_entry   = self._field(body, "Account Name  *")
        self._issuer_entry = self._field(body, "Issuer / Service  (optional)")
        self._secret_entry = self._field(body, "Secret Key  (Base32)  *")

        # ── Advanced options ───────────────────────────────────────────────
        adv = ctk.CTkFrame(body, fg_color=BG_PANEL, corner_radius=10)
        adv.pack(fill="x", pady=(4, 8))

        ctk.CTkLabel(adv, text="⚙  Advanced", font=F_SMALL,
                     text_color=TEXT_DIM).pack(anchor="w", padx=14, pady=(10, 4))

        adv_inner = ctk.CTkFrame(adv, fg_color="transparent")
        adv_inner.pack(fill="x", padx=14, pady=(0, 12))
        adv_inner.columnconfigure((0, 1, 2), weight=1)

        # Digits
        ctk.CTkLabel(adv_inner, text="Digits", font=F_MICRO,
                     text_color=TEXT_SEC).grid(row=0, column=0, sticky="w")
        self._digits_var = StringVar(value="6")
        ctk.CTkOptionMenu(
            adv_inner, variable=self._digits_var, values=["6", "8"],
            width=90, height=32, font=F_SMALL,
            fg_color=BG_CARD, button_color=ACCENT, text_color=TEXT_PRI,
        ).grid(row=1, column=0, sticky="w", pady=2)

        # Algorithm
        ctk.CTkLabel(adv_inner, text="Algorithm", font=F_MICRO,
                     text_color=TEXT_SEC).grid(row=0, column=1, sticky="w")
        self._algo_var = StringVar(value="SHA1")
        ctk.CTkOptionMenu(
            adv_inner, variable=self._algo_var,
            values=["SHA1", "SHA256", "SHA512"],
            width=110, height=32, font=F_SMALL,
            fg_color=BG_CARD, button_color=ACCENT, text_color=TEXT_PRI,
        ).grid(row=1, column=1, sticky="w", pady=2)

        # Period (TOTP) or Counter (HOTP) — swapped by _on_type_change
        self._period_frame = ctk.CTkFrame(adv_inner, fg_color="transparent")
        self._period_frame.grid(row=0, column=2, rowspan=2, sticky="w")
        ctk.CTkLabel(self._period_frame, text="Period (s)", font=F_MICRO,
                     text_color=TEXT_SEC).pack(anchor="w")
        self._period_var = StringVar(value="30")
        ctk.CTkEntry(self._period_frame, textvariable=self._period_var,
                     width=80, height=32, font=F_SMALL,
                     fg_color=BG_CARD, border_color=BORDER,
                     text_color=TEXT_PRI).pack()

        self._counter_frame = ctk.CTkFrame(adv_inner, fg_color="transparent")
        self._counter_frame.grid(row=0, column=2, rowspan=2, sticky="w")
        ctk.CTkLabel(self._counter_frame, text="Init Counter", font=F_MICRO,
                     text_color=TEXT_SEC).pack(anchor="w")
        self._counter_var = StringVar(value="0")
        ctk.CTkEntry(self._counter_frame, textvariable=self._counter_var,
                     width=80, height=32, font=F_SMALL,
                     fg_color=BG_CARD, border_color=BORDER,
                     text_color=TEXT_PRI).pack()
        self._counter_frame.grid_remove()   # Hidden in TOTP mode

        # ── Status / error ─────────────────────────────────────────────────
        self._err_var = StringVar()
        ctk.CTkLabel(
            body, textvariable=self._err_var,
            text_color=ORANGE, font=F_SMALL,
        ).pack(pady=4)

        # ── Submit ─────────────────────────────────────────────────────────
        ctk.CTkButton(
            body, text="Add Account", height=46,
            font=F_BTN, fg_color=ACCENT, hover_color="#3880CC",
            text_color="#0D1117", corner_radius=10,
            command=self._submit,
        ).pack(fill="x")

    def _field(self, parent: ctk.CTkScrollableFrame, label: str) -> ctk.CTkEntry:
        """Labelled entry row inside the scrollable body."""
        ctk.CTkLabel(parent, text=label, font=F_MICRO,
                     text_color=TEXT_SEC, anchor="w").pack(fill="x", pady=(6, 1))
        entry = ctk.CTkEntry(
            parent, height=40, font=F_BODY,
            fg_color=BG_CARD, border_color=BORDER, border_width=1,
            text_color=TEXT_PRI,
        )
        entry.pack(fill="x", pady=(0, 4))
        return entry

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_type_change(self) -> None:
        """Swap the Period / Counter field based on the selected OTP type."""
        if self._type_var.get() == "totp":
            self._counter_frame.grid_remove()
            self._period_frame.grid()
        else:
            self._period_frame.grid_remove()
            self._counter_frame.grid()

    def _import_file(self) -> None:
        """Open a file picker, decode the selected image's QR code, fill fields."""
        path = filedialog.askopenfilename(
            title="Select QR Code Image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        uri = decode_qr_from_image(path)
        if not uri:
            self._err_var.set("⚠  No QR code found in that image.")
            return
        self._populate(uri)

    def _import_webcam(self) -> None:
        """Scan a QR code from the webcam and fill fields."""
        self._err_var.set("Opening webcam…  (press Q or Esc to cancel)")
        self.update()
        uri = scan_qr_from_webcam()
        if not uri:
            self._err_var.set("⚠  No QR code scanned (or webcam unavailable).")
            return
        self._populate(uri)

    def _populate(self, uri: str) -> None:
        """Parse *uri* and fill all form fields from the decoded values."""
        account = parse_otpauth_uri(uri)
        if not account:
            self._err_var.set("⚠  Invalid or unsupported QR code format.")
            return

        # Helper to clear-then-insert into an entry widget
        def _set(entry: ctk.CTkEntry, value: str) -> None:
            entry.delete(0, "end")
            entry.insert(0, value)

        _set(self._name_entry,   account["name"])
        _set(self._issuer_entry, account["issuer"])
        _set(self._secret_entry, account["secret"])
        self._type_var.set(account["type"])
        self._digits_var.set(str(account["digits"]))
        self._algo_var.set(account["algorithm"])
        self._period_var.set(str(account["period"]))
        self._counter_var.set(str(account["counter"]))
        self._on_type_change()
        self._err_var.set("✓  QR code imported successfully!")

    def _submit(self) -> None:
        """Validate form fields and close the dialog, storing result."""
        name   = self._name_entry.get().strip()
        secret = self._secret_entry.get().strip().upper().replace(" ", "")

        if not name:
            self._err_var.set("Account name is required.")
            return
        if not secret:
            self._err_var.set("Secret key is required.")
            return

        # Quick pyotp validation to catch clearly invalid Base32 secrets early
        try:
            pyotp.TOTP(secret).now()
        except Exception:
            self._err_var.set("⚠  Invalid secret key — must be Base32 encoded.")
            return

        try:
            period  = int(self._period_var.get())
            counter = int(self._counter_var.get())
            digits  = int(self._digits_var.get())
        except ValueError:
            self._err_var.set("Period / counter / digits must be integers.")
            return

        self.result = {
            "name":      name,
            "issuer":    self._issuer_entry.get().strip(),
            "secret":    secret,
            "type":      self._type_var.get(),
            "digits":    digits,
            "algorithm": self._algo_var.get(),
            "period":    period,
            "counter":   counter,
        }
        self.destroy()

    def _center_on_screen(self) -> None:
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w,  h  = self.winfo_width(),       self.winfo_height()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ── Account card ──────────────────────────────────────────────────────────────

class AccountCard(ctk.CTkFrame):
    """
    Widget that displays a single 2FA account with its current OTP code.

    For TOTP accounts a circular arc-style countdown timer is drawn on a
    :class:`tk.Canvas`.  For HOTP accounts a "Next Code ▶" button allows
    the user to advance the counter.

    :param parent:               Container widget.
    :param account:              Account dict (same schema as StorageManager).
    :param index:                Position in the StorageManager accounts list.
    :param on_delete:            Callback ``(index) → None`` to delete this card.
    :param on_copy:              Callback ``(code_str) → None`` to copy the code.
    :param on_counter_increment: Callback ``(index) → None`` to advance HOTP counter.
    """

    _ARC_SIZE   = 52    # Diameter of the progress arc canvas
    _ARC_WIDTH  = 4     # Stroke width of the progress arc
    _ARC_INSET  = 6     # Inset from canvas edge to arc bounding box

    def __init__(
        self,
        parent:               ctk.CTkFrame,
        account:              dict,
        index:                int,
        on_delete:            Callable[[int], None],
        on_copy:              Callable[[str], None],
        on_counter_increment: Callable[[int], None],
    ) -> None:
        super().__init__(parent, fg_color=BG_CARD, corner_radius=14)
        self.account  = dict(account)   # Local mutable copy
        self.index    = index
        self._on_del  = on_delete
        self._on_copy = on_copy
        self._on_inc  = on_counter_increment

        # Pre-compute accent colour based on OTP type
        self._type_color = ACCENT2 if account["type"] == "totp" else ORANGE

        self._build()
        self.update_display()   # Populate immediately

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Construct all sub-widgets inside the card frame."""
        # Left colour-bar (visual type indicator)
        bar = ctk.CTkFrame(
            self, width=4, fg_color=self._type_color, corner_radius=0,
        )
        bar.pack(side="left", fill="y", padx=(0, 14))
        bar.pack_propagate(False)

        # ── Identity block (issuer + name) ─────────────────────────────────
        identity = ctk.CTkFrame(self, fg_color="transparent")
        identity.pack(side="left", fill="y", pady=14)

        # Issuer (small, dim)
        self._issuer_lbl = ctk.CTkLabel(
            identity, text="", font=F_MICRO, text_color=TEXT_SEC, anchor="w",
        )
        self._issuer_lbl.pack(anchor="w")

        # Account name
        name_text = self.account.get("issuer") or self.account["name"]
        self._name_lbl = ctk.CTkLabel(
            identity, text=self.account["name"],
            font=F_BTN, text_color=TEXT_PRI, anchor="w",
        )
        self._name_lbl.pack(anchor="w")

        # Type badge
        badge_text = "  TOTP  " if self.account["type"] == "totp" else "  HOTP  "
        self._badge = ctk.CTkLabel(
            identity, text=badge_text,
            font=F_MICRO, text_color=BG_DEEP,
            fg_color=self._type_color, corner_radius=4,
        )
        self._badge.pack(anchor="w", pady=(4, 0))

        # ── OTP code (centred, large) ──────────────────────────────────────
        code_area = ctk.CTkFrame(self, fg_color="transparent")
        code_area.pack(side="left", fill="both", expand=True, pady=14)

        self._code_var = StringVar(value="— — — —")
        self._code_lbl = ctk.CTkLabel(
            code_area, textvariable=self._code_var,
            font=F_CODE, text_color=TEXT_PRI,
        )
        self._code_lbl.pack(expand=True)

        # ── Right-side controls ────────────────────────────────────────────
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(side="right", padx=14, pady=10, fill="y")

        # Progress arc canvas (TOTP) or counter + Next button (HOTP)
        if self.account["type"] == "totp":
            self._canvas = tk.Canvas(
                controls,
                width=self._ARC_SIZE, height=self._ARC_SIZE,
                bg=BG_CARD, highlightthickness=0,
            )
            self._canvas.pack(pady=(4, 2))
            self._arc_bg_id  = None
            self._arc_id     = None
            self._timer_text = None
            self._init_arc()

            self._timer_var = StringVar(value="")
            ctk.CTkLabel(
                controls, textvariable=self._timer_var,
                font=F_MICRO, text_color=TEXT_SEC,
            ).pack()
        else:
            # Counter display
            self._counter_var_lbl = StringVar(value="")
            ctk.CTkLabel(
                controls, textvariable=self._counter_var_lbl,
                font=F_MICRO, text_color=TEXT_SEC,
            ).pack(pady=(4, 0))

            # "Next" button to advance HOTP counter
            ctk.CTkButton(
                controls, text="▶  Next",
                width=80, height=30, font=F_MICRO,
                fg_color=ORANGE, hover_color="#CC5544",
                text_color="#0D1117", corner_radius=6,
                command=lambda: self._on_inc(self.index),
            ).pack(pady=4)

        # Action buttons (copy, delete)
        btn_row = ctk.CTkFrame(controls, fg_color="transparent")
        btn_row.pack(pady=(6, 0))

        self._copy_btn = ctk.CTkButton(
            btn_row, text="Copy", width=52, height=26, font=F_MICRO,
            fg_color=BG_PANEL, hover_color=BG_HOVER,
            border_color=BORDER, border_width=1,
            text_color=TEXT_PRI, corner_radius=6,
            command=self._copy,
        )
        self._copy_btn.pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            btn_row, text="✕", width=26, height=26, font=F_MICRO,
            fg_color=BG_PANEL, hover_color="#3D1C1C",
            border_color=BORDER, border_width=1,
            text_color=ORANGE, corner_radius=6,
            command=lambda: self._on_del(self.index),
        ).pack(side="left")

    def _init_arc(self) -> None:
        """Draw the initial (full) progress ring on the canvas."""
        s  = self._ARC_SIZE
        i  = self._ARC_INSET
        bx0, by0 = i, i
        bx1, by1 = s - i, s - i

        # Background ring (dim)
        self._arc_bg_id = self._canvas.create_arc(
            bx0, by0, bx1, by1,
            start=90, extent=-360,
            outline=BORDER, width=self._ARC_WIDTH, style="arc",
        )
        # Foreground arc (progress)
        self._arc_id = self._canvas.create_arc(
            bx0, by0, bx1, by1,
            start=90, extent=-360,
            outline=self._type_color, width=self._ARC_WIDTH, style="arc",
        )
        # Centre text (seconds remaining)
        self._timer_text = self._canvas.create_text(
            s // 2, s // 2, text="", fill=TEXT_SEC, font=("", 9),
        )

    # ── Update ────────────────────────────────────────────────────────────

    def update_display(self) -> None:
        """
        Refresh the OTP code and progress indicator.

        Called every second by :class:`MainApp._tick`.  For TOTP cards the
        arc extent and centre text are updated; for HOTP cards the counter
        label is refreshed (code stays fixed until "Next" is pressed).
        """
        acct = self.account

        # Update issuer label (shown above the account name)
        issuer = acct.get("issuer", "")
        self._issuer_lbl.configure(text=issuer if issuer else "")

        if acct["type"] == "totp":
            code, remaining = generate_totp(
                acct["secret"], acct["digits"], acct["period"], acct["algorithm"],
            )
            # Format code as "XXX XXX" or "XXXX XXXX" for readability
            mid  = len(code) // 2
            self._code_var.set(f"{code[:mid]}  {code[mid:]}")

            # Colour code urgency: red < 5 s, yellow 5-10 s, green otherwise
            if remaining <= 5:
                self._code_lbl.configure(text_color=ORANGE)
            elif remaining <= 10:
                self._code_lbl.configure(text_color="#D29922")
            else:
                self._code_lbl.configure(text_color=TEXT_PRI)

            # Update arc (fraction of period remaining → arc degrees)
            fraction = remaining / acct["period"]
            extent   = -360 * fraction
            self._canvas.itemconfigure(self._arc_id, extent=extent)
            self._canvas.itemconfigure(self._timer_text, text=str(remaining))
            self._timer_var.set(f"{remaining}s")

        else:
            # HOTP — code only changes when the user advances the counter
            code = generate_hotp(
                acct["secret"], acct["counter"], acct["digits"], acct["algorithm"],
            )
            mid = len(code) // 2
            self._code_var.set(f"{code[:mid]}  {code[mid:]}")
            self._counter_var_lbl.set(f"Counter: {acct['counter']}")

    def _copy(self) -> None:
        """Copy the current OTP code (digits only) and flash the button."""
        raw_code = self._code_var.get().replace(" ", "")
        self._on_copy(raw_code)
        # Visual feedback
        self._copy_btn.configure(text="✓ Copied!", fg_color=ACCENT2,
                                 text_color="#0D1117")
        self.after(1400, lambda: self._copy_btn.configure(
            text="Copy", fg_color=BG_PANEL, text_color=TEXT_PRI,
        ))


# ── Main application window ───────────────────────────────────────────────────

class MainApp:
    """
    Root application window.

    Manages the account list, the 1-second refresh loop, sidebar controls,
    and search filtering.

    :param root:    The :class:`customtkinter.CTk` root window.
    :param storage: An unlocked :class:`StorageManager` instance.
    """

    def __init__(self, root: ctk.CTk, storage: StorageManager) -> None:
        self._root    = root
        self._storage = storage
        self._cards:  list[AccountCard] = []

        root.title("2FA Authenticator")
        root.geometry("860x620")
        root.minsize(720, 480)
        root.configure(fg_color=BG_DEEP)

        self._build_layout()
        self._refresh_cards()
        self._tick()            # Start the 1-second update loop

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        """Construct the two-column layout (sidebar + main area)."""
        # ── Outer container ────────────────────────────────────────────────
        outer = ctk.CTkFrame(self._root, fg_color="transparent")
        outer.pack(fill="both", expand=True)

        # ── Left sidebar ───────────────────────────────────────────────────
        sidebar = ctk.CTkFrame(outer, width=220, fg_color=BG_PANEL, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Brand
        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(24, 20))
        ctk.CTkLabel(brand, text="🔐", font=("", 28)).pack(anchor="w")
        ctk.CTkLabel(brand, text="2FA Vault",
                     font=F_DISPLAY, text_color=TEXT_PRI).pack(anchor="w")
        ctk.CTkLabel(brand, text="Authenticator",
                     font=F_SMALL, text_color=TEXT_DIM).pack(anchor="w")

        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", pady=4)

        # Add account button
        ctk.CTkButton(
            sidebar, text="+ Add Account", height=40,
            font=F_BTN, fg_color=ACCENT, hover_color="#3880CC",
            text_color="#0D1117", corner_radius=10,
            command=self._open_add_dialog,
        ).pack(fill="x", padx=16, pady=(16, 8))

        # Stats labels
        self._count_var = StringVar(value="0 accounts")
        ctk.CTkLabel(
            sidebar, textvariable=self._count_var,
            font=F_MICRO, text_color=TEXT_DIM,
        ).pack(padx=20, anchor="w")

        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).pack(fill="x", pady=12)

        # Legend
        ctk.CTkLabel(sidebar, text="LEGEND", font=F_MICRO, text_color=TEXT_DIM).pack(anchor="w", padx=20)
        for colour, label in ((ACCENT2, "TOTP — time-based"), (ORANGE, "HOTP — counter")):
            row = ctk.CTkFrame(sidebar, fg_color="transparent")
            row.pack(anchor="w", padx=20, pady=2)
            ctk.CTkFrame(row, width=10, height=10, fg_color=colour,
                         corner_radius=2).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(row, text=label, font=F_MICRO, text_color=TEXT_SEC).pack(side="left")

        # Spacer to push version to bottom
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="y", expand=True)

        # Version footer
        ctk.CTkLabel(
            sidebar, text="v1.0  •  AES-256 encrypted",
            font=F_MICRO, text_color=TEXT_DIM,
        ).pack(padx=20, pady=16, anchor="w")

        # ── Right main area ────────────────────────────────────────────────
        main_area = ctk.CTkFrame(outer, fg_color="transparent")
        main_area.pack(side="left", fill="both", expand=True)

        # Top bar with search
        topbar = ctk.CTkFrame(main_area, fg_color="transparent")
        topbar.pack(fill="x", padx=20, pady=(18, 8))

        ctk.CTkLabel(topbar, text="Your Accounts",
                     font=F_TITLE, text_color=TEXT_PRI).pack(side="left")

        # Search entry
        self._search_var = StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_cards())
        search_entry = ctk.CTkEntry(
            topbar, textvariable=self._search_var,
            placeholder_text="🔍  Search accounts…",
            width=200, height=34, font=F_SMALL,
            fg_color=BG_CARD, border_color=BORDER,
            text_color=TEXT_PRI,
        )
        search_entry.pack(side="right")

        # Scrollable cards list
        self._card_list = ctk.CTkScrollableFrame(
            main_area, fg_color="transparent",
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT,
        )
        self._card_list.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        # Empty-state placeholder
        self._empty_frame = ctk.CTkFrame(
            self._card_list, fg_color=BG_PANEL, corner_radius=14,
        )
        self._empty_lbl = ctk.CTkLabel(
            self._empty_frame,
            text="🗝\n\nNo accounts yet\n\nClick  + Add Account  to get started",
            font=F_BODY, text_color=TEXT_DIM, justify="center",
        )
        self._empty_lbl.pack(expand=True, pady=60, padx=40)

    # ── Card management ───────────────────────────────────────────────────

    def _refresh_cards(self) -> None:
        """Destroy all existing card widgets and rebuild from storage."""
        for card in self._cards:
            card.destroy()
        self._cards.clear()

        accounts = self._storage.get_accounts()
        self._count_var.set(f"{len(accounts)} account{'s' if len(accounts) != 1 else ''}")

        if not accounts:
            self._empty_frame.pack(fill="x", pady=8)
        else:
            self._empty_frame.pack_forget()
            for idx, acct in enumerate(accounts):
                card = AccountCard(
                    self._card_list, acct, idx,
                    on_delete=self._delete_account,
                    on_copy=self._copy_code,
                    on_counter_increment=self._increment_counter,
                )
                card.pack(fill="x", pady=5)
                self._cards.append(card)

    def _filter_cards(self) -> None:
        """Show / hide cards based on the search query."""
        query = self._search_var.get().lower().strip()
        for card in self._cards:
            name   = card.account.get("name",   "").lower()
            issuer = card.account.get("issuer", "").lower()
            if not query or query in name or query in issuer:
                card.pack(fill="x", pady=5)
            else:
                card.pack_forget()

    # ── Actions ───────────────────────────────────────────────────────────

    def _open_add_dialog(self) -> None:
        """Open the Add Account modal and refresh cards if an account was added."""
        dlg = AddAccountDialog(self._root)
        self._root.wait_window(dlg)
        if dlg.result:
            self._storage.add_account(dlg.result)
            self._refresh_cards()

    def _delete_account(self, index: int) -> None:
        """Confirm deletion and remove the account from storage."""
        acct = self._storage.get_accounts()[index]
        name = acct.get("name", "this account")
        if messagebox.askyesno(
            "Delete Account",
            f"Remove  '{name}'  from the vault?\n\nThis cannot be undone.",
            icon="warning",
        ):
            self._storage.remove_account(index)
            self._refresh_cards()

    def _copy_code(self, code: str) -> None:
        """Copy *code* to the clipboard."""
        _clipboard_copy(self._root, code)

    def _increment_counter(self, index: int) -> None:
        """
        Increment the HOTP counter for the account at *index*.

        The new counter value is persisted immediately so that it survives
        application restarts.
        """
        accounts = self._storage.get_accounts()
        acct     = dict(accounts[index])
        acct["counter"] += 1
        self._storage.update_account(index, acct)

        # Update the card's local copy so it re-renders immediately
        card = self._cards[index]
        card.account = acct
        card.update_display()

    # ── Update loop ───────────────────────────────────────────────────────

    def _tick(self) -> None:
        """
        Called every 1 000 ms via :meth:`tk.after`.

        Updates all visible AccountCard widgets without rebuilding them —
        this avoids the flicker that would occur from destroy/recreate.
        """
        for card in self._cards:
            try:
                card.update_display()
            except tk.TclError:
                pass   # Widget may have been destroyed mid-tick
        self._root.after(1000, self._tick)   # Schedule next tick
