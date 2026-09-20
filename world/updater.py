import hashlib
import hmac
import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests
from PyQt6.QtCore import QThread, pyqtSignal


UPDATE_MANIFEST_URL = (
    "https://chenboda01.github.io/ScreenBot/updates/latest.json"
)
RELEASES_DIRECTORY = (
    Path.home() / ".local" / "share" / "screenbot" / "releases"
)


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    version: str
    archive_url: str
    checksum_url: str


class UpdateCheckWorker(QThread):
    available = pyqtSignal(object)

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        release = fetch_latest_release()

        if release is not None and is_newer_version(
            release.version,
            self.current_version,
        ):
            self.available.emit(release)


class UpdateInstallWorker(QThread):
    progress = pyqtSignal(int, str)
    installed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, release):
        super().__init__()
        self.release = release

    def run(self):
        self.progress.emit(10, "Downloading verified update...")

        try:
            with tempfile.TemporaryDirectory() as directory:
                archive = download_verified_archive(
                    self.release,
                    Path(directory),
                    self.report_download_progress,
                )

                if archive is None:
                    self.failed.emit("The update download could not be verified.")
                    return

                self.progress.emit(70, "Verifying and installing update...")
                entrypoint = extract_verified_release(
                    archive,
                    RELEASES_DIRECTORY,
                    self.release.version,
                )
        except OSError as error:
            self.failed.emit(f"The update could not be installed: {error}")
            return

        if entrypoint is None:
            self.failed.emit("The downloaded update was not a valid ScreenBot release.")
            return

        self.progress.emit(100, "Restarting ScreenBot...")
        self.installed.emit(str(entrypoint))

    def report_download_progress(self, downloaded, total):
        if total <= 0:
            self.progress.emit(35, "Downloading update...")
            return

        percent = 10 + int(downloaded / total * 60)
        self.progress.emit(percent, "Downloading update...")


def parse_release(payload):
    if not isinstance(payload, dict):
        return None

    version = payload.get("version")

    if not is_safe_version(version):
        return None

    archive_url = payload.get("archive_url")
    checksum_url = payload.get("checksum_url")

    if not is_secure_url(archive_url) or not is_secure_url(checksum_url):
        return None

    return ReleaseInfo(
        version=version,
        archive_url=archive_url,
        checksum_url=checksum_url,
    )


def is_safe_version(version):
    if not isinstance(version, str) or not version:
        return False

    return all(
        character.isalnum() or character in {".", "_", "-"}
        for character in version
    )


def is_secure_url(url):
    return isinstance(url, str) and url.startswith("https://")


def fetch_latest_release():
    try:
        response = requests.get(UPDATE_MANIFEST_URL, timeout=10)
        response.raise_for_status()
        return parse_release(response.json())
    except (requests.RequestException, ValueError) as error:
        print("[UPDATE] Release check failed:", error)
        return None


def is_newer_version(candidate, current):
    candidate_parts = numeric_version_parts(candidate)
    current_parts = numeric_version_parts(current)

    if candidate_parts is None or current_parts is None:
        return False

    return candidate_parts > current_parts


def numeric_version_parts(version):
    normalized = version[1:] if version.startswith("v") else version
    parts = normalized.split(".")

    if not parts or not all(part.isdigit() for part in parts):
        return None

    return tuple(int(part) for part in parts)


def verify_checksum(archive, checksums, filename):
    expected = None

    for line in checksums.splitlines():
        parts = line.split()

        if len(parts) == 2 and parts[1].lstrip("*") == filename:
            expected = parts[0]
            break

    if expected is None or len(expected) != 64:
        return False

    actual = hashlib.sha256(archive).hexdigest()
    return hmac.compare_digest(actual, expected.lower())


def download_verified_archive(release, directory, progress=None):
    archive_name = f"screenbot-{release.version}.zip"

    try:
        checksums = requests.get(
            release.checksum_url,
            timeout=15,
        )
        checksums.raise_for_status()

        archive = requests.get(
            release.archive_url,
            stream=True,
            timeout=60,
        )
        archive.raise_for_status()
    except requests.RequestException as error:
        print("[UPDATE] Download failed:", error)
        return None

    total = int(archive.headers.get("content-length", 0))
    content = bytearray()

    for chunk in archive.iter_content(chunk_size=65536):
        if not chunk:
            continue

        content.extend(chunk)

        if progress is not None:
            progress(len(content), total)

    if not verify_checksum(
        bytes(content),
        checksums.text,
        archive_name,
    ):
        print("[UPDATE] Release checksum did not match.")
        return None

    directory.mkdir(parents=True, exist_ok=True)
    archive_path = directory / archive_name
    archive_path.write_bytes(content)
    return archive_path


def extract_verified_release(archive_path, releases_directory, version):
    if not is_safe_version(version):
        return None

    destination = releases_directory / version
    entrypoint = destination / "main.py"

    if entrypoint.exists():
        return entrypoint

    releases_directory.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(archive_path) as archive:
            if not archive_is_safe(archive):
                return None

            with tempfile.TemporaryDirectory(
                dir=releases_directory,
                prefix=".install-",
            ) as temporary_directory:
                temporary_root = Path(temporary_directory)
                archive.extractall(temporary_root)
                source = extracted_release_root(temporary_root)

                if source is None:
                    return None

                os.replace(source, destination)
    except (OSError, zipfile.BadZipFile) as error:
        print("[UPDATE] Installation failed:", error)
        return None

    if entrypoint.exists():
        return entrypoint

    shutil.rmtree(destination, ignore_errors=True)
    return None


def archive_is_safe(archive):
    for member in archive.infolist():
        path = Path(member.filename)

        if path.is_absolute() or ".." in path.parts:
            return False

        if stat.S_ISLNK(member.external_attr >> 16):
            return False

    return True


def extracted_release_root(temporary_root):
    children = list(temporary_root.iterdir())

    if len(children) != 1 or not children[0].is_dir():
        return None

    source = children[0]

    if not (source / "main.py").is_file():
        return None

    return source
