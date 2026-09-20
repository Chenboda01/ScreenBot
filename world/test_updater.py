import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from world.updater import (
    ReleaseInfo,
    extract_verified_release,
    parse_release,
    verify_checksum,
)


class ReleaseParsingTests(unittest.TestCase):
    def test_parse_release_requires_pages_manifest_assets(self):
        # Given: the GitHub Pages update manifest for a verified release.
        payload = {
            "version": "v1.2.3",
            "archive_url": "https://example.test/app.zip",
            "checksum_url": "https://example.test/sums",
        }

        # When: the release is parsed.
        release = parse_release(payload)

        # Then: the installer receives only the named release assets.
        self.assertEqual(
            ReleaseInfo(
                version="v1.2.3",
                archive_url="https://example.test/app.zip",
                checksum_url="https://example.test/sums",
            ),
            release,
        )

    def test_parse_release_rejects_an_incomplete_pages_manifest(self):
        # Given: a Pages update manifest without its checksum.
        payload = {
            "version": "v1.2.3",
            "archive_url": "https://example.test/app.zip",
        }

        # When: it is parsed.
        release = parse_release(payload)

        # Then: it cannot be installed.
        self.assertIsNone(release)


class ReleaseInstallationTests(unittest.TestCase):
    def test_verify_checksum_accepts_matching_release_archive(self):
        # Given: an archive and its published SHA-256 entry.
        archive = b"screenbot release"
        digest = hashlib.sha256(archive).hexdigest()

        # When: the checksum is verified.
        valid = verify_checksum(
            archive,
            f"{digest}  screenbot-v1.2.3.zip\n",
            "screenbot-v1.2.3.zip",
        )

        # Then: the matching archive is accepted.
        self.assertTrue(valid)

    def test_extract_verified_release_refuses_zip_path_escape(self):
        # Given: a valid ZIP that tries to write above its release folder.
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "release.zip"

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "nope")

            # When: installation extracts the archive.
            installed = extract_verified_release(
                archive_path,
                Path(directory) / "releases",
                "v1.2.3",
            )

            # Then: no release is installed outside its target directory.
            self.assertIsNone(installed)
            self.assertFalse((Path(directory) / "outside.txt").exists())
