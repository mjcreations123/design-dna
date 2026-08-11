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
import hashlib
import html.parser
import http.client
import ipaddress
import re
import socket
import ssl
import urllib.parse
from pathlib import Path

from common import (
    LOCAL_TOOL_DIRECTORY_NAMES,
    ToolFailure,
    absolute,
    emit,
    is_within,
    walk_files,
)


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
# Behavioral fixture inputs are inert test data. Some deliberately contain
# broken, fragment-only, or project-root-relative links so the eval runner can
# prove the matching failure mode. Package-wide link validation must not
# reinterpret those frozen site roots as links relative to the plugin root.
FIXTURE_INPUT_PREFIX = ("maintainer", "evals", "fixtures", "inputs")
TRUSTED_ONLINE_HOSTS = {
    "almanac.httparchive.org",
    "arxiv.org",
    "atlassian.design",
    "aux.engineering.ucsc.edu",
    "bolt.new",
    "carbondesignsystem.com",
    "community.vercel.com",
    "developer.mozilla.org",
    "designsystem.digital.gov",
    "digital-strategy.ec.europa.eu",
    "help.figma.com",
    "gov.uk",
    "guidance.publishing.service.gov.uk",
    "info.nrk.no",
    "newsroom.pinterest.com",
    "owasp.org",
    "pagesmith.ai",
    "raw.githubusercontent.com",
    "resources.relume.io",
    "storybook.js.org",
    "ui.shadcn.com",
    "web.dev",
    "www.framer.com",
    "www.ftc.gov",
    "www.gov.uk",
    "www.newwebsite.ai",
    "www.reddit.com",
    "www.w3.org",
    "www.youtube.com",
    "bradfrost.com",
}
REDIRECT_CODES = {301, 302, 303, 307, 308}


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


def normalized_hostname(hostname: str) -> str:
    try:
        return hostname.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise ValueError("hostname cannot be encoded as IDNA") from exc


def safe_url_label(url: str) -> str:
    """Return a credential- and query-free URL label for diagnostics."""
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        if not hostname:
            return "<redacted-url>"
        host = normalized_hostname(hostname)
        if ":" in host:
            host = f"[{host}]"
        try:
            port = parsed.port
        except ValueError:
            return f"{parsed.scheme.casefold()}://{host}/<invalid-port>"
        default_port = 443 if parsed.scheme.casefold() == "https" else 80
        authority = host if port in {None, default_port} else f"{host}:{port}"
        path = parsed.path or "/"
        if path != "/":
            digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:12]
            path = f"/<path-redacted:{digest}>"
        return urllib.parse.urlunsplit(
            (parsed.scheme.casefold(), authority, path, "", "")
        )
    except (TypeError, ValueError):
        return "<redacted-url>"


