import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ui.mini_bob import MiniBobWidget
from world.overlay import DesktopStrip


class RealBobWalker:
    def __init__(self):
        self.strip = DesktopStrip(height=180)

        screen = QApplication.primaryScreen()
        self.strip.fit_to_screen(screen)

        self.bot = MiniBobWidget(self.strip)
        self.bot.move(20, 10)
        self.bot.set_state("walking")
        self.bot.set_walking(True, 1)

        self.bot.clicked.connect(self.clicked_bob)

        self.x = 20
        self.direction = 1

        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.walk)
        self.move_timer.start(20)

        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.bot.tick)
        self.anim_timer.start(80)

        self.bot.show()
        self.strip.show()

    def clicked_bob(self):
        print("🤖 BOB CLICKED!")
        self.bot.set_state("happy")

    def walk(self):
        self.x += 4 * self.direction

        max_x = (
            self.strip.width()
            - self.bot.width()
        )

        if self.x >= max_x:
            self.x = max_x
            self.direction = -1
            self.bot.set_walking(True, -1)

        elif self.x <= 0:
            self.x = 0
            self.direction = 1
            self.bot.set_walking(True, 1)

        self.bot.move(
            self.x,
            10,
        )


def main():
    app = QApplication(sys.argv)

    walker = RealBobWalker()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
