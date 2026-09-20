import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from PyQt6.QtCore import QCoreApplication, QEventLoop, QObject, QTimer, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage


PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SCREENSHOT_INTERFACE = "org.freedesktop.portal.Screenshot"
PORTAL_REQUEST_INTERFACE = "org.freedesktop.portal.Request"
PORTAL_REQUEST_ROOT = "/org/freedesktop/portal/desktop/request"
PORTAL_TIMEOUT_MS = 15000

_APPLICATION = None


def ensure_application():
    global _APPLICATION

    if QCoreApplication.instance() is None:
        _APPLICATION = QCoreApplication([])

    return _APPLICATION


class PortalScreenshotReceiver(QObject):
    def __init__(self, loop):
        super().__init__()

        self.loop = loop
        self.code = None
        self.results = {}

    @pyqtSlot("uint", "QVariantMap")
    def on_response(self, code, results):
        self.code = code
        self.results = dict(results)
        self.loop.quit()


@dataclass(frozen=True, slots=True)
class TextRegion:
    left: int
    top: int
    width: int
    height: int


class VisionEngine:
    def __init__(self):
        self.prepared_screenshot = None
        self.prepared_rect = None
        self.scan_image = None
        self.text_regions = ()

    def capture_screen(self):
        ensure_application()

        bus = QDBusConnection.sessionBus()

        if not bus.isConnected():
            print(
                "[VISION] No session bus, cannot capture."
            )

            return None

        token = f"screenbot{os.getpid()}t{time.monotonic_ns()}"

        sender = bus.baseService().lstrip(":").replace(
            ".",
            "_",
        )

        request_path = (
            f"{PORTAL_REQUEST_ROOT}/{sender}/{token}"
        )

        loop = QEventLoop()
        receiver = PortalScreenshotReceiver(loop)

        bus.connect(
            PORTAL_SERVICE,
            request_path,
            PORTAL_REQUEST_INTERFACE,
            "Response",
            receiver.on_response,
        )

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(PORTAL_TIMEOUT_MS)

        portal = QDBusInterface(
            PORTAL_SERVICE,
            PORTAL_PATH,
            PORTAL_SCREENSHOT_INTERFACE,
            bus,
        )

        reply = portal.call(
            "Screenshot",
            "",
            {
                "handle_token": token,
                "interactive": False,
            },
        )

        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            print(
                "[VISION] Portal screenshot failed:",
                reply.errorName(),
                reply.errorMessage(),
            )

            return None

        if receiver.code is None:
            loop.exec()

        if receiver.code is None:
            print(
                "[VISION] Portal screenshot timed out."
            )

            return None

        if receiver.code != 0:
            print(
                "[VISION] Portal refused screenshot, code",
                receiver.code,
            )

            return None

        uri = str(receiver.results.get("uri", ""))

        if not uri.startswith("file://"):
            print(
                "[VISION] Portal returned no image path."
            )

            return None

        source = Path(uri[len("file://"):])

        if not source.exists():
            print(
                "[VISION] Portal image is missing:",
                source,
            )

            return None

        tmp = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
        )

        tmp.close()

        path = Path(tmp.name)

        shutil.copyfile(source, path)
        source.unlink(missing_ok=True)

        return path

    def prepare_scan(self, image_path, own_rect=None):
        path = Path(image_path)

        if (
            self.prepared_screenshot == path
            and self.prepared_rect == own_rect
        ):
            return

        with Image.open(path) as image:
            self.scan_image = image.copy()

        if own_rect is not None:
            self.blank_region(self.scan_image, own_rect)

        self.prepared_screenshot = path
        self.prepared_rect = own_rect
        self.text_regions = self.detect_text_regions(
            self.scan_image
        )

    def blank_region(self, image, rect):
        x, y, width, height = rect

        left = max(0, int(x))
        top = max(0, int(y))
        right = min(image.width, left + max(1, int(width)))
        bottom = min(image.height, top + max(1, int(height)))

        if right <= left or bottom <= top:
            return

        draw = ImageDraw.Draw(image)
        draw.rectangle(
            [left, top, right - 1, bottom - 1],
            fill="white",
        )

    def crop_region(
        self,
        image_path,
        x,
        y,
        width,
        height,
    ):
        if (
            self.prepared_screenshot == Path(image_path)
            and self.scan_image is not None
        ):
            return self.crop_image(
                self.scan_image,
                x,
                y,
                width,
                height,
            )

        with Image.open(image_path) as image:
            return self.crop_image(
                image,
                x,
                y,
                width,
                height,
            )

    def crop_image(
        self,
        image,
        x,
        y,
        width,
        height,
    ):

        x = max(0, int(x))
        y = max(0, int(y))

        width = max(1, int(width))
        height = max(1, int(height))

        right = min(
            image.width,
            x + width,
        )

        bottom = min(
            image.height,
            y + height,
        )

        return image.crop(
            (
                x,
                y,
                right,
                bottom,
            )
        )

    def detect_text_regions(self, image):
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
        )

        tmp.close()

        path = Path(tmp.name)

        image.save(path)

        result = subprocess.run(
            [
                "tesseract",
                str(path),
                "stdout",
                "--psm",
                "11",
                "tsv",
            ],
            capture_output=True,
            text=True,
        )

        path.unlink()

        if result.returncode != 0:
            return ()

        regions = []

        for line in result.stdout.splitlines()[1:]:
            fields = line.split("\t", 11)

            if len(fields) != 12 or fields[0] != "5":
                continue

            if not any(
                char.isalnum()
                for char in fields[11]
            ):
                continue

            coordinates = fields[6:10]

            if not all(
                value.isdigit()
                for value in coordinates
            ):
                continue

            regions.append(
                TextRegion(
                    left=int(fields[6]),
                    top=int(fields[7]),
                    width=int(fields[8]),
                    height=int(fields[9]),
                )
            )

        return tuple(regions)

    def prepared_text_score(
        self,
        x,
        y,
        width,
        height,
    ):
        left = max(0, int(x))
        top = max(0, int(y))
        right = left + max(1, int(width))
        bottom = top + max(1, int(height))

        for region in self.text_regions:
            if (
                region.left < right
                and region.left + region.width > left
                and region.top < bottom
                and region.top + region.height > top
            ):
                return 1.0

        return 0.0

    def text_score(self, image):
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
        )

        tmp.close()

        path = Path(tmp.name)

        image.save(path)

        result = subprocess.run(
            [
                "tesseract",
                str(path),
                "stdout",
                "--psm",
                "6",
            ],
            capture_output=True,
            text=True,
        )

        path.unlink()

        if result.returncode != 0:
            return 0.0

        text = result.stdout.strip()

        if not text:
            return 0.0

        useful_chars = sum(
            char.isalnum()
            for char in text
        )

        return min(
            1.0,
            useful_chars / 80.0,
        )

    def visual_score(self, image):
        gray = image.convert("L")

        edges = gray.filter(
            ImageFilter.FIND_EDGES
        )

        pixels = list(
            edges.getdata()
        )

        if not pixels:
            return 0.0

        strong_edges = sum(
            value > 30
            for value in pixels
        )

        return min(
            1.0,
            strong_edges / len(pixels) * 5.0,
        )

    def score_region(
        self,
        image_path,
        x,
        y,
        width,
        height,
    ):
        region = self.crop_region(
            image_path,
            x,
            y,
            width,
            height,
        )

        if self.prepared_screenshot == Path(image_path):
            text = self.prepared_text_score(
                x,
                y,
                width,
                height,
            )

        else:
            text = self.text_score(region)
        visual = self.visual_score(region)

        score = (
            text * 0.70
            + visual * 0.30
        )

        return {
            "score": score,
            "text": text,
            "visual": visual,
        }
