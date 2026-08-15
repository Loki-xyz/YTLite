#!/usr/bin/env python3
"""Resolve share-page IPA URLs to a direct download URL."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

FILEBIN_BIN_RE = re.compile(r"^https?://(?:www\.)?filebin\.net/([^/]+)/?$")


class ResolveError(Exception):
    """The URL cannot be turned into a downloadable IPA."""


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "YTLite-CI",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload: Any = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ResolveError(f"Failed to read Filebin bin metadata from {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResolveError(f"Unexpected Filebin response from {url}")
    return payload


def _filebin_filename(files: list[dict[str, Any]]) -> str:
    named = [item for item in files if isinstance(item.get("filename"), str)]
    ipas = [
        item
        for item in named
        if item["filename"].lower().endswith(".ipa")
    ]
    chosen = ipas or named
    if not chosen:
        raise ResolveError(
            "Filebin bin has no files. Upload the IPA to the bin, then rerun "
            "with the bin URL or a direct file URL like "
            "https://filebin.net/<bin>/<file.ipa>."
        )
    chosen.sort(key=lambda item: int(item.get("bytes") or 0), reverse=True)
    return str(chosen[0]["filename"])


def _resolve_filebin(url: str, fetch_json: Callable[[str], dict[str, Any]]) -> str:
    match = FILEBIN_BIN_RE.match(url)
    if match is None:
        return url
    data = fetch_json(url.rstrip("/"))
    files = data.get("files") or []
    if not isinstance(files, list):
        files = []
    filename = _filebin_filename(files)
    return f"{url.rstrip('/')}/{urllib.parse.quote(filename)}"


def _resolve_dropbox(url: str) -> str:
    if "dl=0" in url:
        return url.replace("dl=0", "dl=1")
    if "dl=1" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}dl=1"


def resolve_ipa_url(
    url: str,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> str:
    cleaned = url.strip()
    if not cleaned:
        raise ResolveError("IPA URL is empty.")
    if FILEBIN_BIN_RE.match(cleaned):
        return _resolve_filebin(cleaned, fetch_json or _fetch_json)
    if "dropbox.com" in cleaned:
        return _resolve_dropbox(cleaned)
    return cleaned.rstrip("/") if cleaned.endswith("/") else cleaned


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": "YTLite-CI"})


def _copy_response(response: Any, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        shutil.copyfileobj(response, out)


def download_to(url: str, dest: str | Path) -> None:
    """Download url to dest, retrying once after Filebin's verification page."""
    dest_path = Path(dest)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    try:
        with opener.open(_request(url), timeout=60) as response:
            if response.headers.get_content_type() != "text/html":
                _copy_response(response, dest_path)
                return
            response.read()
        with opener.open(_request(url), timeout=300) as response:
            _copy_response(response, dest_path)
    except urllib.error.URLError as exc:
        raise ResolveError(f"Failed to download IPA from {url}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve and download an IPA share URL.")
    parser.add_argument("url")
    parser.add_argument("-o", "--output", help="Download the resolved URL to this path.")
    args = parser.parse_args(argv)
    try:
        resolved = resolve_ipa_url(args.url)
        if args.output:
            download_to(resolved, args.output)
        else:
            print(resolved)
    except ResolveError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
