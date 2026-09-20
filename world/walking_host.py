from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QRegion
from PyQt6.QtWidgets import QWidget


class WalkingHost(QWidget):
    def __init__(self):
        super().__init__()

        self.bob = None
        self.panel = None
        self.masked_region = None
        self.close_handler = None

        self.setWindowTitle("ScreenBot Walking Host")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
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
            area.y(),
            area.width(),
            area.height(),
        )

    def attach_bob(self, bob, x=20, y=10):
        self.bob = bob

        bob.setParent(self)
        bob.move(x, y)
        bob.show()

        self.update_mask()
        self.show()

    def attach_panel(self, panel):
        self.panel = panel

        panel.setParent(self)
        panel.show()

        self.update_mask()

    def move_bob(self, x, y=10):
        if self.bob is None:
            return

        self.bob.move(
            int(x),
            int(y),
        )

        self.update_mask()

    def move_panel(self, x, y):
        if self.panel is None:
            return

        self.panel.move(
            int(x),
            int(y),
        )

        self.update_mask()

    def widget_rects(self):
        rects = []

        for widget in (self.bob, self.panel):
            if widget is None or not widget.isVisible():
                continue

            rects.append(
                QRect(
                    widget.x(),
                    widget.y(),
                    widget.width(),
                    widget.height(),
                )
            )

        return rects

    def current_region(self):
        region = QRegion()

        for rect in self.widget_rects():
            region = region.united(
                QRegion(rect)
            )

        return region

    def update_mask(self):
        region = self.current_region()
        previous = self.masked_region

        if previous is None:
            touched = region
        else:
            touched = previous.united(region)

        if touched.isEmpty():
            self.clearMask()
            self.masked_region = None
            return

        self.setMask(touched)
        self.repaint(touched.boundingRect())
        self.setMask(region)

        self.masked_region = region

    def clear_stale_pixels(self):
        if self.masked_region is None:
            return

        region = self.masked_region

        self.setMask(region)
        self.repaint(region.boundingRect())
        self.clearMask()

        self.masked_region = None

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source
        )

        painter.fillRect(
            event.rect(),
            Qt.GlobalColor.transparent,
        )

    def detach_bob(self, bob):
        if self.bob is bob:
            self.bob = None

        bob.setParent(None)

        self.clear_stale_pixels()
        self.hide()

    def closeEvent(self, event):
        if self.close_handler is None:
            event.accept()
            return

        self.close_handler(event)
