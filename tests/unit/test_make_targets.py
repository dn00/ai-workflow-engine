"""Tests for Makefile targets."""

import subprocess

import pytest


# ---------------------------------------------------------------------------
# make demo starts server
# ---------------------------------------------------------------------------

def test_makefile_demo_target_exists():
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "uvicorn app.main:app" in result.stdout


# ---------------------------------------------------------------------------
# data directory created
# ---------------------------------------------------------------------------

def test_makefile_demo_creates_data_dir():
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "mkdir -p data" in result.stdout


# ---------------------------------------------------------------------------
# Startup banner printed
# ---------------------------------------------------------------------------

def test_makefile_demo_has_banner():
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "127.0.0.1:8000" in result.stdout


# ---------------------------------------------------------------------------
# data/ already exists (mkdir -p idempotent)
# ---------------------------------------------------------------------------

def test_mkdir_p_idempotent():
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # mkdir -p is idempotent — the flag -p prevents errors if dir exists
    assert "mkdir -p data" in result.stdout
