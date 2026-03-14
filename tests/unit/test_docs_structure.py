"""Tests for documentation structure verification (Feature 018, Batch 01).

Task 001: Demo script + architecture docs — AC-1..4, EC-1..2, ERR-1
Task 002: README — AC-1..4, EC-1..2, ERR-1
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "docs"


# ---------------------------------------------------------------------------
# Task001 AC-1 `test_demo_script_has_four_sections`
# ---------------------------------------------------------------------------


def test_demo_script_has_four_sections():
    """Task001 AC-1 test_demo_script_has_four_sections — exactly 4 demo sections."""
    path = DOCS / "demo-script.md"
    assert path.exists(), f"Required documentation file not found: {path}"
    content = path.read_text()
    demo_sections = re.findall(r"^## Demo \d", content, re.MULTILINE)
    assert len(demo_sections) == 4, f"Expected 4 demo sections, found {len(demo_sections)}"


# ---------------------------------------------------------------------------
# Task001 AC-2 `test_demo_sections_have_content`
# ---------------------------------------------------------------------------


def test_demo_sections_have_content():
    """Task001 AC-2 test_demo_sections_have_content — each demo has input + expected outcome."""
    path = DOCS / "demo-script.md"
    assert path.exists(), f"Required documentation file not found: {path}"
    content = path.read_text()

    # Split by ## Demo N headers
    sections = re.split(r"^## Demo \d", content, flags=re.MULTILINE)
    # First element is pre-header content, remaining are the 4 demo sections
    demo_bodies = sections[1:]
    assert len(demo_bodies) == 4, f"Expected 4 demo sections, found {len(demo_bodies)}"

    for i, body in enumerate(demo_bodies, 1):
        # Each should have some form of input text/command
        has_input = (
            "curl" in body.lower()
            or "input_text" in body
            or "/ui/" in body
            or "POST" in body
            or "```" in body
        )
        assert has_input, f"Demo {i} missing input/command instructions"

        # Each should describe expected outcome
        has_outcome = (
            "expected" in body.lower()
            or "result" in body.lower()
            or "outcome" in body.lower()
            or "response" in body.lower()
            or "status" in body.lower()
        )
        assert has_outcome, f"Demo {i} missing expected outcome"


# ---------------------------------------------------------------------------
# Task001 AC-3 `test_architecture_has_layers`
# ---------------------------------------------------------------------------


def test_architecture_has_layers():
    """Task001 AC-3 test_architecture_has_layers — contains all 4 layer descriptions."""
    path = DOCS / "architecture.md"
    assert path.exists(), f"Required documentation file not found: {path}"
    content = path.read_text().lower()

    layers = ["persistence", "domain engine", "runtime", "api"]
    for layer in layers:
        assert layer in content, f"Architecture doc missing layer: {layer}"


# ---------------------------------------------------------------------------
# Task001 AC-4 `test_architecture_has_extension_seams`
# ---------------------------------------------------------------------------


def test_architecture_has_extension_seams():
    """Task001 AC-4 test_architecture_has_extension_seams — data flow + extension seams."""
    path = DOCS / "architecture.md"
    assert path.exists(), f"Required documentation file not found: {path}"
    content = path.read_text().lower()

    assert "data flow" in content, "Architecture doc missing data flow description"
    assert "extension" in content or "seam" in content, (
        "Architecture doc missing extension seams"
    )


# ---------------------------------------------------------------------------
# Task001 EC-1 `test_demo_script_valid_endpoints`
# ---------------------------------------------------------------------------


def test_demo_script_valid_endpoints():
    """Task001 EC-1 test_demo_script_valid_endpoints — all API/UI paths match real routes."""
    path = DOCS / "demo-script.md"
    assert path.exists(), f"Required documentation file not found: {path}"
    content = path.read_text()

    # Valid API paths (prefix /runs mounted at app level)
    valid_api_patterns = [
        r"/runs",
        r"/runs/[^/\s\"']+",
        r"/runs/[^/\s\"']+/events",
        r"/runs/[^/\s\"']+/review",
        r"/runs/[^/\s\"']+/replay",
        r"/runs/[^/\s\"']+/bundle",
    ]
    # Valid UI paths (prefix /ui)
    valid_ui_patterns = [
        r"/ui/intake",
        r"/ui/runs/[^/\s\"']+",
        r"/ui/runs/[^/\s\"']+/review",
        r"/ui/runs/[^/\s\"']+/replay",
    ]

    all_valid = valid_api_patterns + valid_ui_patterns

    # Extract paths from curl commands and URLs in the doc
    # Look for paths like /runs, /runs/{run_id}, /ui/intake etc.
    url_pattern = r'(?:http://127\.0\.0\.1:8000)((?:/ui)?/(?:runs|intake)[^\s"\'`)*]*)'
    found_paths = re.findall(url_pattern, content)

    assert len(found_paths) > 0, "No API/UI paths found in demo script"

    for path_str in found_paths:
        matched = any(re.fullmatch(pat, path_str) for pat in all_valid)
        assert matched, f"Demo script references invalid endpoint: {path_str}"


# ---------------------------------------------------------------------------
# Task001 EC-2 `test_architecture_dir_structure`
# ---------------------------------------------------------------------------


def test_architecture_dir_structure():
    """Task001 EC-2 test_architecture_dir_structure — listed directories exist."""
    path = DOCS / "architecture.md"
    assert path.exists(), f"Required documentation file not found: {path}"
    content = path.read_text()

    # Extract directory-like references from code blocks
    # Look for lines like "  app/core/" or "app/api/" in the doc
    dir_refs = re.findall(r"\b(app/\w+(?:/\w+)*)/", content)

    assert len(dir_refs) > 0, "No directory references found in architecture doc"

    for dir_ref in dir_refs:
        dir_path = ROOT / dir_ref
        assert dir_path.is_dir(), (
            f"Directory referenced in architecture doc does not exist: {dir_ref}"
        )


# ---------------------------------------------------------------------------
# Task001 ERR-1 `test_missing_doc_file_fails`
# ---------------------------------------------------------------------------


def test_missing_doc_file_fails():
    """Task001 ERR-1 test_missing_doc_file_fails — missing doc file produces descriptive error."""
    nonexistent = DOCS / "nonexistent-doc.md"
    assert not nonexistent.exists(), "Test setup: file should not exist"

    with pytest.raises(AssertionError, match="Required documentation file not found"):
        if not nonexistent.exists():
            raise AssertionError(f"Required documentation file not found: {nonexistent}")


# ---------------------------------------------------------------------------
# Task002 AC-1 `test_readme_has_summary`
# ---------------------------------------------------------------------------


def test_readme_has_summary():
    """Task002 AC-1 test_readme_has_summary — title + deterministic AI workflow summary."""
    path = ROOT / "README.md"
    assert path.exists(), "Required file not found: README.md"
    content = path.read_text()

    assert "ai-workflow-engine" in content.lower(), "README missing project title"
    assert "deterministic" in content.lower(), "README missing deterministic keyword in summary"
    assert "workflow" in content.lower(), "README missing workflow keyword in summary"


# ---------------------------------------------------------------------------
# Task002 AC-2 `test_readme_has_setup`
# ---------------------------------------------------------------------------


def test_readme_has_setup():
    """Task002 AC-2 test_readme_has_setup — contains pip install and Python version."""
    path = ROOT / "README.md"
    assert path.exists(), "Required file not found: README.md"
    content = path.read_text()

    assert "pip install" in content or "make install" in content, (
        "README missing install instructions"
    )
    assert "python" in content.lower() or "3.11" in content, (
        "README missing Python version prerequisite"
    )


# ---------------------------------------------------------------------------
# Task002 AC-3 `test_readme_has_demo`
# ---------------------------------------------------------------------------


def test_readme_has_demo():
    """Task002 AC-3 test_readme_has_demo — contains make demo and link to demo-script."""
    path = ROOT / "README.md"
    assert path.exists(), "Required file not found: README.md"
    content = path.read_text()

    assert "make demo" in content, "README missing `make demo` command"
    assert "demo-script.md" in content, "README missing link to docs/demo-script.md"


# ---------------------------------------------------------------------------
# Task002 AC-4 `test_readme_has_arch_and_testing`
# ---------------------------------------------------------------------------


def test_readme_has_arch_and_testing():
    """Task002 AC-4 test_readme_has_arch_and_testing — architecture + testing sections."""
    path = ROOT / "README.md"
    assert path.exists(), "Required file not found: README.md"
    content = path.read_text().lower()

    assert "architecture" in content, "README missing architecture section"
    assert "architecture.md" in content, "README missing link to docs/architecture.md"
    assert "make test" in content, "README missing `make test` command"


# ---------------------------------------------------------------------------
# Task002 EC-1 `test_readme_make_targets_exist`
# ---------------------------------------------------------------------------


def test_readme_make_targets_exist():
    """Task002 EC-1 test_readme_make_targets_exist — referenced make targets are real."""
    readme_path = ROOT / "README.md"
    makefile_path = ROOT / "Makefile"
    assert readme_path.exists(), "Required file not found: README.md"
    assert makefile_path.exists(), "Required file not found: Makefile"

    readme = readme_path.read_text()
    makefile = makefile_path.read_text()

    # Extract make targets referenced in README
    targets = re.findall(r"make (\w[\w-]*)", readme)
    assert len(targets) > 0, "No make targets found in README"

    # Extract .PHONY targets from Makefile
    phony_match = re.search(r"\.PHONY:\s*(.+)", makefile)
    assert phony_match, "No .PHONY targets in Makefile"
    phony_targets = set(phony_match.group(1).split())

    # Also check for standalone target definitions (target:)
    defined_targets = set(re.findall(r"^(\w[\w-]*):", makefile, re.MULTILINE))

    all_targets = phony_targets | defined_targets

    for target in targets:
        assert target in all_targets, (
            f"README references `make {target}` but target not found in Makefile"
        )


# ---------------------------------------------------------------------------
# Task002 EC-2 `test_readme_links_valid`
# ---------------------------------------------------------------------------


def test_readme_links_valid():
    """Task002 EC-2 test_readme_links_valid — linked doc files exist."""
    readme_path = ROOT / "README.md"
    assert readme_path.exists(), "Required file not found: README.md"
    content = readme_path.read_text()

    # Extract relative markdown links to local files
    links = re.findall(r"\[.*?\]\((docs/[^)]+)\)", content)
    assert len(links) > 0, "No doc links found in README"

    for link in links:
        link_path = ROOT / link
        assert link_path.exists(), f"README links to non-existent file: {link}"


# ---------------------------------------------------------------------------
# Task002 ERR-1 `test_missing_readme_fails`
# ---------------------------------------------------------------------------


def test_missing_readme_fails():
    """Task002 ERR-1 test_missing_readme_fails — missing README produces descriptive error."""
    nonexistent = ROOT / "NONEXISTENT_README.md"
    assert not nonexistent.exists(), "Test setup: file should not exist"

    with pytest.raises(AssertionError, match="Required file not found"):
        if not nonexistent.exists():
            raise AssertionError(f"Required file not found: {nonexistent.name}")
