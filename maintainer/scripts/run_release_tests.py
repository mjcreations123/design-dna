#!/usr/bin/env python3
"""Run every canonical release test with parseable verbose identities.

The stock ``python -m unittest -v`` runner enables descriptions, which can
place a skipped test's docstring between its identity and result.  Release
attestation needs the exact skipped test identity in the result stream.  The
release candidate has two executable test roots: maintainer verification and
the packaged runtime tests.  Each root keeps the ordinary ``unittest
discover`` semantics it has when run directly; the composite runner prevents a
same-named test module in one root from shadowing the other.
"""

from __future__ import annotations

# The release runner is an executable attestation boundary, not a convenience
# wrapper.  A ``sitecustomize`` module supplied through ``PYTHONPATH`` runs
# *before* ordinary script code and can replace ``unittest`` discovery.  There
# is no safe way for a Python script to undo that after it has happened, so the
# standalone runner refuses every launch that did not isolate the interpreter
# before startup hooks were considered.  Keep this check before the local
# cache preflight and before any import outside the interpreter's stdlib.
import sys as _startup_sys

_ISOLATED_BOOTSTRAP = (
    bool(_startup_sys.flags.isolated)
    and bool(_startup_sys.flags.no_site)
    and bool(_startup_sys.flags.dont_write_bytecode)
)
if __name__ == "__main__" and not _ISOLATED_BOOTSTRAP:
    _startup_sys.stdout.write(
        "{\"ok\": false, \"failures\": [{\"code\": "
        "\"release-test-runner-isolation-required\", \"message\": "
        "\"Launch with python -I -S -B so startup hooks and inherited "
        "Python paths cannot alter release discovery.\"}]}\n"
    )
    raise SystemExit(2)
del _startup_sys

_CACHE_PREFLIGHT_PATH = (
    __file__.replace("\\", "/").rsplit("/", 1)[0] + "/cache_preflight.py"
)
with open(_CACHE_PREFLIGHT_PATH, "rb") as _cache_preflight_stream:
    _CACHE_PREFLIGHT_SOURCE = _cache_preflight_stream.read()
exec(
    compile(_CACHE_PREFLIGHT_SOURCE, _CACHE_PREFLIGHT_PATH, "exec"),
    {
        "__file__": _CACHE_PREFLIGHT_PATH,
        "__name__": "_design_dna_cache_preflight",
    },
)
del _CACHE_PREFLIGHT_PATH, _CACHE_PREFLIGHT_SOURCE, _cache_preflight_stream

import os
import sys
import sysconfig
import time
import unittest
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path


