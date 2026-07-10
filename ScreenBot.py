import sys
import json
import math
import random
import time
import requests
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QFormLayout,
    QVBoxLayout,
    QMessageBox,
)

MODEL = "llama3.2:1b"
MEMORY_FILE = Path.home() / "screenbot_memory.json"
SETTINGS_FILE = Path.home() / "screenbot_settings.json"

DEFAULT_MEMORY = {
    "facts": [],
    "conversation_count": 0,
    "last_chat": "",
    "energy": 90.0,
    "curiosity": 25.0,
    "social": 60.0,
}

DEFAULT_SETTINGS = {
    "theme": "Dark",
    "background": "Black",
    "text_color": "Blue",
    "curious_after": 2,
    "sleep_after": 10,
    "memory_level": "Normal",
    "thinking_level": "Medium",
}

COLORS = {
    "Black": "#020711",
    "White": "#f4f6ff",
    "Red": "#220707",
    "Orange": "#261404",
}

ACCENTS = {
    "Red": "#ff4d6d",
    "Orange": "#ff9f1c",
    "Blue": "#00f7ff",
    "Green": "#00d99a",
}

MEMORY_LIMITS = {
    "Poor": 5,
    "Normal": 20,
    "Pro": 40,
    "Extra": 60,
    "Premium": 90,
    "Ultra-smart": 130,
    "Hyper-smart": 200,
}

THINKING_TEXT = {
    "Instant": "Answer quickly and briefly.",
    "Medium": "Think briefly, then answer clearly.",
    "High": "Think carefully before answering.",
    "Extra High": "Think deeply and give your best concise answer.",
    "Pro": "Reason carefully internally, then give a polished answer without showing hidden reasoning.",
}


def load_json(path, default):
    data = default.copy()
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass
    return data


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


class StreamWorker(QThread):
    chunk = pyqtSignal(str)
    done = pyqtSignal(str)

    def __init__(self, message, memory, settings):
        super().__init__()
        self.message = message
        self.memory = memory
        self.settings = settings

    def run(self):
        facts = "\n".join(f"- {x}" for x in self.memory.get("facts", []))
        prompt = f"""
You are ScreenBot, a calm desktop robot companion.
You are friendly, curious, helpful, and not hyper.
Keep replies short unless the user asks for detail.

Thinking style:
{THINKING_TEXT.get(self.settings.get("thinking_level"), THINKING_TEXT["Medium"])}

Memory:
{facts}

User:
{self.message}
"""
        full = ""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": MODEL, "prompt": prompt, "stream": True},
                stream=True,
                timeout=180,
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line.decode("utf-8"))
                piece = data.get("response", "")
                if piece:
                    full += piece
                    self.chunk.emit(piece)
                if data.get("done"):
                    break
        except Exception:
            full = "My local brain is offline. Make sure Ollama is running."
            self.chunk.emit(full)
        self.done.emit(full.strip())


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

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 + 5

        breath = math.sin(self.t / (18 if self.state == "sleepy" else 11)) * (
            3 if self.state == "sleepy" else 2
        )
        bounce_y = -math.sin(self.bounce / 12 * math.pi) * 9 if self.bounce else 0
        tilt = 5 if self.state == "thinking" else (-4 if self.state == "curious" else 0)

        p.translate(cx, cy + breath + bounce_y)
        p.rotate(tilt)
        p.translate(-cx, -cy)

        accent = QColor(self.accent)
        green = QColor("#00d99a")
        pink = QColor("#ff00ff")

        pulse = abs(math.sin(self.t / 5))
        antenna = QColor(self.accent)
        if self.state == "thinking":
            antenna = QColor(0, int(180 + 75 * pulse), 255)

        p.setPen(QPen(antenna, 3))
        p.drawLine(int(cx), int(cy - 55), int(cx), int(cy - 74))
        p.setBrush(QBrush(antenna))
        p.drawEllipse(QRectF(cx - 5, cy - 84, 10, 10))

        p.setPen(QPen(accent, 3))
        p.setBrush(QBrush(QColor("#050814")))
        p.drawRoundedRect(QRectF(cx - 55, cy - 50, 110, 80), 18, 18)

        p.setPen(QPen(QColor("#0d4d66"), 2))
        p.setBrush(QBrush(QColor("#071326")))
        p.drawRoundedRect(QRectF(cx - 43, cy - 38, 86, 54), 14, 14)

        if self.state == "sleepy":
            p.setPen(QPen(accent, 4))
            p.drawLine(int(cx - 25), int(cy - 14), int(cx - 10), int(cy - 14))
            p.drawLine(int(cx + 10), int(cy - 14), int(cx + 25), int(cy - 14))
        else:
            offset = 0
            if self.state == "curious":
                mouse = self.mapFromGlobal(self.cursor().pos())
                offset = max(-5, min(5, (mouse.x() - w / 2) / 20))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(accent))
            p.drawEllipse(QRectF(cx - 30 + offset, cy - 25, 13, 13))
            p.drawEllipse(QRectF(cx + 17 + offset, cy - 25, 13, 13))

        p.setPen(QPen(green, 3))
        if self.state == "thinking":
            p.drawEllipse(QRectF(cx - 7, cy - 1, 14, 14))
        elif self.state == "happy":
            p.drawArc(QRectF(cx - 15, cy - 4, 30, 22), 200 * 16, 140 * 16)
        else:
            p.drawLine(int(cx - 10), int(cy + 8), int(cx + 10), int(cy + 8))

        p.setPen(QPen(pink if self.state == "happy" else accent, 2))
        p.setBrush(QBrush(QColor("#06101f")))
        p.drawRoundedRect(QRectF(cx - 38, cy + 35, 76, 34), 11, 11)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(pink if self.state == "happy" else green))
        p.drawRoundedRect(QRectF(cx - 12, cy + 46, 24, 10), 5, 5)

        if self.state == "sleepy":
            p.resetTransform()
            p.setPen(QPen(accent, 2))
            p.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            p.drawText(w - 42, int(22 + math.sin(self.t / 8) * 5), "Z")


