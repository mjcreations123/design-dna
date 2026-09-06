"""Real portable directory links for security tests; creation failure is a failure."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess


def make_directory_link(link: Path, target: Path, *, force_junction: bool = False) -> str:
    if link.exists() or link.is_symlink():
        raise AssertionError(f"Refusing to overwrite a directory-link fixture: {link}")
    if not target.is_dir():
        raise AssertionError(f"Directory-link fixture target is not a directory: {target}")
    if force_junction and os.name != "nt":
        raise AssertionError("Junction fixtures apply only to Windows")
    original_error = None
    if not force_junction:
        try:
            os.symlink(target, link, target_is_directory=True)
            if not link.is_symlink() or link.resolve() != target.resolve():
                raise AssertionError("The created fixture is not the exact requested directory symlink")
            return "symlink"
        except (OSError, NotImplementedError) as exc:
            original_error = exc
            if os.name != "nt":
                raise AssertionError(f"The required directory-symlink fixture could not be created: {exc}") from exc
    environment = dict(os.environ, DESIGN_DNA_TEST_LINK_PATH=str(link), DESIGN_DNA_TEST_TARGET_PATH=str(target))
    created = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "New-Item -ItemType Junction -Path $env:DESIGN_DNA_TEST_LINK_PATH -Target $env:DESIGN_DNA_TEST_TARGET_PATH"],
        env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if created.returncode:
        raise AssertionError(f"The required Windows junction fixture could not be created: {created.stderr}; symlink result: {original_error}")
    info = link.lstat()
    if getattr(info, "st_reparse_tag", 0) != 0xA0000003 or link.resolve() != target.resolve():
        raise AssertionError("The created fixture is not the exact requested Windows junction")
    return "junction"


def remove_directory_link(link: Path) -> None:
    """Remove only the link, never its target or an ordinary directory."""
    info = link.lstat()
    if stat.S_ISLNK(info.st_mode):
        link.unlink()
    elif os.name == "nt" and getattr(info, "st_reparse_tag", 0) == 0xA0000003:
        os.rmdir(link)
    else:
        raise AssertionError(f"Refusing to remove a fixture that is not a directory symlink/junction: {link}")
