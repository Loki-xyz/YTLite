#!/usr/bin/env python3
"""Tests for IPA share-URL resolution."""

from __future__ import annotations

import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from resolve_ipa_url import ResolveError, download_to, resolve_ipa_url


class ResolveIpaUrlTests(unittest.TestCase):
    def test_filebin_bin_url_picks_ipa(self) -> None:
        resolved = resolve_ipa_url(
            "https://filebin.net/vwgp9zhzvch1kg3p",
            fetch_json=lambda _url: {
                "files": [
                    {"filename": "notes.txt", "bytes": 10},
                    {"filename": "YouTube.ipa", "bytes": 99},
                ]
            },
        )
        self.assertEqual(
            resolved, "https://filebin.net/vwgp9zhzvch1kg3p/YouTube.ipa"
        )

    def test_filebin_bin_url_encodes_spaces_in_filename(self) -> None:
        resolved = resolve_ipa_url(
            "https://filebin.net/abc123",
            fetch_json=lambda _url: {
                "files": [{"filename": "YouTube Plus.ipa", "bytes": 1}]
            },
        )
        self.assertEqual(resolved, "https://filebin.net/abc123/YouTube%20Plus.ipa")

    def test_filebin_bin_url_strips_trailing_slash(self) -> None:
        resolved = resolve_ipa_url(
            "https://filebin.net/abc123/",
            fetch_json=lambda _url: {
                "files": [{"filename": "app.ipa", "bytes": 1}]
            },
        )
        self.assertEqual(resolved, "https://filebin.net/abc123/app.ipa")

    def test_filebin_empty_bin_raises(self) -> None:
        with self.assertRaises(ResolveError) as ctx:
            resolve_ipa_url(
                "https://filebin.net/emptybin",
                fetch_json=lambda _url: {"files": None},
            )
        self.assertIn("no files", str(ctx.exception).lower())

    def test_filebin_direct_file_url_unchanged(self) -> None:
        url = "https://filebin.net/abc123/YouTube.ipa"
        self.assertEqual(resolve_ipa_url(url), url)

    def test_dropbox_share_link_forces_direct_download(self) -> None:
        self.assertEqual(
            resolve_ipa_url("https://www.dropbox.com/s/abc/YouTube.ipa?dl=0"),
            "https://www.dropbox.com/s/abc/YouTube.ipa?dl=1",
        )

    def test_dropbox_link_without_dl_appends_flag(self) -> None:
        self.assertEqual(
            resolve_ipa_url("https://www.dropbox.com/scl/fi/abc/YouTube.ipa"),
            "https://www.dropbox.com/scl/fi/abc/YouTube.ipa?dl=1",
        )

    def test_direct_url_passthrough(self) -> None:
        url = "https://example.com/files/YouTube.ipa"
        self.assertEqual(resolve_ipa_url(url), url)


class _FilebinInterstitialHandler(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self) -> None:
        type(self).hits += 1
        cookie = self.headers.get("Cookie", "")
        if "verified=" in cookie:
            body = b"PK\x03\x04ipa-bytes"
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = b"<!doctype html><title>Please read</title>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Set-Cookie", "verified=2024-05-24; Path=/")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class DownloadIpaTests(unittest.TestCase):
    def test_retries_after_filebin_verification_page(self) -> None:
        _FilebinInterstitialHandler.hits = 0
        server = HTTPServer(("127.0.0.1", 0), _FilebinInterstitialHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/bin/youtube.ipa"
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "youtube.ipa"
                download_to(url, dest)
                self.assertEqual(dest.read_bytes(), b"PK\x03\x04ipa-bytes")
            self.assertGreaterEqual(_FilebinInterstitialHandler.hits, 2)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
