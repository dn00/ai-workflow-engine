"""Tests for project scaffold (Feature 001, Batches 01+02)."""

import pathlib
import re
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"


class TestTask001AC1DirectoryStructureExists:
    """Task001 AC-1 test_directory_structure_exists"""

    def test_directory_structure_exists(self) -> None:
        """All directories from spec §27 exist and Python packages have __init__.py."""
        # Expected Python packages (must have __init__.py)
        python_packages = [
            "app",
            "app/api",
            "app/api/routes",
            "app/api/schemas",
            "app/core",
            "app/core/events",
            "app/core/receipts",
            "app/core/replay",
            "app/core/policy",
            "app/core/projections",
            "app/core/runners",
            "app/workflows",
            "app/workflows/access_request",
            "app/effects",
            "app/db",
            "app/db/repositories",
            "app/services",
            "tests",
            "tests/unit",
            "tests/integration",
        ]
        for pkg in python_packages:
            pkg_dir = ROOT / pkg
            assert pkg_dir.is_dir(), f"Directory missing: {pkg}"
            init_file = pkg_dir / "__init__.py"
            assert init_file.is_file(), f"__init__.py missing in: {pkg}"

        # Non-package directories (no __init__.py required)
        non_package_dirs = [
            "app/templates",
            "tests/golden",
            "bundles",
            "docs",
        ]
        for d in non_package_dirs:
            assert (ROOT / d).is_dir(), f"Directory missing: {d}"


class TestTask001AC2PyprojectHasRequiredFields:
    """Task001 AC-2 test_pyproject_has_required_fields"""

    def test_pyproject_has_required_fields(self) -> None:
        """pyproject.toml exists, is parseable, and declares required dependencies."""
        pyproject_path = ROOT / "pyproject.toml"
        assert pyproject_path.is_file(), "pyproject.toml missing"

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        project = data.get("project", {})
        assert "name" in project, "project.name missing"

        # Core dependencies
        deps = project.get("dependencies", [])
        required_cores = [
            "fastapi",
            "uvicorn",
            "sqlalchemy",
            "pydantic",
            "jinja2",
            "python-multipart",
        ]
        dep_names = [
            d.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip().lower() for d in deps
        ]
        for req in required_cores:
            assert req in dep_names, f"Core dependency missing: {req}"

        # Dev dependencies
        optional = data.get("project", {}).get("optional-dependencies", {})
        dev_deps = optional.get("dev", [])
        dev_dep_names = [
            d.split(">")[0].split("<")[0].split("=")[0].split("[")[0].strip().lower()
            for d in dev_deps
        ]
        required_devs = ["pytest", "pytest-asyncio", "httpx", "ruff"]
        for req in required_devs:
            assert req in dev_dep_names, f"Dev dependency missing: {req}"


class TestTask001EC1AppPackageImportable:
    """Task001 EC-1 test_app_package_importable"""

    def test_app_package_importable(self) -> None:
        """After install, `import app` succeeds without errors."""
        import app  # noqa: F401


class TestTask001ERR1RequiresPython311Declared:
    """Task001 ERR-1 test_requires_python_311_declared"""

    def test_requires_python_311_declared(self) -> None:
        """pyproject.toml declares requires-python >= 3.11."""
        pyproject_path = ROOT / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        requires_python = data.get("project", {}).get("requires-python", "")
        assert "3.11" in requires_python, (
            f"requires-python should reference 3.11, got: {requires_python}"
        )
        assert ">=" in requires_python, f"requires-python should use >=, got: {requires_python}"


# --- Batch 02: Task 002 (Makefile targets) ---


def _makefile_content() -> str:
    return MAKEFILE.read_text()


class TestTask002AC1MakefileHasTestTarget:
    """Task002 AC-1 test_makefile_has_test_target"""

    def test_makefile_has_test_target(self) -> None:
        """Makefile defines a 'test' target that invokes pytest."""
        content = _makefile_content()
        assert re.search(r"^test:", content, re.MULTILINE), "Makefile missing 'test' target"
        assert "pytest" in content, "test target should invoke pytest"


class TestTask002AC2MakefileHasLintTarget:
    """Task002 AC-2 test_makefile_has_lint_target"""

    def test_makefile_has_lint_target(self) -> None:
        """Makefile defines a 'lint' target that invokes ruff."""
        content = _makefile_content()
        assert re.search(r"^lint:", content, re.MULTILINE), "Makefile missing 'lint' target"
        assert "ruff check" in content, "lint target should invoke ruff check"
        assert "ruff format" in content, "lint target should invoke ruff format"


class TestTask002EC1MakefileHasDemoTarget:
    """Task002 EC-1 test_makefile_has_demo_target"""

    def test_makefile_has_demo_target(self) -> None:
        """Makefile defines a 'demo' target (stub)."""
        content = _makefile_content()
        assert re.search(r"^demo:", content, re.MULTILINE), "Makefile missing 'demo' target"


class TestTask002EC2MakefileHasExportBundleTarget:
    """Task002 EC-2 test_makefile_has_export_bundle_target"""

    def test_makefile_has_export_bundle_target(self) -> None:
        """Makefile defines an 'export-bundle' target (stub)."""
        content = _makefile_content()
        assert re.search(r"^export-bundle:", content, re.MULTILINE), (
            "Makefile missing 'export-bundle' target"
        )


# --- Batch 02: Task 003 (Test infrastructure + smoke test) ---


class TestTask003AC1AppPackageImportable:
    """Task003 AC-1 test_app_package_importable"""

    def test_app_package_importable(self) -> None:
        """Smoke test: import app succeeds."""
        import app  # noqa: F401

        assert hasattr(app, "__file__")


class TestTask003AC2PytestConfigInPyproject:
    """Task003 AC-2 test_pytest_config_in_pyproject"""

    def test_pytest_config_in_pyproject(self) -> None:
        """pyproject.toml has [tool.pytest.ini_options] with testpaths."""
        pyproject_path = ROOT / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        pytest_config = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
        assert "testpaths" in pytest_config, "pytest testpaths not configured"
        assert "tests" in pytest_config["testpaths"], "testpaths should include 'tests'"


class TestTask003AC3TmpDbPathFixture:
    """Task003 AC-3 test_tmp_db_path_fixture"""

    def test_tmp_db_path_fixture(self, tmp_db_path: pathlib.Path) -> None:
        """conftest.py provides tmp_db_path fixture returning a Path."""
        assert isinstance(tmp_db_path, pathlib.Path)
        assert tmp_db_path.name == "test.db"
