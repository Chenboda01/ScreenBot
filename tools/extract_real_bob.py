from pathlib import Path


ROOT = Path.home() / "ScreenBot"
SOURCE = ROOT / "ScreenBot.py"
TARGET = ROOT / "ui" / "robot.py"


def main():
    source = SOURCE.read_text()

    start_marker = "class RobotWidget(QWidget):"
    end_marker = "\n\nclass SettingsWindow(QWidget):"

    start = source.find(start_marker)
    end = source.find(end_marker)

    if start == -1:
        raise SystemExit("❌ Could not find RobotWidget.")

    if end == -1:
        raise SystemExit("❌ Could not find end of RobotWidget.")

    robot_class = source[start:end].rstrip() + "\n"

    header = """import math

from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import QWidget


"""

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(header + robot_class)

    patched = source[:start] + source[end + 2:]

    import_line = "from ui.robot import RobotWidget\n"

    if import_line not in patched:
        marker = "from bot.life import LifeEngine\n"

        if marker not in patched:
            raise SystemExit("❌ Could not find import insertion point.")

        patched = patched.replace(
            marker,
            marker + import_line,
            1,
        )

    SOURCE.write_text(patched)

    print("✅ Extracted the REAL RobotWidget to ui/robot.py")
    print("✅ ScreenBot.py now imports the exact same Bob")


if __name__ == "__main__":
    main()
