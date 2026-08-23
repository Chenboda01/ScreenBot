from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget


class WalkingHost(QWidget):
    def __init__(self, height=180):
        super().__init__()

        self.host_height = height

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setStyleSheet(
            "background: transparent;"
        )

    def fit_to_screen(self, screen):
        area = screen.availableGeometry()

        self.setGeometry(
            area.x(),
            area.bottom() - self.host_height + 1,
            area.width(),
            self.host_height,
        )

    def attach_bob(self, bob, x=20, y=10):
        bob.setParent(self)
        bob.move(x, y)
        bob.show()

    def detach_bob(self, bob):
        bob.setParent(None)