def _is_within_interpreter_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _interpreter_owned_roots() -> tuple[Path, ...]:
    """Find only paths owned by the executing interpreter or its venv.

    ``-S`` deliberately suppresses normal site initialization.  Python 3.14
    retains venv prefixes during early path initialization, while older
    supported interpreters can expose the base prefix until ``site`` runs.
    Recover a real venv root only from the executable's adjacent
    ``pyvenv.cfg``; do not consult an environment variable or a caller path.
    """

    candidates = [Path(sys.prefix), Path(sys.base_prefix)]
    executable = Path(sys.executable)
    try:
        if not executable.is_absolute():
            executable = executable.absolute()
        if not executable.is_file():
            raise OSError("Python executable is not a regular file")
    except OSError as exc:
        raise RuntimeError(
            "The isolated release runner cannot resolve its Python executable."
        ) from exc
    for candidate in (executable.parent, executable.parent.parent):
        try:
            if (candidate / "pyvenv.cfg").is_file():
                candidates.append(candidate)
        except OSError as exc:
            raise RuntimeError(
                "The isolated release runner cannot inspect its virtual environment."
            ) from exc
    roots: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise RuntimeError(
                "The isolated release runner has an unreadable interpreter root."
            ) from exc
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _canonical_site_packages(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return existing interpreter-owned site-package directories only."""

    # When an executable belongs to a venv, do not silently widen its
    # dependency boundary to the base interpreter's global site-packages.
    # The pinned closure must be installed in that selected environment.
    venv_roots = tuple(
        root for root in roots if (root / "pyvenv.cfg").is_file()
    )
    dependency_roots = venv_roots or (Path(sys.prefix).resolve(),)
    candidates: list[Path] = []
    for key in ("purelib", "platlib"):
        value = sysconfig.get_path(key)
        if value:
            candidates.append(Path(value))
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for root in dependency_roots:
        candidates.extend((
            root / "Lib" / "site-packages",
            root / "lib" / version / "site-packages",
            root / "lib64" / version / "site-packages",
        ))
    approved: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            exists = resolved.is_dir()
        except OSError as exc:
            raise RuntimeError(
                "The isolated release runner cannot inspect a dependency path."
            ) from exc
        if not exists or not any(
            _is_within_interpreter_root(resolved, root)
            for root in dependency_roots
        ):
            continue
        if resolved not in approved:
            approved.append(resolved)
    return tuple(approved)


def _install_isolated_import_paths() -> None:
    """Restore only canonical local tooling and interpreter dependencies.

    This runs only after ``-I -S -B`` startup and after cache preflight.  The
    standard library remains first; local maintainer modules and pinned
    dependencies are added explicitly without processing ``.pth`` files,
    user-site paths, or ``sitecustomize``.
    """

    if not _ISOLATED_BOOTSTRAP:
        return
    if any(name in sys.modules for name in ("site", "sitecustomize", "usercustomize")):
        raise RuntimeError(
            "The isolated release runner detected site initialization."
        )
    roots = _interpreter_owned_roots()
    interpreter_paths: list[str] = []
    for entry in sys.path:
        if not entry:
            raise RuntimeError(
                "The isolated release runner received an empty import path."
            )
        try:
            resolved = Path(entry).resolve()
        except OSError as exc:
            raise RuntimeError(
                "The isolated release runner cannot resolve an interpreter path."
            ) from exc
        if not any(_is_within_interpreter_root(resolved, root) for root in roots):
            raise RuntimeError(
                "The isolated release runner received a non-canonical import path."
            )
        interpreter_paths.append(str(resolved))
    script_directory = Path(__file__).resolve().parent
    sys.path[:] = [
        *dict.fromkeys(interpreter_paths),
        str(script_directory),
        *(str(path) for path in _canonical_site_packages(roots)),
    ]
    sys.path_importer_cache.clear()


_install_isolated_import_paths()


TEST_PATTERN = "test_*.py"
TEST_ROOTS = (
    Path("maintainer") / "tests",
    Path("skills") / "design-dna" / "tests",
)


def _sanitize_child_python_environment() -> None:
    """Keep test-launched Python children off inherited startup controls."""

    for key in tuple(os.environ):
        if key.upper().startswith("PYTHON") or key.upper() in {
            "VIRTUAL_ENV",
            "VIRTUAL_ENV_PROMPT",
        }:
            os.environ.pop(key, None)


_sanitize_child_python_environment()

# ``-B`` only controls this interpreter.  Tests may launch Python subprocesses
# (for lifecycle, parser, or renderer coverage), so make the no-bytecode
# contract explicit in their inherited environment as well.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _is_within(path: Path, root: Path) -> bool:
    """Return whether a resolved module path belongs to one test root."""

    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _forget_modules_from(test_roots: tuple[Path, ...]) -> None:
    """Clear modules imported from an earlier bare-name discovery root.

    Both canonical test roots intentionally use the standard discovery command
    shape, which gives modules their bare filenames.  Some of those filenames
    overlap (for example ``test_font_audit``).  ``unittest`` rightfully rejects
    a later same-named file when the earlier module remains cached, so retain
    the already-discovered suite while removing only modules sourced from a
    release-test root before discovering the next one.  Test cases keep direct
    references to their classes, so this does not drop the first suite.
    """

    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        try:
            source = Path(filename)
        except (OSError, TypeError, ValueError):
            continue
        if any(_is_within(source, root) for root in test_roots):
            sys.modules.pop(name, None)


def release_test_roots(plugin_root: Path) -> tuple[Path, ...]:
    """Return the required executable roots after checking their existence."""

    roots = tuple(plugin_root / relative for relative in TEST_ROOTS)
    missing = [path for path in roots if not path.is_dir()]
    if missing:
        labels = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Required release test root is missing: {labels}")
    return roots


def _aggregate_counts(
    results: list[unittest.TestResult],
) -> tuple[int, dict[str, int], bool]:
    """Return the exact aggregate unittest counts and outcome."""

    counts = {
        "failures": sum(len(result.failures) for result in results),
        "errors": sum(len(result.errors) for result in results),
        "skipped": sum(len(result.skipped) for result in results),
        "expected failures": sum(
            len(result.expectedFailures) for result in results
        ),
        "unexpected successes": sum(
            len(result.unexpectedSuccesses) for result in results
        ),
    }
    tests_run = sum(result.testsRun for result in results)
    return tests_run, counts, all(result.wasSuccessful() for result in results)


def _write_aggregate_summary(
    results: list[unittest.TestResult],
    elapsed_seconds: float,
) -> bool:
    """Append one parseable whole-suite summary after root-local output."""

    tests_run, counts, successful = _aggregate_counts(results)
    stream = sys.stderr
    stream.write("\n" + unittest.runner.TextTestResult.separator2 + "\n")
    noun = "test" if tests_run == 1 else "tests"
    stream.write(f"Ran {tests_run} {noun} in {elapsed_seconds:.3f}s\n\n")
    stream.write("OK" if successful else "FAILED")
    rendered_counts = [
        f"{name}={value}"
        for name, value in counts.items()
        if value
    ]
    if rendered_counts:
        stream.write(" (" + ", ".join(rendered_counts) + ")")
    stream.write("\n")
    stream.flush()
    return successful


def run_release_suites(plugin_root: Path) -> bool:
    """Discover and run each root before exposing the next root's modules.

    The roots deliberately use bare module names to retain ordinary
    ``unittest discover -s <root>`` identities.  Discovering both suites
    before execution leaves the later root's module in ``sys.modules`` when
    the earlier suite reaches ``setUpModule``.  That can silently replace a
    fixture or hide an error.  Run each discovered suite immediately, then
    evict only release-test modules before discovering the next root.

    Root-local ``TextTestRunner`` output remains verbatim for diagnostic IDs.
    A final aggregate summary gives the attester one authoritative count and
    exit outcome across both isolated roots.
    """

    roots = release_test_roots(plugin_root)
    results: list[unittest.TestResult] = []
    started = time.monotonic()
    with _plugin_root_import_context(plugin_root):
        for root, relative in zip(roots, TEST_ROOTS, strict=True):
            _forget_modules_from(roots)
            sys.stderr.write(
                f"\n=== Design DNA release test root: {relative.as_posix()} ===\n"
            )
            sys.stderr.flush()
            suite = unittest.defaultTestLoader.discover(
                str(root),
                pattern=TEST_PATTERN,
            )
            results.append(
                unittest.TextTestRunner(
                    verbosity=2,
                    descriptions=False,
                ).run(suite)
            )
            _forget_modules_from(roots)
    return _write_aggregate_summary(results, time.monotonic() - started)


@contextmanager
def _plugin_root_import_context(plugin_root: Path) -> Iterator[None]:
    """Keep the package root importable for discovery and test execution."""

    entry = str(plugin_root.resolve())
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    try:
        yield
    finally:
        if added and entry in sys.path:
            sys.path.remove(entry)


def main() -> int:
    # Keep this authoritative boundary in main as well as the early
    # direct-script guard. A startup hook can import this file under another
    # module name and call main(); non-isolated code must not reach discovery
    # in that path. The external -I -S -B launch is the actual protection
    # before startup hooks run, not evidence against a compromised interpreter.
    if not _ISOLATED_BOOTSTRAP:
        sys.stdout.write(
            "{\"ok\": false, \"failures\": [{\"code\": "
            "\"release-test-runner-isolation-required\", \"message\": "
            "\"Launch with python -I -S -B so startup hooks and inherited "
            "Python paths cannot alter release discovery.\"}]}\n"
        )
        return 2
    plugin_root = Path(__file__).resolve().parents[2]
    return 0 if run_release_suites(plugin_root) else 1


if __name__ == "__main__":
    raise SystemExit(main())
