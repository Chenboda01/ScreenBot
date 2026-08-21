from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QLabel

from ui.robot import RobotWidget


class MiniBobWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedSize(180, 160)

        # IMPORTANT:
        # Bob's container itself is transparent.
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setStyleSheet(
            "background: transparent;"
        )

        self.robot = RobotWidget()
        self.robot.setParent(self)
        self.robot.setGeometry(25, 4, 130, 122)

        self.robot.setStyleSheet(
            "background: transparent;"
        )

        self.mood = QLabel("IDLE", self)
        self.mood.setGeometry(15, 126, 150, 28)

        self.mood.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.mood.setStyleSheet(
            """
            QLabel {
                background: transparent;
                color: #00f7ff;
                font-family: Arial;
                font-size: 18px;
                font-weight: bold;
            }
            """
        )

        self.robot.clicked.connect(
            self.clicked.emit
        )

    def set_state(self, state):
        names = {
            "idle": "IDLE",
            "thinking": "THINKING",
            "speaking": "SPEAKING",
            "happy": "HAPPY",
            "sleepy": "SLEEP",
            "curious": "CURIOUS",
            "walking": "WALKING",
        }

        self.mood.setText(
            names.get(state, "IDLE")
        )

        if state == "walking":
            self.robot.set_state("curious")
        else:
            self.robot.set_state(state)

    def set_accent(self, color):
        self.robot.set_accent(color)

        self.mood.setStyleSheet(
            f"""
            QLabel {{
                background: transparent;
                color: {color};
                font-family: Arial;
                font-size: 18px;
                font-weight: bold;
            }}
            """
        )

    def set_walking(self, walking, direction=1):
        self.robot.set_walking(
            walking,
            direction,
        )

        if walking:
            self.mood.setText("WALKING")

    def tick(self):
        self.robot.tick()

    def mousePressEvent(self, event):
        self.clicked.emit()