class SettingsWindow(QWidget):
    saved = pyqtSignal(dict)

    def __init__(self, settings):
        super().__init__()
        self.setWindowTitle("ScreenBot Settings")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.Tool)
        self.setFixedSize(390, 430)

        form = QFormLayout(self)

        self.theme = QComboBox()
        self.theme.addItems(["Dark", "Light"])
        self.theme.setCurrentText(settings["theme"])

        self.background = QComboBox()
        self.background.addItems(COLORS.keys())
        self.background.setCurrentText(settings["background"])

        self.text_color = QComboBox()
        self.text_color.addItems(ACCENTS.keys())
        self.text_color.setCurrentText(settings["text_color"])

        self.curious = QSpinBox()
        self.curious.setRange(1, 60)
        self.curious.setSuffix(" min")
        self.curious.setValue(int(settings["curious_after"]))

        self.sleep = QSpinBox()
        self.sleep.setRange(1, 120)
        self.sleep.setSuffix(" min")
        self.sleep.setValue(int(settings["sleep_after"]))

        self.memory = QComboBox()
        self.memory.addItems(MEMORY_LIMITS.keys())
        self.memory.setCurrentText(settings["memory_level"])

        self.thinking = QComboBox()
        self.thinking.addItems(THINKING_TEXT.keys())
        self.thinking.setCurrentText(settings["thinking_level"])

        form.addRow("Theme:", self.theme)
        form.addRow("Background:", self.background)
        form.addRow("Text color:", self.text_color)
        form.addRow("Curious after:", self.curious)
        form.addRow("Sleep after:", self.sleep)
        form.addRow("Memory:", self.memory)
        form.addRow("Thinking:", self.thinking)

        save_btn = QPushButton("SAVE")
        close_btn = QPushButton("CLOSE")
        save_btn.clicked.connect(self.save_settings)
        close_btn.clicked.connect(self.close)
        form.addRow(save_btn)
        form.addRow(close_btn)

    def save_settings(self):
        data = {
            "theme": self.theme.currentText(),
            "background": self.background.currentText(),
            "text_color": self.text_color.currentText(),
            "curious_after": self.curious.value(),
            "sleep_after": self.sleep.value(),
            "memory_level": self.memory.currentText(),
            "thinking_level": self.thinking.currentText(),
        }
        save_json(SETTINGS_FILE, data)
        self.saved.emit(data)
        QMessageBox.information(self, "Saved", "Settings saved.")
        self.close()


