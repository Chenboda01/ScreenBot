import sys

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QLabel

from world.overlay import DesktopStrip


class WalkerTest:
    def __init__(self, app):
        self.app = app

        self.strip = DesktopStrip(height=180)

        screen = QApplication.primaryScreen()
        self.strip.fit_to_screen(screen)

        self.bot = QLabel("🤖", self.strip)
        self.bot.setFont(QFont("Arial", 58))
        self.bot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bot.setGeometry(20, 50, 100, 100)

        self.x = 20
        self.direction = 1

        self.timer = QTimer()
        self.timer.timeout.connect(self.walk)
        self.timer.start(20)

        self.strip.show()

    def walk(self):
        self.x += 4 * self.direction

        max_x = self.strip.width() - self.bot.width()

        if self.x >= max_x:
            self.x = max_x
            self.direction = -1

        elif self.x <= 0:
            self.x = 0
            self.direction = 1

        self.bot.move(self.x, 50)


def main():
    app = QApplication(sys.argv)

    test = WalkerTest(app)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
