import sys
import json
import math
import random
import time
import requests
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRectF, QPoint
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
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
)

from bot.chats import ChatStore, suggested_title
from bot.life import LifeEngine
from bot.brain import HybridBrain
from bot.memory import ConversationMemory
from world.control_panel import SHAPES as PANEL_SHAPES
from world.movement import MovementEngine


MODEL = "llama3.2:1b"

MEMORY_FILE = Path.home() / "screenbot_memory.json"
SETTINGS_FILE = Path.home() / "screenbot_settings.json"
CHATS_FILE = Path.home() / ".screenbot_chats.json"


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
    "background_mode": "On",
    "text_size": "Medium",
    "panel_color": "Blue",
    "bot_name": "Bob",
    "panel_shape": "Circle",
    "panel_auto_move": "On",
    "update_check_minutes": 5,
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


TEXT_SIZES = {
    "Small": 12,
    "Medium": 14,
    "Large": 17,
    "Extra Large": 20,
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

        except (OSError, ValueError) as error:
            print(
                "[CONFIG] Could not read",
                path.name,
                "-",
                error,
            )

    return data


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


class StreamWorker(QThread):
    chunk = pyqtSignal(str)
    done = pyqtSignal(str)

    def __init__(
        self,
        message,
        memory,
        settings,
        mode="chat",
        recent_conversation="",
    ):
        super().__init__()

        self.message = message
        self.memory = memory
        self.settings = settings
        self.mode = mode
        self.recent_conversation = recent_conversation

    def run(self):
        facts = "\n".join(
            f"- {x}"
            for x in self.memory.get("facts", [])
        )

        if not facts:
            facts = "- No saved facts yet."

        if self.mode == "autonomous":
            prompt = f"""
You are ScreenBot, a little AI creature who lives on the user's desktop.

You decided by yourself that you wanted to speak.
Nobody asked you a question.

Personality:
- curious
- playful
- friendly
- sometimes mischievous
- not hyper
- not a generic assistant

Current internal state:
Energy: {float(self.memory.get("energy", 90)):.0f}/100
Curiosity: {float(self.memory.get("curiosity", 25)):.0f}/100
Social: {float(self.memory.get("social", 60)):.0f}/100

Memories:
{facts}

Recent conversation:
{self.recent_conversation}

STRICT REALITY RULES:
- Never invent personal facts about the user.
- Never claim you watched, opened, saw, heard, visited,
  or did something unless the supplied memory or
  conversation says it actually happened.
- You may WANT to do something, but never pretend
  you already did it.
- If you do not know something, say you do not know.

Say ONE short natural thing to the user.
Do not explain why you decided to speak.
Talk like ScreenBot.
"""

            # Autonomous chatter stays FREE and LOCAL.
            brain_mode = "local"

        else:
            thinking = THINKING_TEXT.get(
                self.settings.get("thinking_level"),
                THINKING_TEXT["Medium"],
            )

            prompt = f"""
You are ScreenBot, a clever little desktop robot companion.

You are:
- friendly
- curious
- playful
- helpful
- concise
- not a generic customer-service assistant

Thinking style:
{thinking}

Memory:
{facts}

Recent conversation:
{self.recent_conversation}

STRICT MEMORY AND REALITY RULES:
- Never invent memories or personal facts.
- A personal fact is known only when it appears
  explicitly in Memory or Recent conversation.
- If the user asks for an unknown favorite game,
  food, color, hobby, etc., say you do not know yet.
- Never pretend you performed computer activities
  that are not in the supplied context.
- Interpret short replies such as yes, no, it,
  that, and why using the recent conversation.

User:
{self.message}
"""

            # Real conversations get Performance Mode.
            brain_mode = self.settings.get("_session_brain_mode", "pro")

        brain = HybridBrain()
        full = ""

        try:
            for piece in brain.stream(
                prompt,
                mode=brain_mode,
            ):
                if piece:
                    full += piece
                    self.chunk.emit(piece)

            print(
                "[BRAIN]",
                "⚡ PRO"
                if brain.last_mode == "pro"
                else "🏠 LOCAL",
            )

        except Exception as error:  # noqa: BROAD_EXCEPT_OK
            print(
                "[BRAIN] Complete brain failure:",
                error,
            )

            full = (
                "My brain is having trouble right now."
            )

            self.chunk.emit(full)

        self.done.emit(full.strip())


class TitleWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, message, settings):
        super().__init__()

        self.message = message
        self.settings = settings

    def run(self):
        prompt = (
            "Write a short title for this conversation.\n"
            "Rules:\n"
            "- at most 6 words\n"
            "- capitalize company names, product names, proper nouns,"
            " and acronyms, for example Google, Slides, iPhone, Python\n"
            "- use correct grammar and spelling\n"
            "- return only the title, with no quotes and no final period\n\n"
            f"First message:\n{self.message}\n"
        )

        brain = HybridBrain()
        mode = self.settings.get("_session_brain_mode", "local")
        title = ""

        try:
            for piece in brain.stream(prompt, mode=mode):
                title += piece

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            print("[TITLE] Brain title failed:", error)

        self.done.emit(title.strip())


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


