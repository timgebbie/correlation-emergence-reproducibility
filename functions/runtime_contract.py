"""Frozen numerical-library contract for reproducible gate execution."""

from __future__ import annotations

import importlib.metadata
import platform
import sys


EXPECTED_PACKAGE_VERSIONS = {
    "numpy": "2.3.5",
    "matplotlib": "3.10.8",
    "pypdf": "6.10.0",
}
SUPPORTED_PYTHON_MINORS = {(3, 12), (3, 13)}


def installed_package_versions() -> dict[str, str]:
    return {
        package: importlib.metadata.version(package)
        for package in EXPECTED_PACKAGE_VERSIONS
    }


def runtime_version_errors() -> dict[str, tuple[str, str]]:
    installed = installed_package_versions()
    errors = {
        package: (installed[package], expected)
        for package, expected in EXPECTED_PACKAGE_VERSIONS.items()
        if installed[package] != expected
    }
    if sys.version_info[:2] not in SUPPORTED_PYTHON_MINORS:
        errors["python"] = (platform.python_version(), "3.12.x or 3.13.x")
    return errors


def verify_runtime_versions() -> dict[str, str]:
    installed = installed_package_versions()
    errors = runtime_version_errors()
    if errors:
        raise RuntimeError(f"numerical runtime does not match requirements.txt: {errors}")
    return {"python": platform.python_version(), **installed}


__all__ = [
    "EXPECTED_PACKAGE_VERSIONS",
    "SUPPORTED_PYTHON_MINORS",
    "installed_package_versions",
    "runtime_version_errors",
    "verify_runtime_versions",
]
