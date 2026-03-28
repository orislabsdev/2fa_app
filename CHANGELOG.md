# Changelog

All notable changes to the 2FA Authenticator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-03-28

### Added
- **Build System**: Introduced an advanced Makefile configured with linting, formatting (`black`/`flake8`), test running, and PyInstaller for building native, standalone executables automatically (`make build`).
- **Assets**: Added `assets/` directory containing the `logo.png`/`icon.png` application icon, supporting native window icons and App icon bundling via the new build system.
- **Documentation**: Initialized project-related templates: `CONTRIBUTING.md`, `SECURITY.md`, and this `CHANGELOG.md`.

### Fixed
- Improved padding reliability and robustness of TOTP key generation for edge-case bases (`otp_engine.py`).

## [1.0.0] - 2026-03-25

### Added
- **Core Functionality**: Full integration of HOTP / TOTP token generation leveraging `pyotp`.
- **UI Toolkit**: Initial release of the dark-glass aesthetic minimalist UI using CustomTkinter. Included an `AddAccountDialog` equipped with webcam-based QR scanning (via OpenCV and pyzbar) as well as file-based QR code decoding capabilities.
- **Master Encrypted Vault**: `cryptography` backed fully encrypted SQLite database wrapper class `StorageManager` providing self-contained, AES-256 persistent token storage out of the box in the `~/.2fa_authenticator` user directory.
- Fully functional UI bindings with search filtering, circular progress progress arcs for TOTP visual countdown, and 1-second auto-update loops.
