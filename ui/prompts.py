import re
import subprocess

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtDBus import QDBusConnection


NOTIFICATION_SERVICE = "org.freedesktop.Notifications"
NOTIFICATION_PATH = "/org/freedesktop/Notifications"
NOTIFICATION_INTERFACE = "org.freedesktop.Notifications"


def gvariant_string(text):
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


class ActionNotification(QObject):
    invoked = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.bus = QDBusConnection.sessionBus()
        self.notification_id = None
        self.resolved = False

        self.bus.connect(
            "",
            NOTIFICATION_PATH,
            NOTIFICATION_INTERFACE,
            "ActionInvoked",
            self.on_action_invoked,
        )

        self.bus.connect(
            "",
            NOTIFICATION_PATH,
            NOTIFICATION_INTERFACE,
            "NotificationClosed",
            self.on_closed,
        )

    def show(self, summary, body, actions):
        self.resolved = False
        self.notification_id = None

        actions_literal = "[" + ", ".join(
            f"{gvariant_string(key)}, {gvariant_string(label)}"
            for key, label in actions
        ) + "]"

        result = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                NOTIFICATION_SERVICE,
                "--object-path",
                NOTIFICATION_PATH,
                "--method",
                f"{NOTIFICATION_INTERFACE}.Notify",
                "ScreenBot",
                "0",
                "",
                summary,
                body,
                actions_literal,
                "{}",
                "0",
            ],
            capture_output=True,
            text=True,
        )

        match = re.search(
            r"uint32\s+(\d+)",
            result.stdout,
        )

        if match is None:
            print(
                "[NOTIFY] Notification failed:",
                result.stderr.strip()
                or result.stdout.strip(),
            )

            self.resolved = True
            self.closed.emit()
            return None

        self.notification_id = int(match.group(1))

        return self.notification_id

    def close(self):
        if self.notification_id is None:
            return

        subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                NOTIFICATION_SERVICE,
                "--object-path",
                NOTIFICATION_PATH,
                "--method",
                f"{NOTIFICATION_INTERFACE}.CloseNotification",
                str(self.notification_id),
            ],
            capture_output=True,
            text=True,
        )

        self.notification_id = None

    @pyqtSlot("uint", str)
    def on_action_invoked(self, notification_id, action_key):
        if self.resolved or notification_id != self.notification_id:
            return

        self.resolved = True
        self.invoked.emit(action_key)

    @pyqtSlot("uint", "uint")
    def on_closed(self, notification_id, reason):
        if self.resolved or notification_id != self.notification_id:
            return

        self.resolved = True
        self.closed.emit()


class ChoicePrompt(QObject):
    def __init__(self, parent=None):
        super().__init__()

        self.parent_widget = parent
        self.notification = ActionNotification()
        self.notification.invoked.connect(
            self.on_notification_invoked
        )

        self.dialog = None
        self.button_keys = {}
        self.result = None

    def ask(self, title, body, choices, default_key):
        self.result = None
        self.button_keys = {}

        self.notification.show(title, body, choices)

        dialog = QMessageBox(self.parent_widget)
        dialog.setWindowTitle(title)
        dialog.setText(body)

        for index, (key, label) in enumerate(choices):
            role = (
                QMessageBox.ButtonRole.AcceptRole
                if index == 0
                else QMessageBox.ButtonRole.RejectRole
            )

            self.button_keys[dialog.addButton(label, role)] = key

        self.dialog = dialog
        dialog.exec()

        if self.result is None:
            clicked = dialog.clickedButton()

            if clicked is not None:
                self.result = self.button_keys.get(clicked)

        if self.result is None:
            self.result = default_key

        self.dialog = None
        self.notification.close()

        return self.result

    def on_notification_invoked(self, action_key):
        self.finish(action_key)

    def finish(self, key):
        if self.result is not None:
            return

        self.result = key

        if self.dialog is not None:
            self.dialog.done(0)
