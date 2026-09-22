from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QWidget


class DestinationScene(QWidget):
    visibility_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.destination_name = "Home"
        self.setFixedSize(230, 150)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.transition = QPropertyAnimation(self.opacity, b"opacity", self)
        self.transition.setDuration(240)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.finished.connect(self.finish_exit)

    def show_destination(self, name, x, y):
        self.destination_name = name
        self.move(x, y)
        self.transition.stop()
        self.opacity.setOpacity(0.0)
        self.show()
        self.transition.setStartValue(0.0)
        self.transition.setEndValue(1.0)
        self.transition.start()
        self.visibility_changed.emit()

    def clear_destination(self):
        if not self.isVisible():
            return

        self.transition.stop()
        self.transition.setStartValue(self.opacity.opacity())
        self.transition.setEndValue(0.0)
        self.transition.start()

    def finish_exit(self):
        if self.opacity.opacity() != 0.0:
            return

        self.hide()
        self.visibility_changed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111a2a"))
        painter.drawRoundedRect(4, 22, 222, 120, 22, 22)
        painter.setBrush(QColor("#1c2c3d"))
        painter.drawRoundedRect(11, 29, 208, 106, 18, 18)

        renderers = {
            "Home": self.paint_home,
            "Grocery Store": self.paint_grocery_store,
            "Desk": self.paint_desk,
            "Park": self.paint_park,
        }
        renderers.get(self.destination_name, self.paint_home)(painter)

        painter.setPen(QPen(QColor("#dbeafe"), 1))
        painter.drawText(
            self.rect().adjusted(0, 2, 0, 0),
            Qt.AlignmentFlag.AlignHCenter,
            self.destination_name,
        )

    def paint_home(self, painter):
        painter.setBrush(QColor("#f0b36b"))
        painter.drawRoundedRect(78, 64, 76, 57, 6, 6)
        painter.setBrush(QColor("#d96f57"))
        painter.drawPolygon(
            QPolygon(
                [QPoint(72, 67), QPoint(116, 37), QPoint(160, 67)]
            )
        )
        painter.setBrush(QColor("#704a3b"))
        painter.drawRoundedRect(108, 91, 16, 30, 3, 3)
        painter.setBrush(QColor("#bfe7f7"))
        painter.drawRoundedRect(87, 79, 14, 15, 2, 2)
        painter.drawRoundedRect(131, 79, 14, 15, 2, 2)
        self.paint_path(painter, QColor("#e9d0a8"), 104, 121, 24, 18)

    def paint_grocery_store(self, painter):
        painter.setBrush(QColor("#f7e7b5"))
        painter.drawRoundedRect(52, 60, 126, 61, 6, 6)
        painter.setBrush(QColor("#e85d50"))
        painter.drawRoundedRect(46, 50, 138, 18, 5, 5)
        painter.setPen(QPen(QColor("#fff6de"), 2))
        painter.drawText(78, 64, "FRESH MART")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#87c77b"))
        painter.drawEllipse(62, 93, 16, 16)
        painter.setBrush(QColor("#f3ba54"))
        painter.drawEllipse(87, 91, 17, 17)
        painter.setBrush(QColor("#f06d57"))
        painter.drawEllipse(112, 94, 15, 15)
        painter.setBrush(QColor("#7bb8d6"))
        painter.drawRoundedRect(139, 82, 25, 35, 4, 4)

    def paint_desk(self, painter):
        painter.setBrush(QColor("#be8157"))
        painter.drawRoundedRect(54, 91, 124, 16, 4, 4)
        painter.drawRect(65, 105, 9, 20)
        painter.drawRect(158, 105, 9, 20)
        painter.setBrush(QColor("#8bb8d9"))
        painter.drawRoundedRect(88, 50, 56, 42, 5, 5)
        painter.setBrush(QColor("#263545"))
        painter.drawRoundedRect(94, 56, 44, 28, 3, 3)
        painter.setBrush(QColor("#d6e7f2"))
        painter.drawRect(113, 92, 7, 12)
        painter.setBrush(QColor("#90c878"))
        painter.drawEllipse(66, 63, 22, 28)
        painter.setBrush(QColor("#efcf90"))
        painter.drawRoundedRect(148, 76, 18, 15, 3, 3)

    def paint_park(self, painter):
        painter.setBrush(QColor("#69b867"))
        painter.drawEllipse(34, 45, 54, 60)
        painter.drawEllipse(145, 42, 61, 66)
        painter.setBrush(QColor("#8c6044"))
        painter.drawRoundedRect(58, 87, 8, 34, 3, 3)
        painter.drawRoundedRect(170, 88, 8, 33, 3, 3)
        painter.setBrush(QColor("#d9bd7e"))
        painter.drawRoundedRect(86, 101, 58, 10, 4, 4)
        painter.setBrush(QColor("#765447"))
        painter.drawRect(91, 111, 7, 14)
        painter.drawRect(132, 111, 7, 14)
        self.paint_path(painter, QColor("#d9c797"), 105, 121, 21, 18)

    def paint_path(self, painter, color, x, y, width, height):
        painter.setBrush(color)
        painter.drawRoundedRect(x, y, width, height, 7, 7)
