# -----------------------------------------------------------------------------
# Professional Makefile for 2FA Authenticator
# -----------------------------------------------------------------------------

# --- Configuration & Variables ---
APP_NAME    := 2FA_Authenticator
MAIN_SCRIPT := main.py
PYTHON      := python3

# Virtual Environment
VENV        := venv
VENV_BIN    := $(VENV)/bin
PIP         := $(VENV_BIN)/pip
VENV_PYTHON := $(VENV_BIN)/python

# File Discovery
SOURCES     := $(wildcard *.py)

# Standardize shell
SHELL := /bin/bash

# --- Defines ---
.PHONY: help install run test lint format build dist clean clean-all

# --- Default Target ---
.DEFAULT_GOAL := help

# --- Help Target ---
help: ## Display this help message
	@echo "======================================================================"
	@echo "                    $(APP_NAME) Build System                           "
	@echo "======================================================================"
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo "======================================================================"

# --- Environment & Dependencies ---
$(VENV)/touchfile: requirements.txt
	@echo "[+] Setting up virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "[+] Upgrading pip..."
	$(PIP) install --upgrade pip
	@echo "[+] Installing project requirements..."
	$(PIP) install -r requirements.txt
	@echo "[+] Installing build and dev tools..."
	$(PIP) install pyinstaller black flake8 pytest
	@touch $(VENV)/touchfile

install: $(VENV)/touchfile ## Initialize virtual env and install dependencies

# --- Development Tasks ---
run: install ## Run the application from source
	@echo "[+] Running $(APP_NAME)..."
	$(VENV_PYTHON) $(MAIN_SCRIPT)

test: install ## Run test suite using pytest
	@echo "[+] Running tests..."
	$(VENV_BIN)/pytest -v

format: install ## Auto-format Python source files using Black
	@echo "[+] Formatting code with Black..."
	$(VENV_BIN)/black $(SOURCES)

lint: install ## Lint Python source files using flake8
	@echo "[+] Linting code with flake8..."
	$(VENV_BIN)/flake8 $(SOURCES) --max-line-length=100 --extend-ignore=E203,E221,E241,E272,E501

# --- Build & Packaging Tasks ---
build: install clean-build ## Build a standalone executable/app bundle via PyInstaller
	@echo "[+] Building $(APP_NAME) executable..."
	$(VENV_BIN)/pyinstaller \
		--name="$(APP_NAME)" \
		--windowed \
		--onefile \
		--icon=assets/icon.png \
		--add-data="assets:assets" \
		--noconfirm \
		--clean \
		$(MAIN_SCRIPT)
	@echo "[+] Build complete. Check the 'dist/' directory."

dist: build ## Package the built executable into a distributable ZIP archive
	@echo "[+] Packaging application for distribution..."
	@cd dist && \
	if [ -d "$(APP_NAME).app" ]; then \
		echo "Zipping macOS App Bundle..."; \
		zip -qr $(APP_NAME)_macOS.zip $(APP_NAME).app; \
		echo "Ready: dist/$(APP_NAME)_macOS.zip"; \
	elif [ -f "$(APP_NAME)" ]; then \
		echo "Zipping Linux/Unix binary..."; \
		zip -q $(APP_NAME)_linux.zip $(APP_NAME); \
		echo "Ready: dist/$(APP_NAME)_linux.zip"; \
	fi

# --- Cleanup Tasks ---
clean-build: ## Remove previous build artifacts
	@echo "[+] Cleaning build artifacts..."
	rm -rf build/ dist/ *.spec

clean: clean-build ## Remove compile caches and build artifacts
	@echo "[+] Cleaning python cache files..."
	rm -rf __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-all: clean ## Perform a deep clean (removes virtual env)
	@echo "[+] Removing virtual environment..."
	rm -rf $(VENV)
	@echo "[+] Deep clean completed."