def resolve_external_target(
    url: str,
    allow_private_hosts: set[str],
    allowed_online_hosts: set[str],
) -> tuple[bool, str, str | None, int | None, tuple[str, ...]]:
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        return False, f"malformed URL: {exc}", None, None, ()
    if parsed.scheme not in {"http", "https"} or not hostname:
        return (
            False,
            "external URL needs http(s) and a hostname",
            None,
            None,
            (),
        )
    if parsed.username is not None or parsed.password is not None:
        return False, "credential-bearing URL refused", None, None, ()
    if parsed.query:
        # Evidence cards may point at one exact YouTube video. Admit only the
        # canonical public watch shape: one non-secret `v` parameter whose
        # value has the fixed YouTube video-ID shape. Every other query remains
        # rejected so the probe cannot leak tokens or arbitrary parameters.
        try:
            query = urllib.parse.parse_qsl(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
            )
        except ValueError:
            return False, "query-bearing URL refused", None, None, ()
        youtube_watch = (
            parsed.scheme == "https"
            and normalized_hostname(hostname) == "www.youtube.com"
            and parsed.path == "/watch"
            and len(query) == 1
            and query[0][0] == "v"
            and re.fullmatch(r"[A-Za-z0-9_-]{11}", query[0][1]) is not None
        )
        if not youtube_watch:
            return False, "query-bearing URL refused", None, None, ()
    if any(ord(character) < 32 or ord(character) == 127 for character in url):
        return False, "control character in URL refused", None, None, ()
    try:
        normalized = normalized_hostname(hostname)
    except ValueError as exc:
        return False, str(exc), None, None, ()
    private_allowlist = {
        normalized_hostname(host) for host in allow_private_hosts
    }
    online_allowlist = {
        normalized_hostname(host) for host in allowed_online_hosts
    }
    private_allowed = normalized in private_allowlist
    if not private_allowed and normalized not in online_allowlist:
        return (
            False,
            "online host is not allowlisted",
            normalized,
            port,
            (),
        )
    target_port = port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = {
            item[4][0].split("%", 1)[0]
            for item in socket.getaddrinfo(
                normalized,
                target_port,
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as exc:
        return False, f"DNS failure: {exc}", normalized, target_port, ()
    if not addresses:
        return (
            False,
            "hostname resolved to no addresses",
            normalized,
            target_port,
            (),
        )
    for address in addresses:
        try:
            value = ipaddress.ip_address(address)
        except ValueError:
            return (
                False,
                "hostname resolved to an invalid address",
                normalized,
                target_port,
                (),
            )
        if not private_allowed and not value.is_global:
            return (
                False,
                "hostname resolved to a non-public address",
                normalized,
                target_port,
                (),
            )
    return (
        True,
        "explicit private-host allowance" if private_allowed else "public",
        normalized,
        target_port,
        tuple(sorted(addresses)),
    )


def validate_external_target(
    url: str,
    allow_private_hosts: set[str],
    allowed_online_hosts: set[str] | None = None,
) -> tuple[bool, str]:
    safe, reason, _, _, _ = resolve_external_target(
        url,
        allow_private_hosts,
        allowed_online_hosts or TRUSTED_ONLINE_HOSTS,
    )
    return safe, reason


def pinned_head(
    url: str,
    *,
    hostname: str,
    port: int,
    addresses: tuple[str, ...],
    timeout: float,
) -> tuple[int, str | None]:
    """Issue HEAD to one prevalidated address without a second DNS lookup."""
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(
        parsed.path or "/",
        safe="/:@!$&'()*+,;=-._~%",
    )
    if parsed.query:
        # `resolve_external_target` has already restricted this to one safe,
        # canonical YouTube video ID. Preserve it so the probe checks the
        # cited video rather than the generic /watch endpoint.
        path += "?" + parsed.query
    failures: list[str] = []
    for address in addresses:
        raw_socket: socket.socket | None = None
        transport: socket.socket | ssl.SSLSocket | None = None
        try:
            raw_socket = socket.create_connection((address, port), timeout)
            raw_socket.settimeout(timeout)
            if parsed.scheme == "https":
                transport = ssl.create_default_context().wrap_socket(
                    raw_socket,
                    server_hostname=hostname,
                )
            else:
                transport = raw_socket
            default_port = 443 if parsed.scheme == "https" else 80
            authority = (
                hostname if port == default_port else f"{hostname}:{port}"
            )
            request = (
                f"HEAD {path} HTTP/1.1\r\n"
                f"Host: {authority}\r\n"
                "User-Agent: design-dna-maintainer/3 link-check\r\n"
                "Accept: */*\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            transport.sendall(request)
            response = http.client.HTTPResponse(transport)
            response.begin()
            location = response.getheader("Location")
            return response.status, location
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            failures.append(type(exc).__name__)
        finally:
            if transport is not None:
                transport.close()
            elif raw_socket is not None:
                raw_socket.close()
    detail = ", ".join(sorted(set(failures))) or "connection failed"
    raise OSError(f"all pinned connection attempts failed ({detail})")


def external_status(
    url: str,
    timeout: float,
    allow_private_hosts: set[str] | None = None,
    allowed_online_hosts: set[str] | None = None,
) -> tuple[bool, str]:
    """Probe with pinned-address HEAD; validate every redirect before following."""
    allow_private_hosts = allow_private_hosts or set()
    allowed_online_hosts = allowed_online_hosts or TRUSTED_ONLINE_HOSTS
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        safe, reason, hostname, port, addresses = resolve_external_target(
            current,
            allow_private_hosts,
            allowed_online_hosts,
        )
        if not safe:
            return False, reason
        assert hostname is not None
        assert port is not None
        try:
            status, location = pinned_head(
                current,
                hostname=hostname,
                port=port,
                addresses=addresses,
                timeout=timeout,
            )
            if status in REDIRECT_CODES:
                if not location:
                    return False, f"{status} without Location"
                current = urllib.parse.urljoin(current, location)
                continue
            return 200 <= status < 400, str(status)
        except (OSError, ValueError) as exc:
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
    allowed_online_hosts: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    external_seen: dict[str, tuple[bool, str]] = {}
    allow_private_hosts = allow_private_hosts or set()
    allowed_online_hosts = allowed_online_hosts or TRUSTED_ONLINE_HOSTS
    sources = []
    for path in walk_files(
        root,
        ignored_directory_names=LOCAL_TOOL_DIRECTORY_NAMES,
    ):
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        relative_parts = path.relative_to(root).parts
        if (
            len(relative_parts) >= len(FIXTURE_INPUT_PREFIX)
            and tuple(part.casefold() for part in relative_parts[
                : len(FIXTURE_INPUT_PREFIX)
            ])
            == FIXTURE_INPUT_PREFIX
        ):
            continue
        sources.append(path)
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
                    label = safe_url_label(base)
                    if label not in external_seen:
                        external_seen[label] = external_status(
                            base,
                            timeout,
                            allow_private_hosts,
                            allowed_online_hosts,
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
    parser.add_argument(
        "--allow-online-host",
        action="append",
        default=[],
        help=(
            "Add an exact public hostname to the built-in evidence-source "
            "allowlist; repeatable."
        ),
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
            allowed_online_hosts=(
                TRUSTED_ONLINE_HOSTS | set(args.allow_online_host)
            ),
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