class SettingsWindow(QWidget):
    saved = pyqtSignal(dict)
    check_updates_requested = pyqtSignal()

    def __init__(self, settings):
        super().__init__()

        self.setWindowTitle(
            "ScreenBot Settings"
        )

        self.setWindowFlags(Qt.WindowType.Window)

        self.setFixedSize(
            390,
            740,
        )

        form = QFormLayout(self)

        self.theme = QComboBox()
        self.theme.addItems(
            ["Dark", "Light"]
        )

        self.theme.setCurrentText(
            settings["theme"]
        )

        self.background = QComboBox()
        self.background.addItems(
            COLORS.keys()
        )

        self.background.setCurrentText(
            settings["background"]
        )

        self.text_color = QComboBox()
        self.text_color.addItems(
            ACCENTS.keys()
        )

        self.text_color.setCurrentText(
            settings["text_color"]
        )

        self.curious = QSpinBox()
        self.curious.setRange(1, 60)
        self.curious.setSuffix(" min")

        self.curious.setValue(
            int(
                settings["curious_after"]
            )
        )

        self.sleep = QSpinBox()
        self.sleep.setRange(1, 120)
        self.sleep.setSuffix(" min")

        self.sleep.setValue(
            int(
                settings["sleep_after"]
            )
        )

        self.memory = QComboBox()
        self.memory.addItems(
            MEMORY_LIMITS.keys()
        )

        self.memory.setCurrentText(
            settings["memory_level"]
        )

        self.thinking = QComboBox()
        self.thinking.addItems(
            THINKING_TEXT.keys()
        )

        self.thinking.setCurrentText(
            settings["thinking_level"]
        )

        self.background_mode = QComboBox()
        self.background_mode.addItems(
            ["On", "Off"]
        )

        self.background_mode.setCurrentText(
            settings.get(
                "background_mode",
                "On",
            )
        )

        self.text_size = QComboBox()
        self.text_size.addItems(
            TEXT_SIZES.keys()
        )

        self.text_size.setCurrentText(
            settings.get(
                "text_size",
                "Medium",
            )
        )

        self.panel_color = QComboBox()
        self.panel_color.addItems(
            ACCENTS.keys()
        )

        self.panel_color.setCurrentText(
            settings.get(
                "panel_color",
                "Blue",
            )
        )

        self.bot_name = QLineEdit(
            settings.get("bot_name", "Bob")
        )

        self.panel_shape = QComboBox()
        self.panel_shape.addItems(
            PANEL_SHAPES.keys()
        )

        self.panel_shape.setCurrentText(
            settings.get(
                "panel_shape",
                "Circle",
            )
        )

        self.panel_auto_move = QComboBox()
        self.panel_auto_move.addItems(
            ["On", "Off"]
        )

        self.panel_auto_move.setCurrentText(
            settings.get(
                "panel_auto_move",
                "On",
            )
        )

        self.update_check_minutes = QSpinBox()
        self.update_check_minutes.setRange(1, 60)
        self.update_check_minutes.setSuffix(" min")
        self.update_check_minutes.setValue(
            int(settings.get("update_check_minutes", 5))
        )

        form.addRow(
            "Theme:",
            self.theme,
        )

        form.addRow(
            "Background:",
            self.background,
        )

        form.addRow(
            "Text color:",
            self.text_color,
        )

        form.addRow(
            "Curious after:",
            self.curious,
        )

        form.addRow(
            "Sleep after:",
            self.sleep,
        )

        form.addRow(
            "Memory:",
            self.memory,
        )

        form.addRow(
            "Thinking:",
            self.thinking,
        )

        form.addRow(
            "Background mode:",
            self.background_mode,
        )

        form.addRow(
            "Text size:",
            self.text_size,
        )

        form.addRow(
            "Panel color:",
            self.panel_color,
        )

        form.addRow(
            "Name:",
            self.bot_name,
        )

        form.addRow(
            "Button shape:",
            self.panel_shape,
        )

        form.addRow(
            "Auto move:",
            self.panel_auto_move,
        )

        form.addRow(
            "Update checks:",
            self.update_check_minutes,
        )

        save_btn = QPushButton("SAVE")
        close_btn = QPushButton("CLOSE")

        save_btn.clicked.connect(
            self.save_settings
        )

        close_btn.clicked.connect(
            self.close
        )

        check_updates_btn = QPushButton("CHECK FOR UPDATES")
        check_updates_btn.clicked.connect(
            self.check_updates_requested.emit
        )

        form.addRow(save_btn)
        form.addRow(check_updates_btn)
        form.addRow(close_btn)

    def save_settings(self):
        if (
            self.update_check_minutes.value() < 3
            and not self.confirm_short_update_interval()
        ):
            return

        data = {
            "theme": self.theme.currentText(),
            "background": self.background.currentText(),
            "text_color": self.text_color.currentText(),
            "curious_after": self.curious.value(),
            "sleep_after": self.sleep.value(),
            "memory_level": self.memory.currentText(),
            "thinking_level": self.thinking.currentText(),
            "background_mode": self.background_mode.currentText(),
            "text_size": self.text_size.currentText(),
            "panel_color": self.panel_color.currentText(),
            "bot_name": self.bot_name.text().strip() or "Bob",
            "panel_shape": self.panel_shape.currentText(),
            "panel_auto_move": self.panel_auto_move.currentText(),
            "update_check_minutes": self.update_check_minutes.value(),
        }

        save_json(
            SETTINGS_FILE,
            data,
        )

        self.saved.emit(data)

        QMessageBox.information(
            self,
            "Saved",
            "Settings saved.",
        )

        self.close()

    def confirm_short_update_interval(self):
        subprocess.run(
            [
                "notify-send",
                "ScreenBot",
                "Checking for updates this often may use more CPU.",
            ],
            check=False,
        )

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Frequent update checks")
        dialog.setText(
            "Checking for updates in under three minutes may use more CPU."
        )
        yes_button = dialog.addButton(
            "Yes, I'm sure.",
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.addButton(
            "No, exit.",
            QMessageBox.ButtonRole.RejectRole,
        )
        yes_button.setEnabled(False)
        unlock_timer = QTimer(dialog)
        unlock_timer.setSingleShot(True)
        unlock_timer.timeout.connect(
            lambda: yes_button.setEnabled(True)
        )
        unlock_timer.start(1000)
        dialog.exec()
        return dialog.clickedButton() is yes_button


class ScreenBot(QWidget):
    def __init__(self):
        super().__init__()

        self.memory = load_json(
            MEMORY_FILE,
            DEFAULT_MEMORY,
        )

        self.settings = load_json(
            SETTINGS_FILE,
            DEFAULT_SETTINGS,
        )

        self.state = "idle"
        self.expanded = False
        self.worker = None
        self.settings_window = None
        self.current_reply = ""
        self.autonomous_message = False
        self.idle_seconds = 0
        self.loading_step = 0

        self.life = LifeEngine()
        self.conversation = ConversationMemory()
        self.movement = MovementEngine()
        self.walking = False

        self.setWindowTitle(
            "ScreenBot 10"
        )

        self.setWindowFlags(
            Qt.WindowType.Window
        )

        self.robot = RobotWidget()
        self.robot.setParent(self)

        self.robot.clicked.connect(
            self.toggle_mode
        )

        self.mood = QLabel(
            "IDLE",
            self,
        )

        self.mood.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.chat = QTextEdit(self)
        self.chat.setReadOnly(True)

        self.input = QLineEdit(self)

        self.input.setPlaceholderText(
            "Type your message..."
        )

        self.input.returnPressed.connect(
            self.send_message
        )

        self.send_btn = QPushButton(
            "SEND",
            self,
        )

        self.send_btn.clicked.connect(
            self.send_message
        )

        self.settings_btn = QPushButton(
            "SETTINGS",
            self,
        )

        self.settings_btn.clicked.connect(
            self.open_settings
        )

        self.sleep_btn = QPushButton(
            "SLEEP",
            self,
        )

        self.sleep_btn.clicked.connect(
            lambda: self.set_state("sleepy")
        )

        self.mini_btn = QPushButton(
            "MINI",
            self,
        )

        self.mini_btn.clicked.connect(
            self.show_mini
        )

        self.exit_btn = QPushButton(
            "X",
            self,
        )

        self.exit_btn.clicked.connect(
            self.close
        )

        self.loading = QLabel(
            "",
            self,
        )

        self.loading.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.chats = ChatStore(CHATS_FILE)
        self.title_worker = None

        self.new_chat_btn = QPushButton(
            "＋  New chat",
            self,
        )

        self.new_chat_btn.clicked.connect(
            self.start_new_chat
        )

        self.chat_search = QLineEdit(self)

        self.chat_search.setPlaceholderText(
            "Search chats"
        )

        self.chat_search.textChanged.connect(
            self.refresh_chat_list
        )

        self.chat_list = QListWidget(self)

        self.chat_list.itemClicked.connect(
            self.on_chat_clicked
        )

        self.chat_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.chat_list.customContextMenuRequested.connect(
            self.open_chat_menu_at
        )

        self.rename_btn = QPushButton(
            "⋯   Rename",
            self,
        )

        self.rename_btn.clicked.connect(
            lambda: self.open_chat_menu()
        )

        self.thinking_picker = QComboBox(self)

        self.thinking_picker.addItems(
            THINKING_TEXT.keys()
        )

        self.thinking_picker.setCurrentText(
            self.settings.get(
                "thinking_level",
                "Medium",
            )
        )

        self.thinking_picker.currentTextChanged.connect(
            self.thinking_changed
        )

        self.anim_timer = QTimer(self)

        self.anim_timer.timeout.connect(
            self.animate
        )

        self.anim_timer.start(80)

        self.life_timer = QTimer(self)

        self.life_timer.timeout.connect(
            self.life_loop
        )

        self.life_timer.start(1000)

        self.move_timer = QTimer(self)
        self.move_timer.timeout.connect(self.movement_loop)
        self.move_timer.start(30)

        self.apply_theme()
        self.show_mini()

    def apply_theme(self):
        bg = COLORS.get(
            self.settings["background"],
            "#020711",
        )

        accent = ACCENTS.get(
            self.settings["text_color"],
            "#00f7ff",
        )

        text_size = TEXT_SIZES.get(
            self.settings.get("text_size", "Medium"),
            TEXT_SIZES["Medium"],
        )

        if self.settings["theme"] == "Light":
            bg = "#f4f6ff"

        self.robot.set_accent(accent)

        self.setStyleSheet(
            f"""
            QWidget {{
                background:{bg};
                color:{accent};
                font-family:Arial;
                font-size:{text_size}px;
            }}

            QLineEdit, QTextEdit {{
                background:#071326;
                color:white;
                border:2px solid {accent};
                border-radius:12px;
                padding:8px;
            }}

            QListWidget, QComboBox {{
                background:#071326;
                color:white;
                border:2px solid {accent};
                border-radius:12px;
                padding:4px;
            }}

            QListWidget::item {{
                padding:6px;
            }}

            QListWidget::item:selected {{
                background:{accent};
                color:#020711;
            }}

            QPushButton {{
                background:#071326;
                color:{accent};
                border:2px solid {accent};
                border-radius:12px;
                padding:6px;
                font-weight:bold;
            }}

            QPushButton:hover {{
                background:{accent};
                color:#020711;
            }}
            """
        )

        self.mood.setStyleSheet(
            f"""
            font-size:{text_size + 4}px;
            font-weight:bold;
            color:{accent};
            """
        )

        self.loading.setStyleSheet(
            f"""
            font-size:{text_size}px;
            font-weight:bold;
            color:{accent};
            """
        )

    def show_mini(self):
        if getattr(self, "background_mode", False):
            return

        self.expanded = False

        self.setFixedSize(
            180,
            160,
        )

        self.robot.setGeometry(
            25,
            8,
            130,
            118,
        )

        self.mood.setGeometry(
            20,
            126,
            140,
            26,
        )

        for widget in [
            self.chat,
            self.input,
            self.send_btn,
            self.settings_btn,
            self.sleep_btn,
            self.mini_btn,
            self.exit_btn,
            self.loading,
            *self.expanded_only_widgets(),
        ]:
            widget.hide()

        self.robot.show()
        self.mood.show()

    def expanded_only_widgets(self):
        return [
            self.new_chat_btn,
            self.chat_search,
            self.chat_list,
            self.rename_btn,
            self.thinking_picker,
        ]

    def show_expanded(self):
        self.expanded = True

        self.setFixedSize(
            760,
            670,
        )

        self.exit_btn.setGeometry(
            713,
            12,
            35,
            30,
        )

        self.new_chat_btn.setGeometry(
            12,
            12,
            196,
            34,
        )

        self.chat_search.setGeometry(
            12,
            54,
            196,
            30,
        )

        self.chat_list.setGeometry(
            12,
            92,
            196,
            470,
        )

        self.rename_btn.setGeometry(
            12,
            570,
            196,
            30,
        )

        self.robot.setGeometry(
            395,
            35,
            190,
            150,
        )

        self.mood.setGeometry(
            380,
            188,
            220,
            28,
        )

        self.loading.setGeometry(
            380,
            218,
            220,
            24,
        )

        self.chat.setGeometry(
            245,
            255,
            490,
            265,
        )

        self.input.setGeometry(
            245,
            535,
            270,
            42,
        )

        self.thinking_picker.setGeometry(
            520,
            535,
            110,
            42,
        )

        self.send_btn.setGeometry(
            640,
            535,
            95,
            42,
        )

        self.settings_btn.setGeometry(
            245,
            600,
            150,
            36,
        )

        self.sleep_btn.setGeometry(
            412,
            600,
            150,
            36,
        )

        self.mini_btn.setGeometry(
            579,
            600,
            150,
            36,
        )

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
            *self.expanded_only_widgets(),
        ]:
            widget.show()

        self.refresh_chat_list()

        if not self.current_reply:
            self.load_active_conversation()
            self.render_active_chat()

        self.loading.setVisible(
            self.state == "thinking"
        )

        self.input.setFocus()

    def active_chat(self):
        return self.chats.active()

    def ensure_active_chat(self):
        chat = self.chats.active()

        if chat is None:
            chat = self.chats.new_chat()
            self.refresh_chat_list()

        return chat

    def start_new_chat(self):
        self.chats.new_chat()
        self.load_active_conversation()
        self.render_active_chat()
        self.refresh_chat_list()

        if self.expanded:
            self.input.setFocus()

    def on_chat_clicked(self, item):
        chat_id = item.data(
            Qt.ItemDataRole.UserRole
        )

        if self.chats.select(chat_id) is None:
            return

        self.load_active_conversation()
        self.render_active_chat()
        self.refresh_chat_list()

        if self.expanded:
            self.input.setFocus()

    def refresh_chat_list(self):
        self.chat_list.clear()

        for chat in self.chats.search(
            self.chat_search.text()
        ):
            item = QListWidgetItem(chat["title"])

            item.setData(
                Qt.ItemDataRole.UserRole,
                chat["id"],
            )

            self.chat_list.addItem(item)

            if chat["id"] == self.chats.active_id:
                self.chat_list.setCurrentItem(item)

    def open_chat_menu_at(self, position):
        item = self.chat_list.itemAt(position)

        if item is not None:
            self.open_chat_menu(item)

    def open_chat_menu(self, item=None):
        target = (
            item
            if isinstance(item, QListWidgetItem)
            else self.chat_list.currentItem()
        )

        if target is None:
            return

        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")

        chosen = menu.exec(
            self.rename_btn.mapToGlobal(
                QPoint(0, self.rename_btn.height())
            )
        )

        if chosen is None:
            return

        chat_id = target.data(
            Qt.ItemDataRole.UserRole
        )

        if chosen.text() == rename_action.text():
            self.rename_chat(chat_id)

        elif chosen.text() == delete_action.text():
            self.delete_chat(chat_id)

    def delete_chat(self, chat_id):
        chat = self.chats.get(chat_id)

        if chat is None:
            return

        answer = QMessageBox.question(
            self,
            "Delete chat",
            f"Delete \"{chat['title']}\"?",
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        if not self.chats.delete(chat_id):
            return

        self.load_active_conversation()
        self.render_active_chat()
        self.refresh_chat_list()

    def rename_chat(self, chat_id):
        chat = self.chats.get(chat_id)

        if chat is None:
            return

        title, accepted = QInputDialog.getText(
            self,
            "Rename chat",
            "Chat name:",
            text=chat["title"],
        )

        if not accepted:
            return

        self.chats.rename(chat_id, title)
        self.refresh_chat_list()

    def load_active_conversation(self):
        self.conversation = ConversationMemory()
        chat = self.chats.active()

        if chat is None:
            return

        for message in chat["messages"]:
            if message["role"] == "user":
                self.conversation.add_user(
                    message["text"]
                )
            else:
                self.conversation.add_screenbot(
                    message["text"]
                )

    def bot_name(self):
        return self.settings.get("bot_name", "Bob")

    def render_active_chat(self):
        self.chat.clear()
        chat = self.chats.active()

        if chat is None:
            return

        for message in chat["messages"]:
            speaker = (
                "You"
                if message["role"] == "user"
                else self.bot_name()
            )

            self.chat.append(
                f"<b>{speaker}:</b> {message['text']}"
            )

        self.chat.append("")

    def store_message(self, role, text):
        chat = self.ensure_active_chat()

        self.chats.append(chat["id"], role, text)
        self.refresh_chat_list()

        return chat

    def maybe_refine_title(self):
        chat = self.chats.active()

        if chat is None or chat["renamed"]:
            return

        if len(chat["messages"]) != 2:
            return

        first_user = ""

        for message in chat["messages"]:
            if message["role"] == "user":
                first_user = message["text"]
                break

        if not first_user:
            return

        chat_id = chat["id"]

        self.title_worker = TitleWorker(
            first_user,
            self.settings,
        )

        self.title_worker.done.connect(
            lambda title, target=chat_id: (
                self.apply_brain_title(target, title)
            )
        )

        self.title_worker.start()

    def apply_brain_title(self, chat_id, title):
        if self.chats.auto_title(chat_id, title) is None:
            return

        self.refresh_chat_list()

    def thinking_changed(self, level):
        if level == self.settings.get("thinking_level"):
            return

        self.settings["thinking_level"] = level

        save_json(
            SETTINGS_FILE,
            self.settings_for_disk(),
        )

    def settings_for_disk(self):
        return {
            "theme": self.settings["theme"],
            "background": self.settings["background"],
            "text_color": self.settings["text_color"],
            "curious_after": self.settings["curious_after"],
            "sleep_after": self.settings["sleep_after"],
            "memory_level": self.settings["memory_level"],
            "thinking_level": self.settings["thinking_level"],
            "background_mode": self.settings.get(
                "background_mode",
                "On",
            ),
            "text_size": self.settings.get(
                "text_size",
                "Medium",
            ),
            "panel_color": self.settings.get(
                "panel_color",
                "Blue",
            ),
            "bot_name": self.settings.get(
                "bot_name",
                "Bob",
            ),
            "panel_shape": self.settings.get(
                "panel_shape",
                "Circle",
            ),
            "panel_auto_move": self.settings.get(
                "panel_auto_move",
                "On",
            ),
            "update_check_minutes": self.settings.get(
                "update_check_minutes",
                5,
            ),
        }

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

        self.mood.setText(
            names.get(
                state,
                "IDLE",
            )
        )

        self.robot.set_state(state)

        self.loading.setVisible(
            self.expanded
            and state == "thinking"
        )

    def animate(self):
        self.robot.tick()

        if self.state == "thinking":
            self.loading_step = (
                self.loading_step + 1
            ) % 11

            self.loading.setText(
                "Thinking "
                + "█" * self.loading_step
                + "░" * (
                    10
                    - self.loading_step
                )
            )

    def life_loop(self):
        if self.state in {
            "thinking",
            "speaking",
        }:
            return

        self.idle_seconds += 1

        self.memory["energy"] = max(
            0,
            float(
                self.memory.get(
                    "energy",
                    90,
                )
            )
            - 0.01,
        )

        self.memory["curiosity"] = min(
            100,
            float(
                self.memory.get(
                    "curiosity",
                    25,
                )
            )
            + random.uniform(
                0.04,
                0.12,
            ),
        )

        action = self.life.tick(
            self.state,
            self.memory,
        )

        if action == "curious":
            self.set_state("curious")

        elif action == "happy":
            self.set_state("happy")

        elif action == "sleepy":
            self.set_state("sleepy")

        elif action == "look_around":
            self.set_state("curious")

        elif action == "speak":
            self.autonomous_speak()

        if (
            self.state == "happy"
            and self.idle_seconds >= 5
        ):
            self.set_state("idle")

        elif (
            self.state == "curious"
            and self.idle_seconds >= 8
        ):
            self.memory["curiosity"] = max(
                0,
                self.memory["curiosity"] - 30,
            )

            self.set_state("idle")

        elif self.state == "idle":
            curious_at = (
                int(
                    self.settings[
                        "curious_after"
                    ]
                )
                * 60
            )

            sleep_at = (
                int(
                    self.settings[
                        "sleep_after"
                    ]
                )
                * 60
            )

            if (
                self.idle_seconds
                >= sleep_at
            ):
                self.set_state("sleepy")

            elif (
                self.idle_seconds
                >= curious_at
                and self.memory[
                    "curiosity"
                ] > 60
            ):
                if random.random() < 0.04:
                    self.set_state(
                        "curious"
                    )

        if self.idle_seconds % 30 == 0:
            save_json(
                MEMORY_FILE,
                self.memory,
            )

    def movement_loop(self):
        if self.expanded or self.state in {"thinking", "speaking", "sleepy"}:
            return

        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry()

        if not self.walking:
            if True:
                local_x = self.x() - area.x()
                self.movement.choose_target(local_x, area.width(), self.width())
                self.walking = True
                self.set_state("curious")
            return

        local_x = self.x() - area.x()
        new_x, done = self.movement.step(local_x)
        self.move(area.x() + new_x, self.y())

        if done:
            self.walking = False
            self.set_state("idle")

    def open_settings(self):
        if (
            self.settings_window
            and self.settings_window.isVisible()
        ):
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return

        self.settings_window = SettingsWindow(
            self.settings
        )

        self.settings_window.saved.connect(
            self.settings_saved
        )

        if hasattr(self, "check_for_updates"):
            self.settings_window.check_updates_requested.connect(
                self.check_for_updates
            )

        self.settings_window.show()

    def settings_saved(self, settings):
        session_mode = self.settings.get(
            "_session_brain_mode"
        )

        self.settings = settings

        if session_mode is not None:
            self.settings["_session_brain_mode"] = (
                session_mode
            )

        self.thinking_picker.setCurrentText(
            self.settings.get(
                "thinking_level",
                "Medium",
            )
        )

        self.apply_theme()

    def learn_fact(self, text):
        lower = text.lower().strip()

        fact = None

        if lower.startswith(
            "remember that "
        ):
            fact = text[14:].strip()

        elif lower.startswith(
            "remember "
        ):
            fact = text[9:].strip()

        elif lower.startswith(
            "i like "
        ):
            fact = (
                "User likes "
                + text[7:].strip()
            )

        elif lower.startswith(
            "i prefer "
        ):
            fact = (
                "User prefers "
                + text[9:].strip()
            )

        if not fact:
            return False

        facts = self.memory.setdefault(
            "facts",
            [],
        )

        limit = MEMORY_LIMITS.get(
            self.settings["memory_level"],
            20,
        )

        if fact not in facts:
            facts.append(fact)

            self.memory["facts"] = (
                facts[-limit:]
            )

            save_json(
                MEMORY_FILE,
                self.memory,
            )

        return True

    def autonomous_speak(self):
        if (
            self.worker
            and self.worker.isRunning()
        ):
            return

        self.autonomous_message = True
        self.set_state("thinking")

        self.loading_step = 0
        self.current_reply = ""

        self.chat.append(
            f"<br><b>{self.bot_name()}:</b> "
        )

        self.worker = StreamWorker(
            "",
            self.memory,
            self.settings,
            mode="autonomous",
            recent_conversation=self.conversation.recent_text(),
        )

        self.worker.chunk.connect(
            self.receive_chunk
        )

        self.worker.done.connect(
            self.finish_reply
        )

        self.worker.start()

    def send_message(self):
        message = self.input.text().strip()

        if not message:
            return

        if (
            self.worker
            and self.worker.isRunning()
        ):
            return

        self.input.clear()

        self.chat.append(
            f"<b>You:</b> {message}"
        )

        self.conversation.add_user(message)

        chat = self.ensure_active_chat()
        self.chats.append(chat["id"], "user", message)

        if not chat["renamed"] and len(chat["messages"]) == 1:
            self.chats.auto_title(
                chat["id"],
                suggested_title(message),
            )

        self.refresh_chat_list()

        self.memory["conversation_count"] = (
            int(
                self.memory.get(
                    "conversation_count",
                    0,
                )
            )
            + 1
        )

        self.memory["last_chat"] = (
            time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        if self.learn_fact(message):
            self.chat.append(
                f"<b>{self.bot_name()}:</b> I will remember that."
            )

            self.store_message(
                "screenbot",
                "I will remember that.",
            )

            self.set_state("happy")
            return

        save_json(
            MEMORY_FILE,
            self.memory,
        )

        self.set_state("thinking")

        self.loading_step = 0
        self.current_reply = ""

        self.chat.append(
            f"<b>{self.bot_name()}:</b> "
        )

        self.worker = StreamWorker(
            message,
            self.memory,
            self.settings,
            mode="chat",
            recent_conversation=self.conversation.recent_text(),
        )

        self.worker.chunk.connect(
            self.receive_chunk
        )

        self.worker.done.connect(
            self.finish_reply
        )

        self.worker.start()

    def receive_chunk(self, chunk):
        if self.state == "thinking":
            self.set_state("speaking")

        self.current_reply += chunk

        cursor = self.chat.textCursor()

        cursor.movePosition(
            cursor.MoveOperation.End
        )

        cursor.insertText(chunk)

        self.chat.setTextCursor(cursor)

    def finish_reply(self, reply):
        autonomous = self.autonomous_message

        if autonomous and reply:
            subprocess.run(["notify-send", "ScreenBot", reply], check=False)
            self.autonomous_message = False
            self.show_mini()

        self.set_state("happy")

        if reply:
            self.conversation.add_screenbot(reply)

            if not autonomous:
                self.store_message(
                    "screenbot",
                    reply,
                )

                self.maybe_refine_title()

        self.current_reply = ""

        self.chat.append("")


def main():
    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(True)

    bot = ScreenBot()

    bot.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
