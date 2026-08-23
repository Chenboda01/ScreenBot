import math

from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import QWidget


class RobotWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.state = "idle"
        self.t = 0
        self.bounce = 0
        self.accent = "#00f7ff"

    def set_state(self, state):
        self.state = state

        if state == "happy":
            self.bounce = 12

        self.update()

    def set_accent(self, color):
        self.accent = color
        self.update()

    def tick(self):
        self.t += 1

        if self.bounce > 0:
            self.bounce -= 1

        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        cx = w / 2
        cy = h / 2 + 5

        breath = math.sin(
            self.t / (18 if self.state == "sleepy" else 11)
        ) * (
            3 if self.state == "sleepy" else 2
        )

        bounce_y = (
            -math.sin(self.bounce / 12 * math.pi) * 9
            if self.bounce
            else 0
        )

        tilt = (
            5
            if self.state == "thinking"
            else (-4 if self.state == "curious" else 0)
        )

        p.translate(cx, cy + breath + bounce_y)
        p.rotate(tilt)
        p.translate(-cx, -cy)

        accent = QColor(self.accent)
        green = QColor("#00d99a")
        pink = QColor("#ff00ff")

        pulse = abs(math.sin(self.t / 5))

        antenna = QColor(self.accent)

        if self.state == "thinking":
            antenna = QColor(
                0,
                int(180 + 75 * pulse),
                255,
            )

        p.setPen(QPen(antenna, 3))
        p.drawLine(
            int(cx),
            int(cy - 55),
            int(cx),
            int(cy - 74),
        )

        p.setBrush(QBrush(antenna))
        p.drawEllipse(
            QRectF(
                cx - 5,
                cy - 84,
                10,
                10,
            )
        )

        p.setPen(QPen(accent, 3))
        p.setBrush(QBrush(QColor("#050814")))

        p.drawRoundedRect(
            QRectF(
                cx - 55,
                cy - 50,
                110,
                80,
            ),
            18,
            18,
        )

        p.setPen(QPen(QColor("#0d4d66"), 2))
        p.setBrush(QBrush(QColor("#071326")))

        p.drawRoundedRect(
            QRectF(
                cx - 43,
                cy - 38,
                86,
                54,
            ),
            14,
            14,
        )

        if self.state == "sleepy":
            p.setPen(QPen(accent, 4))

            p.drawLine(
                int(cx - 25),
                int(cy - 14),
                int(cx - 10),
                int(cy - 14),
            )

            p.drawLine(
                int(cx + 10),
                int(cy - 14),
                int(cx + 25),
                int(cy - 14),
            )

        else:
            offset = 0

            if self.state == "curious":
                mouse = self.mapFromGlobal(
                    self.cursor().pos()
                )

                offset = max(
                    -5,
                    min(
                        5,
                        (mouse.x() - w / 2) / 20,
                    ),
                )

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(accent))

            p.drawEllipse(
                QRectF(
                    cx - 30 + offset,
                    cy - 25,
                    13,
                    13,
                )
            )

            p.drawEllipse(
                QRectF(
                    cx + 17 + offset,
                    cy - 25,
                    13,
                    13,
                )
            )

        p.setPen(QPen(green, 3))

        if self.state == "thinking":
            p.drawEllipse(
                QRectF(
                    cx - 7,
                    cy - 1,
                    14,
                    14,
                )
            )

        elif self.state == "happy":
            p.drawArc(
                QRectF(
                    cx - 15,
                    cy - 4,
                    30,
                    22,
                ),
                200 * 16,
                140 * 16,
            )

        else:
            p.drawLine(
                int(cx - 10),
                int(cy + 8),
                int(cx + 10),
                int(cy + 8),
            )

        p.setPen(
            QPen(
                pink
                if self.state == "happy"
                else accent,
                2,
            )
        )

        p.setBrush(QBrush(QColor("#06101f")))

        p.drawRoundedRect(
            QRectF(
                cx - 38,
                cy + 35,
                76,
                34,
            ),
            11,
            11,
        )

        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(
            QBrush(
                pink
                if self.state == "happy"
                else green
            )
        )

        p.drawRoundedRect(
            QRectF(
                cx - 12,
                cy + 46,
                24,
                10,
            ),
            5,
            5,
        )

        if self.state == "sleepy":
            p.resetTransform()

            p.setPen(QPen(accent, 2))

            p.setFont(
                QFont(
                    "Arial",
                    16,
                    QFont.Weight.Bold,
                )
            )

            p.drawText(
                w - 42,
                int(
                    22
                    + math.sin(self.t / 8) * 5
                ),
                "Z",
            )
