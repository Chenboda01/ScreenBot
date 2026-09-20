from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QMenu, QWidget


PANEL_ACCENT = "#00f7ff"
DRAG_THRESHOLD = 6

SHAPES = {
    "Circle": (46, 46),
    "Square": (46, 46),
    "Rectangle": (72, 40),
    "Triangle": (54, 46),
}

DEFAULT_SHAPE = "Circle"


class ControlPanel(QWidget):
    sleep_requested = pyqtSignal()
    idle_requested = pyqtSignal()
    expand_requested = pyqtSignal()
    geometry_changed = pyqtSignal()
    reshaped = pyqtSignal()
    moved = pyqtSignal()

    def __init__(self, name="Bob"):
        super().__init__()

        self.name = name
        self.accent = PANEL_ACCENT
        self.shape = DEFAULT_SHAPE

        self.dragging = False
        self.press_pos = QPoint()
        self.press_origin = QPoint()

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.setToolTip(name)

        width, height = SHAPES[DEFAULT_SHAPE]

        self.setFixedSize(width, height)

    def set_name(self, name):
        self.name = name
        self.setToolTip(name)

    def apply_accent(self, color):
        self.accent = color
        self.update()

    def apply_shape(self, shape):
        if shape not in SHAPES:
            shape = DEFAULT_SHAPE

        self.shape = shape

        width, height = SHAPES[shape]

        self.setFixedSize(width, height)
        self.update()
        self.geometry_changed.emit()
        self.reshaped.emit()

    def button_rect(self):
        return self.rect().adjusted(1, 1, -1, -1)

    def triangle_polygon(self, rect):
        polygon = QPolygon()

        polygon.append(
            QPoint(rect.center().x(), rect.top())
        )

        polygon.append(
            QPoint(rect.right(), rect.bottom())
        )

        polygon.append(
            QPoint(rect.left(), rect.bottom())
        )

        return polygon

    def shape_renderer(self, painter):
        renderers = {
            "Circle": painter.drawEllipse,
            "Square": painter.drawRect,
            "Rectangle": painter.drawRect,
            "Triangle": lambda rect: painter.drawPolygon(
                self.triangle_polygon(rect)
            ),
        }

        return renderers.get(
            self.shape,
            painter.drawRect,
        )

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        rect = self.button_rect()
        render_shape = self.shape_renderer(painter)
        glow = QColor(self.accent)
        glow.setAlpha(55)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(glow, 7))
        render_shape(rect)

        painter.setBrush(
            QBrush(QColor(2, 7, 17, 230))
        )
        painter.setPen(QPen(QColor("#75fbff"), 1))
        render_shape(rect.adjusted(2, 2, -2, -2))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(self.accent), 2))
        render_shape(rect)

        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)

        painter.setFont(font)
        painter.setPen(QPen(QColor("#d8feff")))

        text_rect = (
            rect.adjusted(0, 8, 0, 0)
            if self.shape == "Triangle"
            else rect
        )

        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter,
            "•••",
        )

        painter.setBrush(QBrush(QColor(self.accent)))
        painter.setPen(Qt.PenStyle.NoPen)

        for offset in (-7, 0, 7):
            painter.drawEllipse(
                rect.center().x() + offset - 1,
                rect.top() + 5,
                3,
                3,
            )

    def start_drag(self, global_pos):
        self.dragging = False
        self.press_pos = global_pos
        self.press_origin = self.pos()

    def drag_to(self, global_pos):
        delta = global_pos - self.press_pos

        if (
            not self.dragging
            and delta.manhattanLength() <= DRAG_THRESHOLD
        ):
            return

        self.dragging = True

        target = self.press_origin + delta
        parent = self.parentWidget()

        if parent is not None:
            target.setX(
                max(
                    0,
                    min(
                        target.x(),
                        parent.width() - self.width(),
                    ),
                )
            )

            target.setY(
                max(
                    0,
                    min(
                        target.y(),
                        parent.height() - self.height(),
                    ),
                )
            )

        self.move(target)
        self.geometry_changed.emit()

    def end_drag(self):
        if not self.dragging:
            return False

        self.dragging = False
        self.moved.emit()

        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_drag(
                event.globalPosition().toPoint()
            )

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.drag_to(
                event.globalPosition().toPoint()
            )

    def mouseReleaseEvent(self, event):
        if not self.end_drag():
            self.open_menu()

    def open_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#020711; color:#d8feff;"
            " border:2px solid #00f7ff; border-radius:10px;"
            " padding:8px; font-weight:bold; }"
            "QMenu::item { background:#071326; border:1px solid #0d4d66;"
            " border-radius:6px; margin:3px 0; padding:8px 24px 8px 10px; }"
            "QMenu::item:selected { background:#00f7ff; color:#020711;"
            " border-color:#d8feff; }"
            "QMenu::item:disabled { background:transparent; color:#00f7ff;"
            " border:0; padding:4px 4px 8px 4px; }"
            "QMenu::separator { height:1px; background:#0d4d66; margin:5px 0; }"
        )

        title = menu.addAction(f"{self.name.upper()} CONTROL CENTER")
        title.setEnabled(False)

        menu.addSeparator()

        sleep_action = menu.addAction("SLEEP MODE")
        idle_action = menu.addAction("IDLE MODE")
        big_action = menu.addAction("EXPAND SCREENBOT")

        chosen = menu.exec(
            self.mapToGlobal(
                QPoint(0, self.height())
            )
        )

        if chosen is None:
            return

        if chosen.text() == sleep_action.text():
            self.sleep_requested.emit()

        elif chosen.text() == idle_action.text():
            self.idle_requested.emit()

        elif chosen.text() == big_action.text():
            self.expand_requested.emit()
