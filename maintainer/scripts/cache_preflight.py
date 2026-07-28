"""Source-loaded preflight for unhashed compiled Python residue.

Maintainer entrypoints execute this file with ``compile``/``exec`` before any
local import. That deliberately bypasses Python's bytecode import machinery.
"""

from __future__ import annotations

import sys


# A package or PYTHONPATH directory could contain a compiled module that
# shadows the standard library. Build the temporary import path only from
# interpreter-owned locations before importing the helpers used below.
_ORIGINAL_SYS_PATH = list(sys.path)
_BASE_PREFIX = str(sys.base_prefix).replace("\\", "/").rstrip("/")
_STDLIB_DIRECTORY = getattr(sys, "_stdlib_dir", None)
if not _STDLIB_DIRECTORY:
    if sys.platform == "win32":
        _STDLIB_DIRECTORY = _BASE_PREFIX + "/Lib"
    else:
        _STDLIB_DIRECTORY = (
            _BASE_PREFIX
            + "/lib/python"
            + str(sys.version_info.major)
            + "."
            + str(sys.version_info.minor)
        )
_STDLIB_DIRECTORY = str(_STDLIB_DIRECTORY).replace("\\", "/").rstrip("/")
sys.path[:] = [
    _STDLIB_DIRECTORY,
    _STDLIB_DIRECTORY + "/lib-dynload",
    _BASE_PREFIX + "/DLLs",
    (
        _BASE_PREFIX
        + "/python"
        + str(sys.version_info.major)
        + str(sys.version_info.minor)
        + ".zip"
    ),
]
sys.dont_write_bytecode = True
import json
import os
from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path


_PROTECTED_IMPORT_NAMES = {
    name.casefold()
    for name in (
        *sys.stdlib_module_names,
        "_yaml",
        "attr",
        "attrs",
        "jsonschema",
        "jsonschema_specifications",
        "packaging",
        "referencing",
        "rpds",
        "typing_extensions",
        "yaml",
    )
}
_IMPORTABLE_FILE_SUFFIXES = tuple(sorted(
    {
        ".py",
        ".pyc",
        ".pyo",
        *(suffix.casefold() for suffix in EXTENSION_SUFFIXES),
    },
    key=len,
    reverse=True,
))


def _file_import_name(name: str) -> str | None:
    lowered = name.casefold()
    for suffix in _IMPORTABLE_FILE_SUFFIXES:
        if lowered.endswith(suffix):
            candidate = lowered[:-len(suffix)]
            return candidate or None
    return None


def _compiled_python_failures() -> list[dict[str, str]]:
    script_directory = Path(__file__).absolute().parent
    maintainer = script_directory.parent
    plugin = maintainer.parent
    scopes = (
        (
            "runtime-cache-residue",
            plugin / "skills" / "design-dna",
            "Remove compiled Python residue from the runtime skill.",
        ),
        (
            "maintainer-cache-residue",
            maintainer / "scripts",
            "Remove compiled Python residue from executable maintainer tooling.",
        ),
        (
            "maintainer-cache-residue",
            maintainer / "tests",
            "Remove compiled Python residue from executable maintainer tests.",
        ),
    )
    failures: list[dict[str, str]] = []

    def label(path: Path) -> str:
        try:
            return path.relative_to(plugin).as_posix()
        except ValueError:
            return str(path)

    for code, root, message in scopes:
        if not root.is_dir():
            continue

        def fail_walk(error: OSError, *, selected_root: Path = root) -> None:
            failures.append({
                "code": "compiled-python-inspection-failed",
                "path": label(
                    Path(error.filename)
                    if error.filename
                    else selected_root
                ),
                "message": str(error),
            })

        for current, directories, files in os.walk(
            root,
            topdown=True,
            followlinks=False,
            onerror=fail_walk,
        ):
            current_path = Path(current)
            for name in list(directories):
                if name.casefold() != "__pycache__":
                    continue
                cache = current_path / name
                failures.append({
                    "code": code,
                    "path": label(cache),
                    "message": message,
                })
                directories.remove(name)
            for name in files:
                if Path(name).suffix.casefold() not in {".pyc", ".pyo"}:
                    continue
                failures.append({
                    "code": code,
                    "path": label(current_path / name),
                    "message": message,
                })
    return sorted(
        failures,
        key=lambda item: (
            item["path"].casefold(),
            item["code"],
            item["message"],
        ),
    )


def _import_shadow_failures() -> list[dict[str, str]]:
    """Reject untrusted entries that can shadow release-tool imports."""
    script_directory = Path(__file__).absolute().parent
    plugin = script_directory.parent.parent
    trusted_roots = tuple(
        Path(value).absolute()
        for value in {sys.prefix, sys.base_prefix}
        if value
    )
    candidates = [plugin, script_directory]

    def is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    for entry in _ORIGINAL_SYS_PATH:
        try:
            path = Path(entry if entry else os.getcwd()).absolute()
        except (OSError, TypeError, ValueError):
            continue
        if any(is_within(path, root) for root in trusted_roots):
            continue
        candidates.append(path)

    failures: list[dict[str, str]] = []
    seen: set[str] = set()

    def label(path: Path) -> str:
        try:
            return path.relative_to(plugin).as_posix()
        except ValueError:
            return str(path)

    for directory in candidates:
        identity = os.path.normcase(str(directory))
        if identity in seen:
            continue
        seen.add(identity)
        try:
            exists = directory.exists()
            is_directory = directory.is_dir()
        except OSError as exc:
            failures.append({
                "code": "import-shadow-inspection-failed",
                "path": label(directory),
                "message": str(exc),
            })
            continue
        if not exists:
            continue
        if not is_directory:
            failures.append({
                "code": "untrusted-import-path",
                "path": label(directory),
                "message": (
                    "Release tooling refuses non-interpreter import archives "
                    "and files because their module contents cannot be trusted."
                ),
            })
            continue
        try:
            children = list(directory.iterdir())
        except OSError as exc:
            failures.append({
                "code": "import-shadow-inspection-failed",
                "path": label(directory),
                "message": str(exc),
            })
            continue
        for child in children:
            name = child.name.casefold()
            import_name: str | None = None
            try:
                if child.is_dir():
                    if name in _PROTECTED_IMPORT_NAMES:
                        for package_entry in child.iterdir():
                            if (
                                package_entry.is_file()
                                and _file_import_name(package_entry.name)
                                == "__init__"
                            ):
                                import_name = name
                                break
                elif child.is_file():
                    import_name = _file_import_name(child.name)
            except OSError as exc:
                failures.append({
                    "code": "import-shadow-inspection-failed",
                    "path": label(child),
                    "message": str(exc),
                })
                continue
            if import_name not in _PROTECTED_IMPORT_NAMES:
                continue
            failures.append({
                "code": "import-shadow-residue",
                "path": label(child),
                "message": (
                    f"Remove {child.name!r}; it can shadow the protected "
                    f"Python import {import_name!r} before release tooling runs."
                ),
            })
    return sorted(
        failures,
        key=lambda item: (
            item["path"].casefold(),
            item["code"],
            item["message"],
        ),
    )


_FAILURES = _compiled_python_failures() + _import_shadow_failures()
if _FAILURES:
    print(json.dumps({"ok": False, "failures": _FAILURES}, indent=2))
    raise SystemExit(2)

sys.path[:] = _ORIGINAL_SYS_PATH
