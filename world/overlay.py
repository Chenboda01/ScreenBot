from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget


class DesktopStrip(QWidget):
    def __init__(self, height=180):
        super().__init__()

        self.strip_height = height

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

    def fit_to_screen(self, screen):
        area = screen.availableGeometry()

        self.setGeometry(
            area.x(),
            area.bottom() - self.strip_height + 1,
            area.width(),
            self.strip_height,
        )
