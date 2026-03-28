# Release Notes: 2FA Authenticator v1.1.0

**Release Date:** March 28, 2026

We are thrilled to announce version **1.1.0** of the 2FA Authenticator! This update focuses on professionalizing the project's build tooling, enhancing visual identity, and expanding repository documentation for contributors.

---

## 🚀 Highlights

### Professional Build Ecosystem
We have introduced a powerful, fully automated `Makefile` configured for a hassle-free developer experience.
- **One-Command Setup:** Use `make install` to bootstrap your Python virtual environment dynamically with all necessary dependencies and toolchains.
- **Standalone Native Binaries:** Use `make build` to seamlessly trigger **PyInstaller**. This bundles Python, CustomTkinter, cryptography primitives, and local assets into a single lightweight, hidden-console executable/app bundle perfectly tailored for native OS execution.
- **Development Tooling:** New test runners (`pytest`), linters (`flake8`), and aggressive code formatters (`black`) are tightly integrated across standard targets (`make test`, `make lint`, `make format`). 

### Refined Brand & Aesthetic
- **New App Icon & Logo:** Replaced the default Tkinter window icon with a gorgeous, dark-glassmorphism neon-cyan shield.
- On compilation via `make build`, the final application executable seamlessly absorbs the embedded `.png` to correctly present the native application icon inside the MacOS command dock and Windows Taskbar alike. 

### Hardened Code & Reliability fixes
- Edge cases in `otp_engine.py` processing malformed or oddly padded user TOTP secrets have been fortified, maximizing reliable compatibility with QR codes exported from Google Authenticator, Authy, or Microsoft Authenticator.

### New Documentation
- [**SECURITY.md**](./SECURITY.md): Added clear bug handling standards outlining our explicit threat model (utilizing AES-256 local encrypted SQLite vaults decoupled from the cloud).
- [**CONTRIBUTING.md**](./CONTRIBUTING.md): Laid down strict, clear contributor expectations on pull-requests, test writing, and preserving the CustomTkinter dark-glass aesthetic for new components.
- [**CHANGELOG.md**](./CHANGELOG.md): Centralized a semantic versioning tracker to monitor past features like the initial HOTP framework and pyzbar webcam capabilities.
- **LICENSE**: Added a protective, permissive standard **MIT License** to encourage open-source modification whilst providing liability shielding.

---

## 📦 Upgrading

### Running from Source
If updating via `git pull`:
```bash
make clean-all    # Nuke the old caches
make run          # Re-initialize dependencies & launch the UI
```

### From Compiled Bundle
Users running the `.zip` distributable can seamlessly override their old v1.0 file. Your SQLite `StorageManager` vault relies on `~/.2fa_authenticator` and resides safely unaffected by the executable itself. Your master-password remains unchanged.
