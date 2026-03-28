# Contributing to 2FA Authenticator

Thank you for your interest in contributing to the 2FA Authenticator project! We welcome code contributions, issue reports, bug fixes, and suggestions to make this the ultimate desktop 2FA tool.

## Getting Started

1. **Fork the Repository:** Start by forking the project to your own GitHub account.
2. **Clone Locally:** 
   ```bash
   git clone https://github.com/your-username/2fa_app.git
   cd 2fa_app
   ```
3. **Setup Environment:** Use the provided generic Makefile:
   ```bash
   make install
   make run
   ```

## Development Workflow

1. **Create a branch:** For each feature or bug fix, create a new branch from `main`.
2. **Make changes:** Keep your commits concise and focused. Remember to always format and lint:
   ```bash
   make format
   make lint
   ```
3. **Run the Tests:** We use `pytest` for the `otp_engine` tests. Ensure tests still pass locally:
   ```bash
   make test
   ```
4. **Submit a Pull Request (PR):** Push your branch securely to GitHub and create a Pull Request against our `main` branch. Provide a clear description of the issue and what your fix or enhancement accomplishes.

## Code Standards
- Code must be formatted with `black` and pass `flake8` checks.
- Changes impacting the cryptography or TOTP generation logic must include valid, newly created unit tests.
- UI changes should maintain the dark-glass aesthetic, sticking to the existing design tokens found in `gui.py`.

## Bug Reports and Feature Requests
If you encounter a bug or have an idea for a feature, please feel free to open a detailed issue ticket on the GitHub tracker.

We look forward to seeing your contributions!
