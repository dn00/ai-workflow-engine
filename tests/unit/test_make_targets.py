"""Tests for Makefile targets (Feature 017, Batch 01, Task 001)."""

import subprocess

import pytest


# ---------------------------------------------------------------------------
# Task001 AC-1: make demo starts server
# ---------------------------------------------------------------------------

def test_makefile_demo_target_exists():
    """Task001 AC-1 test_makefile_demo_target_exists — demo target exists and has uvicorn."""
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "uvicorn app.main:app" in result.stdout


# ---------------------------------------------------------------------------
# Task001 AC-2: data directory created
# ---------------------------------------------------------------------------

def test_makefile_demo_creates_data_dir():
    """Task001 AC-2 test_makefile_demo_creates_data_dir — demo target creates data/ dir."""
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "mkdir -p data" in result.stdout


# ---------------------------------------------------------------------------
# Task001 AC-3: Startup banner printed
# ---------------------------------------------------------------------------

def test_makefile_demo_has_banner():
    """Task001 AC-3 test_makefile_demo_has_banner — demo target prints banner with URL."""
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "127.0.0.1:8000" in result.stdout


# ---------------------------------------------------------------------------
# Task001 EC-1: data/ already exists (mkdir -p idempotent)
# ---------------------------------------------------------------------------

def test_mkdir_p_idempotent():
    """Task001 EC-1 test_mkdir_p_idempotent — mkdir -p is used so existing data/ is fine."""
    result = subprocess.run(
        ["make", "-n", "demo"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # mkdir -p is idempotent — the flag -p prevents errors if dir exists
    assert "mkdir -p data" in result.stdout
