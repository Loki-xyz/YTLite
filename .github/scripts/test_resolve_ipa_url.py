#!/usr/bin/env python3
"""Tests for IPA share-URL resolution."""

from __future__ import annotations

import unittest

from resolve_ipa_url import ResolveError, resolve_ipa_url


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


if __name__ == "__main__":
    unittest.main()