class ScreenBot(QWidget):
    def __init__(self):
        super().__init__()

        self.memory = load_json(MEMORY_FILE, DEFAULT_MEMORY)
        self.settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        self.state = "idle"
        self.expanded = False
        self.worker = None
        self.settings_window = None
        self.current_reply = ""
        self.idle_seconds = 0
        self.loading_step = 0

        self.setWindowTitle("ScreenBot v8.2")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)

        self.robot = RobotWidget()
        self.robot.setParent(self)
        self.robot.clicked.connect(self.toggle_mode)

        self.mood = QLabel("IDLE", self)
        self.mood.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.chat = QTextEdit(self)
        self.chat.setReadOnly(True)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Type your message...")
        self.input.returnPressed.connect(self.send_message)

        self.send_btn = QPushButton("SEND", self)
        self.send_btn.clicked.connect(self.send_message)

        self.settings_btn = QPushButton("SETTINGS", self)
        self.settings_btn.clicked.connect(self.open_settings)

        self.sleep_btn = QPushButton("SLEEP", self)
        self.sleep_btn.clicked.connect(lambda: self.set_state("sleepy"))

        self.mini_btn = QPushButton("MINI", self)
        self.mini_btn.clicked.connect(self.show_mini)

        self.exit_btn = QPushButton("X", self)
        self.exit_btn.clicked.connect(self.close)

        self.loading = QLabel("", self)
        self.loading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate)
        self.anim_timer.start(80)

        self.life_timer = QTimer(self)
        self.life_timer.timeout.connect(self.life_loop)
        self.life_timer.start(1000)

        self.apply_theme()
        self.show_mini()

    def apply_theme(self):
        bg = COLORS.get(self.settings["background"], "#020711")
        accent = ACCENTS.get(self.settings["text_color"], "#00f7ff")
        if self.settings["theme"] == "Light":
            bg = "#f4f6ff"

        self.robot.set_accent(accent)
        self.setStyleSheet(f"""
            QWidget {{ background:{bg}; color:{accent}; font-family:Arial; }}
            QLineEdit, QTextEdit {{
                background:#071326; color:white; border:2px solid {accent};
                border-radius:12px; padding:8px;
            }}
            QPushButton {{
                background:#071326; color:{accent}; border:2px solid {accent};
                border-radius:12px; padding:6px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{accent}; color:#020711; }}
        """)
        self.mood.setStyleSheet(f"font-size:18px;font-weight:bold;color:{accent};")
        self.loading.setStyleSheet(f"font-size:14px;font-weight:bold;color:{accent};")

    def show_mini(self):
        self.expanded = False
        self.setFixedSize(180, 160)
        self.robot.setGeometry(25, 8, 130, 118)
        self.mood.setGeometry(20, 126, 140, 26)

        for widget in [
            self.chat,
            self.input,
            self.send_btn,
            self.settings_btn,
            self.sleep_btn,
            self.mini_btn,
            self.exit_btn,
            self.loading,
        ]:
            widget.hide()

        self.robot.show()
        self.mood.show()

    def show_expanded(self):
        self.expanded = True
        self.setFixedSize(520, 670)

        self.exit_btn.setGeometry(470, 12, 35, 30)
        self.robot.setGeometry(165, 35, 190, 150)
        self.mood.setGeometry(150, 188, 220, 28)
        self.loading.setGeometry(150, 218, 220, 24)
        self.chat.setGeometry(25, 255, 470, 265)
        self.input.setGeometry(25, 535, 350, 42)
        self.send_btn.setGeometry(390, 535, 105, 42)
        self.settings_btn.setGeometry(25, 600, 145, 36)
        self.sleep_btn.setGeometry(188, 600, 145, 36)
        self.mini_btn.setGeometry(350, 600, 145, 36)

        for widget in [
            self.robot,
            self.mood,
            self.chat,
            self.input,
            self.send_btn,
            self.settings_btn,
            self.sleep_btn,
            self.mini_btn,
            self.exit_btn,
        ]:
            widget.show()

        self.loading.setVisible(self.state == "thinking")
        self.input.setFocus()

    def toggle_mode(self):
        if self.expanded:
            self.show_mini()
        else:
            self.show_expanded()
            if self.state == "sleepy":
                self.set_state("idle")

    def set_state(self, state):
        self.state = state
        self.idle_seconds = 0
        names = {
            "idle": "IDLE",
            "thinking": "THINKING",
            "speaking": "SPEAKING",
            "happy": "HAPPY",
            "sleepy": "SLEEP",
            "curious": "CURIOUS",
        }
        self.mood.setText(names.get(state, "IDLE"))
        self.robot.set_state(state)
        self.loading.setVisible(self.expanded and state == "thinking")

    def animate(self):
        self.robot.tick()
        if self.state == "thinking":
            self.loading_step = (self.loading_step + 1) % 11
            self.loading.setText(
                "Thinking " + "█" * self.loading_step + "░" * (10 - self.loading_step)
            )

    def life_loop(self):
        if self.state in {"thinking", "speaking"}:
            return

        self.idle_seconds += 1
        self.memory["energy"] = max(0, float(self.memory.get("energy", 90)) - 0.01)
        self.memory["curiosity"] = min(
            100, float(self.memory.get("curiosity", 25)) + random.uniform(0.04, 0.12)
        )

        if self.state == "happy" and self.idle_seconds >= 5:
            self.set_state("idle")
        elif self.state == "curious" and self.idle_seconds >= 8:
            self.memory["curiosity"] = max(0, self.memory["curiosity"] - 30)
            self.set_state("idle")
        elif self.state == "idle":
            curious_at = int(self.settings["curious_after"]) * 60
            sleep_at = int(self.settings["sleep_after"]) * 60

            if self.idle_seconds >= sleep_at:
                self.set_state("sleepy")
            elif self.idle_seconds >= curious_at and self.memory["curiosity"] > 60:
                if random.random() < 0.04:
                    self.set_state("curious")

        if self.idle_seconds % 30 == 0:
            save_json(MEMORY_FILE, self.memory)

    def open_settings(self):
        if self.settings_window and self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return

        self.settings_window = SettingsWindow(self.settings)
        self.settings_window.saved.connect(self.settings_saved)
        self.settings_window.show()

    def settings_saved(self, settings):
        self.settings = settings
        self.apply_theme()

    def learn_fact(self, text):
        lower = text.lower().strip()
        fact = None

        if lower.startswith("remember that "):
            fact = text[14:].strip()
        elif lower.startswith("remember "):
            fact = text[9:].strip()
        elif lower.startswith("i like "):
            fact = "User likes " + text[7:].strip()
        elif lower.startswith("i prefer "):
            fact = "User prefers " + text[9:].strip()

        if not fact:
            return False

        facts = self.memory.setdefault("facts", [])
        limit = MEMORY_LIMITS.get(self.settings["memory_level"], 20)
        if fact not in facts:
            facts.append(fact)
            self.memory["facts"] = facts[-limit:]
            save_json(MEMORY_FILE, self.memory)
        return True

    def send_message(self):
        message = self.input.text().strip()
        if not message or (self.worker and self.worker.isRunning()):
            return

        self.input.clear()
        self.chat.append(f"<b>You:</b> {message}")

        self.memory["conversation_count"] = (
            int(self.memory.get("conversation_count", 0)) + 1
        )
        self.memory["last_chat"] = time.strftime("%Y-%m-%d %H:%M:%S")

        if self.learn_fact(message):
            self.chat.append("<b>ScreenBot:</b> I will remember that.")
            self.set_state("happy")
            return

        save_json(MEMORY_FILE, self.memory)
        self.set_state("thinking")
        self.loading_step = 0
        self.current_reply = ""
        self.chat.append("<b>ScreenBot:</b> ")

        self.worker = StreamWorker(message, self.memory, self.settings)
        self.worker.chunk.connect(self.receive_chunk)
        self.worker.done.connect(self.finish_reply)
        self.worker.start()

    def receive_chunk(self, chunk):
        if self.state == "thinking":
            self.set_state("speaking")
        self.current_reply += chunk
        cursor = self.chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.chat.setTextCursor(cursor)

    def finish_reply(self, reply):
        self.set_state("happy")
        self.current_reply = ""
        self.chat.append("")


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    bot = ScreenBot()
    bot.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
