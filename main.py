from bot.brain import HybridBrain
import os
import random
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QProcess, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)

from ScreenBot import (
    ACCENTS,
    SETTINGS_FILE,
    ScreenBot,
    load_json,
)
from ui.prompts import ChoicePrompt
from world.control_panel import ControlPanel
from world.movement import MovementEngine
from world.parking import ParkingEngine
from world.vision import VisionEngine
from world.walking_host import WalkingHost
from world.updater import UpdateCheckWorker, UpdateInstallWorker


TERRITORY_FILE = Path.home() / ".screenbot_territory.json"
SHOW_REQUEST_FILE = Path.home() / ".screenbot_show_request"
SHOW_REQUEST_MAX_AGE = 60.0

PRO_INITIAL_SCAN_RANGE = (2, 4)
PRO_AWARENESS_SCAN_RANGE = (3, 5)
LOCAL_INITIAL_SCAN_RANGE = (8, 18)
LOCAL_AWARENESS_SCAN_RANGE = (10, 25)


def scan_delay_range(brain_mode, initial):
    if brain_mode == "pro":
        if initial:
            return PRO_INITIAL_SCAN_RANGE

        return PRO_AWARENESS_SCAN_RANGE

    if initial:
        return LOCAL_INITIAL_SCAN_RANGE

    return LOCAL_AWARENESS_SCAN_RANGE


def internet_available():
    try:
        connection = socket.create_connection(
            ("1.1.1.1", 443),
            timeout=1.5,
        )
        connection.close()
        return True
    except OSError:
        return False


BOB_PROCESS_PATTERNS = (
    "/home/boda/ScreenBot/main.py",
    "/home/boda/ScreenBot/ScreenBot.py",
)


def bob_process_pids():
    own_pid = os.getpid()
    pids = set()

    for pattern in BOB_PROCESS_PATTERNS:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
        )

        for token in result.stdout.split():
            if token.isdigit():
                pid = int(token)

                if pid != own_pid:
                    pids.add(pid)

    return pids


def another_bob_is_running():
    return bool(bob_process_pids())


def pid_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    stat_path = Path("/proc") / str(pid) / "stat"

    try:
        content = stat_path.read_text()
    except OSError:
        return True

    parts = content.split(") ", 1)

    if len(parts) < 2:
        return True

    return not parts[1].startswith("Z")


def clean_up_old_bobs(app, report, pids=None):
    if pids is None:
        pids = bob_process_pids()

    pids = set(pids)

    if not pids:
        report(100, "No old Bobs found.")
        return

    report(10, f"Sending shutdown to {len(pids)} old Bob(s)...")

    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue

    deadline = time.monotonic() + 5.0

    while time.monotonic() < deadline:
        alive = [
            pid
            for pid in pids
            if pid_is_alive(pid)
        ]

        if not alive:
            report(75, "Old Bobs are shutting down...")
            break

        elapsed = (
            5.0
            - (deadline - time.monotonic())
        )

        report(
            int(10 + elapsed / 5.0 * 60),
            "Waiting for old Bobs to exit...",
        )

        app.processEvents()
        time.sleep(0.1)

    survivors = [
        pid
        for pid in pids
        if pid_is_alive(pid)
    ]

    if survivors:
        report(85, "Force-stopping stubborn Bobs...")
        app.processEvents()

        for pid in sorted(survivors):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                continue

        time.sleep(0.5)
        app.processEvents()

    remaining = [
        pid
        for pid in pids
        if pid_is_alive(pid)
    ]

    if remaining:
        report(100, f"{len(remaining)} Bob(s) survived cleanup.")
    else:
        report(100, "All old Bobs are gone. 🤖💀")


class ParkingWorker(QThread):
    finished_scan = pyqtSignal(object)

    def __init__(
        self,
        territory_x,
        territory_y,
        territory_width,
        territory_height,
        current_x,
        current_y,
        own_rect,
        panel_rect,
        panel_size,
    ):
        super().__init__()

        self.territory_x = territory_x
        self.territory_y = territory_y
        self.territory_width = territory_width
        self.territory_height = territory_height
        self.current_x = current_x
        self.current_y = current_y
        self.own_rect = own_rect
        self.panel_rect = panel_rect
        self.panel_size = panel_size

    def find_panel_spot(self, vision, screenshot, decision):
        panel_width, panel_height = self.panel_size

        parking = ParkingEngine(
            vision=vision,
            bot_width=panel_width,
            bot_height=panel_height,
            step=90,
            max_score=0.22,
            max_travel=700,
            padding=20,
        )

        exclude_rect = None
        destination = decision.get("destination")

        if destination is not None:
            exclude_rect = (
                int(destination["x"]) - 30,
                int(destination["y"]) - 30,
                240,
                220,
            )

        panel_decision = parking.plan_parking(
            screenshot=screenshot,
            territory_x=self.territory_x,
            territory_y=self.territory_y,
            territory_width=self.territory_width,
            territory_height=self.territory_height,
            current_x=self.panel_rect[0],
            current_y=self.panel_rect[1],
            own_rect=self.own_rect,
            exclude_rect=exclude_rect,
        )

        return panel_decision.get("destination")

    def run(self):
        try:
            vision = VisionEngine()

            parking = ParkingEngine(
                vision=vision,
                bot_width=180,
                bot_height=160,
                step=90,
                max_score=0.22,
                max_travel=700,
                padding=30,
            )

            screenshot = vision.capture_screen()

            if screenshot is None:
                self.finished_scan.emit(None)
                return

            decision = parking.plan_parking(
                screenshot=screenshot,
                territory_x=self.territory_x,
                territory_y=self.territory_y,
                territory_width=self.territory_width,
                territory_height=self.territory_height,
                current_x=self.current_x,
                current_y=self.current_y,
                own_rect=self.own_rect,
            )

            if decision is not None:
                decision["panel"] = self.find_panel_spot(
                    vision,
                    screenshot,
                    decision,
                )

            self.finished_scan.emit(decision)

        except Exception as error:
            print("[SMART PARKING ERROR]", error)
            self.finished_scan.emit(None)


class UpdateProgressWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScreenBot Update")
        self.setFixedSize(460, 150)
        self.setStyleSheet(
            "QWidget { background:#020711; color:#00f7ff; }"
            "QLabel { font-size:16px; font-weight:bold; }"
            "QProgressBar { border:2px solid #00f7ff; border-radius:8px;"
            " background:#071326; text-align:center; }"
            "QProgressBar::chunk { background:#00f7ff; }"
        )
        self.status = QLabel("Preparing update...", self)
        self.status.setGeometry(35, 35, 390, 30)
        self.bar = QProgressBar(self)
        self.bar.setGeometry(35, 80, 390, 28)
        self.bar.setRange(0, 100)
        self.target_progress = 0
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.advance_progress)
        self.progress_timer.start(35)

    def set_progress(self, percent, text):
        self.status.setText(text)
        self.target_progress = percent

    def advance_progress(self):
        current = self.bar.value()

        if current >= self.target_progress:
            return

        self.bar.setValue(current + 1)
        self.bar.setFormat(f"{current + 1}%")


class ScreenBot10(ScreenBot):
    def __init__(self, brain_mode="local"):
        self.screenbot10_ready = False

        super().__init__()

        # Startup choice controls normal conversations.
        self.settings["_session_brain_mode"] = brain_mode

        self.brain_mode = brain_mode

        self.brain_badge = QLabel(
            "⚡ PRO"
            if brain_mode == "pro"
            else "🏠 LOCAL",
            self,
        )

        self.brain_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.brain_badge.setStyleSheet(
            """
            QLabel {
                background: rgba(2, 7, 17, 210);
                color: #00f7ff;
                border: 1px solid #00f7ff;
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
                padding: 2px;
            }
            """
        )

        self.version_badge = QLabel(
            f"v{Path(__file__).with_name('VERSION').read_text().strip()}",
            self,
        )
        self.current_version = Path(__file__).with_name(
            "VERSION"
        ).read_text().strip()
        self.version_badge.setStyleSheet(
            "QLabel { color:#00d99a; font-size:10px; font-weight:bold; }"
        )

        if hasattr(self, "move_timer"):
            self.move_timer.stop()

        self.walking_host = WalkingHost()

        self.walking_host.close_handler = (
            self.handle_host_close
        )

        screen = QApplication.primaryScreen()

        self.walking_host.fit_to_screen(screen)

        self.smart_movement = MovementEngine()
        self.smart_movement.speed = 3

        self.panel_movement = MovementEngine()
        self.panel_movement.speed = 2

        self.smart_walking = False
        self.parking_worker = None
        self.parking_scan_active = False
        self.walking_before_scan = False
        self.close_confirmed = False
        self.close_prompt_active = False
        self.session_ending = False
        self.background_mode = False
        self.panel_manual = False
        self.close_prompt = ChoicePrompt(self)
        self.update_worker = None
        self.update_timer = None
        self.install_worker = None
        self.update_progress = None

        self.control_panel = ControlPanel(
            self.bot_name()
        )

        self.control_panel.sleep_requested.connect(
            lambda: self.set_state("sleepy")
        )

        self.control_panel.idle_requested.connect(
            lambda: self.set_state("idle")
        )

        self.control_panel.expand_requested.connect(
            self.show_expanded
        )

        self.control_panel.geometry_changed.connect(
            self.walking_host.update_mask
        )

        self.control_panel.reshaped.connect(
            self.walking_host.repaint
        )

        self.control_panel.moved.connect(
            self.pin_panel
        )

        self.apply_panel_style()

        self.next_scan_time = 0.0
        self.schedule_next_scan(initial=True)

        self.smart_timer = QTimer(self)
        self.smart_timer.timeout.connect(
            self.smart_walk_loop
        )
        self.smart_timer.start(30)

        self.screenbot10_ready = True

        self.show_mini()

        if self.brain_mode == "pro":
            self.configure_update_timer()
            QTimer.singleShot(1000, self.check_for_updates)

        print(
            "🧠 Brain:",
            "⚡ PRO"
            if brain_mode == "pro"
            else "🏠 LOCAL",
        )

    def check_for_updates(self):
        if self.brain_mode != "pro":
            return

        if self.update_worker is not None and self.update_worker.isRunning():
            return

        subprocess.run(
            ["notify-send", "ScreenBot", "Checking for updates..."],
            check=False,
        )
        self.update_worker = UpdateCheckWorker(self.current_version)
        self.update_worker.available.connect(self.offer_update)
        self.update_worker.start()

    def configure_update_timer(self):
        if self.brain_mode != "pro":
            return

        if self.update_timer is None:
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self.check_for_updates)

        minutes = int(self.settings.get("update_check_minutes", 5))
        self.update_timer.start(minutes * 60 * 1000)

    def offer_update(self, release):
        subprocess.run(
            [
                "notify-send",
                "ScreenBot",
                f"Update available: {release.version}",
            ],
            check=False,
        )

        choice = ChoicePrompt(self).ask(
            "ScreenBot Update",
            f"Update available: {release.version}. Want to install it?",
            [("install", "Install update"), ("later", "Not now")],
            "later",
        )

        if choice == "install":
            self.install_update(release)

    def install_update(self, release):
        self.update_progress = UpdateProgressWindow()
        self.update_progress.show()
        self.update_progress.raise_()
        self.install_worker = UpdateInstallWorker(release)
        self.install_worker.progress.connect(
            self.update_progress.set_progress
        )
        self.install_worker.installed.connect(self.restart_after_update)
        self.install_worker.failed.connect(self.show_update_failure)
        self.install_worker.start()

    def restart_after_update(self, entrypoint):
        QProcess.startDetached(sys.executable, [entrypoint])
        self.end_session()

    def show_update_failure(self, message):
        if self.update_progress is not None:
            self.update_progress.close()

        ChoicePrompt(self).ask(
            "ScreenBot Update",
            message,
            [("ok", "OK")],
            "ok",
        )

    def show_mini(self):
        if not getattr(
            self,
            "screenbot10_ready",
            False,
        ):
            return ScreenBot.show_mini(self)

        if self.background_mode:
            return

        self.expanded = False

        self.setFixedSize(180, 160)

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

        self.brain_badge.setGeometry(
            4,
            4,
            66,
            22,
        )
        self.brain_badge.show()
        self.brain_badge.raise_()

        if self.parent() is not self.walking_host:
            self.walking_host.attach_bob(
                self,
                x=max(
                    0,
                    (
                        self.walking_host.width()
                        - self.width()
                    ) // 2,
                ),
                y=max(
                    0,
                    (
                        self.walking_host.height()
                        - self.height()
                    ) // 2,
                ),
            )

            self.walking_host.attach_panel(
                self.control_panel
            )

            self.place_panel(
                self.x(),
                self.y() + self.height() + 6,
            )
        else:
            self.show()

    def show_expanded(self):
        if not getattr(
            self,
            "screenbot10_ready",
            False,
        ):
            return ScreenBot.show_expanded(self)

        if self.parent() is self.walking_host:
            self.walking_host.detach_bob(self)

        self.control_panel.hide()
        self.walking_host.update_mask()

        self.setWindowFlags(
            Qt.WindowType.Window
        )

        ScreenBot.show_expanded(self)

        self.brain_badge.setGeometry(
            245,
            14,
            76,
            24,
        )
        self.brain_badge.show()
        self.brain_badge.raise_()

        self.version_badge.setGeometry(655, 14, 80, 24)
        self.version_badge.show()
        self.version_badge.raise_()

        self.show()
        self.raise_()
        self.activateWindow()

    def smart_walk_loop(self):
        if not self.screenbot10_ready:
            return

        self.handle_show_request()

        if self.background_mode:
            return

        if self.expanded:
            return

        if self.state in {
            "thinking",
            "speaking",
            "sleepy",
        }:
            return

        self.panel_step()

        if self.parking_scan_active:
            return

        if time.monotonic() >= self.next_scan_time:
            self.start_smart_scan()
            return

        if self.smart_walking:
            self.walk_step()

    def start_smart_scan(self):
        screen = QApplication.primaryScreen()

        if screen is None:
            self.schedule_next_scan()
            return

        area = screen.availableGeometry()

        current_global_x = (
            area.x()
            + self.x()
        )

        current_global_y = (
            area.y()
            + self.y()
        )

        self.walking_before_scan = self.smart_walking
        self.parking_scan_active = True

        print(
            f"👁️ {self.bot_name()} is looking for blank space..."
        )

        self.parking_worker = ParkingWorker(
            territory_x=area.x(),
            territory_y=area.y(),
            territory_width=area.width(),
            territory_height=area.height(),
            current_x=current_global_x,
            current_y=current_global_y,
            own_rect=(
                current_global_x,
                current_global_y,
                self.width(),
                self.height(),
            ),
            panel_rect=(
                area.x() + self.control_panel.x(),
                area.y() + self.control_panel.y(),
                self.control_panel.width(),
                self.control_panel.height(),
            ),
            panel_size=(
                self.control_panel.width(),
                self.control_panel.height(),
            ),
        )

        self.parking_worker.finished_scan.connect(
            self.parking_found
        )

        self.parking_worker.start()

    def parking_found(self, decision):
        self.parking_scan_active = False
        self.schedule_next_scan()

        screen = QApplication.primaryScreen()

        if screen is None:
            return

        if decision is None:
            print(
                f"😐 {self.bot_name()} found no safe blank space."
            )

            if not self.walking_before_scan:
                self.set_state("idle")

            return

        escape_mode = decision["escape_mode"]
        best = decision["destination"]

        if best is None:
            print(
                f"😐 {self.bot_name()} found no safe blank space."
            )

            if escape_mode:
                self.smart_walking = False
                self.smart_movement.clear_target()
                self.set_state("idle")

            elif not self.walking_before_scan:
                self.set_state("idle")

            return

        if (
            not escape_mode
            and self.walking_before_scan
        ):
            self.mood.setText("WALKING")
            return

        area = screen.availableGeometry()

        self.move_panel_from_scan(decision, area)

        target_local_x = (
            int(best["x"])
            - area.x()
        )

        target_local_y = (
            int(best["y"])
            - area.y()
        )

        print(
            f"🏆 {self.bot_name()} chose:",            f"x={best['x']}",
            f"y={best['y']}",
            f"score={best['raw_score']:.2f}",
            f"escape={escape_mode}",
        )
        self.smart_movement.set_target(
            target_local_x,
            target_local_y,
        )

        if target_local_x > self.x():
            self.smart_movement.direction = 1

        elif target_local_x < self.x():
            self.smart_movement.direction = -1

        self.smart_walking = True
        self.mood.setText(
            "ESCAPING"
            if escape_mode
            else "WALKING"
        )

        if hasattr(
            self.robot,
            "set_walking",
        ):
            self.robot.set_walking(
                True,
                self.smart_movement.direction,
            )

    def walk_step(self):
        new_x, new_y, done = (
            self.smart_movement.step_to(
                self.x(),
                self.y(),
            )
        )

        self.walking_host.move_bob(
            new_x,
            new_y,
        )

        if not done:
            return

        self.smart_walking = False

        if hasattr(
            self.robot,
            "set_walking",
        ):
            self.robot.set_walking(
                False,
                self.smart_movement.direction,
            )

        self.set_state("idle")
        self.schedule_next_scan()

    def autonomous_speak(self):
        if self.background_mode:
            return

        super().autonomous_speak()

    def closeEvent(self, event):
        self.handle_close_request(event)

    def handle_host_close(self, event):
        self.handle_close_request(event)

    def handle_close_request(self, event):
        if self.close_confirmed:
            event.accept()
            return

        choice = self.ask_close_choice()

        if choice == "kill":
            event.accept()
            self.end_session()
            return

        if choice == "keep":
            if not self.background_enabled():
                event.ignore()
                return

            event.accept()
            self.enter_background()
            return

        event.ignore()

    def background_enabled(self):
        return (
            self.settings.get("background_mode", "On")
            == "On"
        )

    def ask_close_choice(self):
        if self.close_prompt_active:
            return None

        self.close_prompt_active = True

        choice = self.close_prompt.ask(
            "ScreenBot",
            f"Want to keep {self.bot_name()} on or off?",
            [
                (
                    "keep",
                    "Yes, keep it open and close screenbot",
                ),
                ("kill", "No, kill it."),
            ],
            "cancel",
        )

        self.close_prompt_active = False

        return choice

    def bot_name(self):
        return self.settings.get("bot_name", "Bob")

    def apply_panel_style(self):
        accent = ACCENTS.get(
            self.settings.get("panel_color", "Blue"),
            ACCENTS["Blue"],
        )

        self.control_panel.apply_accent(accent)
        self.control_panel.set_name(self.bot_name())
        self.control_panel.apply_shape(
            self.settings.get("panel_shape", "Circle")
        )

    def auto_move_enabled(self):
        return (
            self.settings.get("panel_auto_move", "On")
            == "On"
        )

    def settings_saved(self, settings):
        super().settings_saved(settings)

        if self.auto_move_enabled():
            self.panel_manual = False

        self.apply_panel_style()
        self.configure_update_timer()

    def panel_step(self):
        current_x = self.control_panel.x()
        current_y = self.control_panel.y()

        new_x, new_y, done = self.panel_movement.step_to(
            current_x,
            current_y,
        )

        if (new_x, new_y) == (current_x, current_y):
            return

        self.walking_host.move_panel(new_x, new_y)

    def place_panel(self, x, y):
        screen = QApplication.primaryScreen()

        if screen is None:
            return

        area = screen.availableGeometry()

        x = max(
            0,
            min(x, area.width() - self.control_panel.width()),
        )

        y = max(
            0,
            min(y, area.height() - self.control_panel.height()),
        )

        self.panel_movement.clear_target()
        self.walking_host.move_panel(x, y)

    def pin_panel(self):
        self.panel_manual = True

        print(
            f"📌 {self.bot_name()}'s control panel pinned where you dropped it."
        )

    def move_panel_from_scan(self, decision, area):
        if self.panel_manual:
            return

        if not self.auto_move_enabled():
            return

        spot = decision.get("panel")

        if spot is None:
            return

        self.panel_movement.set_target(
            int(spot["x"]) - area.x(),
            int(spot["y"]) - area.y(),
        )

    def handle_show_request(self):
        if not SHOW_REQUEST_FILE.exists():
            return

        try:
            age = time.time() - SHOW_REQUEST_FILE.stat().st_mtime

        except OSError:
            return

        SHOW_REQUEST_FILE.unlink(missing_ok=True)

        if age > SHOW_REQUEST_MAX_AGE:
            return

        print("👋 Reopening Bob on request.")

        self.reveal()

    def reveal(self):
        self.background_mode = False
        self.close_confirmed = False
        self.close_prompt_active = False

        app = QApplication.instance()

        if app is not None:
            app.setQuitOnLastWindowClosed(True)

        self.show_expanded()

    def enter_background(self):
        self.background_mode = True
        self.close_confirmed = True

        self.hide()

        if self.parent() is self.walking_host:
            self.walking_host.detach_bob(self)

        self.walking_host.hide()

        app = QApplication.instance()

        if app is not None:
            app.setQuitOnLastWindowClosed(False)

    def end_session(self):
        if self.session_ending:
            return

        self.session_ending = True
        self.close_confirmed = True

        self.hide()
        self.walking_host.hide()
        self.walking_host.close()

        app = QApplication.instance()

        if app is not None:
            app.quit()

    def schedule_next_scan(self, initial=False):
        delay_min, delay_max = scan_delay_range(
            self.brain_mode,
            initial,
        )

        self.next_scan_time = (
            time.monotonic()
            + random.uniform(delay_min, delay_max)
        )


class BrainChoiceWindow(QWidget):
    def __init__(self, territory_mode):
        super().__init__()

        self.territory_mode = territory_mode
        self.bot = None

        self.setWindowTitle("ScreenBot 10")
        self.setFixedSize(620, 360)

        self.setStyleSheet(
            """
            QWidget {
                background:#020711;
                color:#00f7ff;
                font-family:Arial;
            }

            QLabel#title {
                font-size:30px;
                font-weight:bold;
            }

            QLabel#status {
                font-size:16px;
            }

            QPushButton {
                background:#071326;
                color:#00f7ff;
                border:2px solid #00f7ff;
                border-radius:16px;
                font-size:18px;
                font-weight:bold;
                padding:18px;
            }

            QPushButton:hover {
                background:#00f7ff;
                color:#020711;
            }
            """
        )

        title = QLabel(
            "🤖 HOW SHOULD I THINK?",
            self,
        )
        title.setObjectName("title")
        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        title.setGeometry(
            70,
            45,
            480,
            50,
        )

        self.status = QLabel(
            "Choose a brain mode.",
            self,
        )
        self.status.setObjectName("status")
        self.status.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.status.setGeometry(
            60,
            105,
            500,
            35,
        )

        self.wifi_btn = QPushButton(
            "📶 USE WIFI\n\nPerformance Mode",
            self,
        )
        self.wifi_btn.setGeometry(
            60,
            180,
            230,
            120,
        )

        self.local_btn = QPushButton(
            "🏠 WITHOUT WIFI\n\nLocal Ollama",
            self,
        )
        self.local_btn.setGeometry(
            330,
            180,
            230,
            120,
        )

        self.wifi_btn.clicked.connect(
            self.use_wifi
        )

        self.local_btn.clicked.connect(
            self.use_local
        )

    def use_wifi(self):
        self.status.setText(
            "Searching for connection..."
        )
        QApplication.processEvents()

        has_internet = internet_available()
        has_key = HybridBrain().pro_available()

        if has_internet and has_key:
            self.status.setText(
                "⚡ Performance Mode!"
            )
            QApplication.processEvents()

            print(
                "📶 Internet: YES"
            )
            print(
                "🔑 DeepSeek key: YES"
            )
            print(
                "⚡ Performance Mode enabled"
            )

            self.start_bob("pro")
            return

        if not has_internet:
            print(
                "📵 Internet: NO"
            )
            print(
                "🏠 Falling back to Local Mode"
            )

            self.status.setText(
                "No internet — Local Mode"
            )

        else:
            print(
                "📶 Internet: YES"
            )
            print(
                "🔑 DeepSeek key: NO"
            )
            print(
                "🏠 Falling back to Local Mode"
            )

            self.status.setText(
                "No API key — Local Mode"
            )

        QApplication.processEvents()
        self.start_bob("local")

    def use_local(self):
        print(
            "🏠 Local Mode selected"
        )
        self.start_bob("local")

    def start_bob(self, brain_mode):
        # DEFAULT currently works.
        # ORIGINAL/NEW will later provide
        # different territories to this same Bob.
        self.bot = ScreenBot10(
            brain_mode=brain_mode
        )

        self.hide()


class StartupWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.brain_window = None

        self.setWindowTitle(
            "ScreenBot 10"
        )
        self.setFixedSize(
            760,
            430,
        )

        self.setStyleSheet(
            """
            QWidget {
                background:#020711;
                color:#00f7ff;
                font-family:Arial;
            }

            QLabel#title {
                font-size:34px;
                font-weight:bold;
            }

            QLabel#subtitle {
                font-size:20px;
            }

            QPushButton {
                background:#071326;
                color:#00f7ff;
                border:2px solid #00f7ff;
                border-radius:16px;
                font-size:18px;
                font-weight:bold;
                padding:18px;
            }

            QPushButton:hover {
                background:#00f7ff;
                color:#020711;
            }

            QPushButton:disabled {
                border-color:#32444d;
                color:#32444d;
                background:#071019;
            }

            QProgressBar {
                background:#071326;
                color:#00f7ff;
                border:2px solid #00f7ff;
                border-radius:8px;
                text-align:center;
            }

            QProgressBar::chunk {
                background:#00f7ff;
            }
            """
        )

        title = QLabel(
            "🤖 SCREENBOT 10",
            self,
        )
        title.setObjectName("title")
        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        title.setGeometry(
            100,
            45,
            560,
            55,
        )

        subtitle = QLabel(
            "Where may I explore?",
            self,
        )
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        subtitle.setGeometry(
            100,
            105,
            560,
            40,
        )

        self.default_btn = QPushButton(
            "DEFAULT\n\nSmart bottom territory",
            self,
        )
        self.default_btn.setGeometry(
            45,
            190,
            210,
            150,
        )

        self.original_btn = QPushButton(
            "ORIGINAL\n\nUse my last territory",
            self,
        )
        self.original_btn.setGeometry(
            275,
            190,
            210,
            150,
        )

        self.new_btn = QPushButton(
            "NEW\n\nDraw a new territory",
            self,
        )
        self.new_btn.setGeometry(
            505,
            190,
            210,
            150,
        )

        self.default_btn.clicked.connect(
            lambda:
                self.choose_territory(
                    "default"
                )
        )

        self.original_btn.clicked.connect(
            lambda:
                self.choose_territory(
                    "original"
                )
        )

        self.new_btn.clicked.connect(
            lambda:
                self.choose_territory(
                    "new"
                )
        )

        self.original_btn.setEnabled(
            TERRITORY_FILE.exists()
        )
        self.new_btn.setEnabled(False)

        self.cleanup_bar = QProgressBar(self)
        self.cleanup_bar.setGeometry(
            100,
            365,
            560,
            26,
        )
        self.cleanup_bar.setRange(0, 100)
        self.cleanup_bar.hide()

    def set_cleanup_progress(self, percent, text):
        self.cleanup_bar.setValue(percent)
        self.cleanup_bar.setFormat(text)

    def show_cleanup_progress(self):
        self.cleanup_bar.setValue(0)
        self.cleanup_bar.show()
        self.cleanup_bar.raise_()

    def hide_cleanup_progress(self):
        self.cleanup_bar.hide()

    def choose_territory(self, mode):
        print(
            f"🗺 Territory: {mode}"
        )

        self.brain_window = (
            BrainChoiceWindow(mode)
        )

        self.brain_window.show()
        self.hide()


def main():
    app = QApplication(sys.argv)

    app.setQuitOnLastWindowClosed(
        True
    )

    startup_holder = {}
    bot_name = load_json(SETTINGS_FILE, {}).get(
        "bot_name",
        "Bob",
    )

    def show_startup():
        startup = StartupWindow()
        startup_holder["window"] = startup
        startup.show()

    def start_after_cleanup():
        show_startup()

        startup = startup_holder["window"]
        startup.show_cleanup_progress()

        clean_up_old_bobs(
            app,
            startup.set_cleanup_progress,
        )

        startup.hide_cleanup_progress()

    if another_bob_is_running():
        prompt = ChoicePrompt()

        choice = prompt.ask(
            "ScreenBot",
            f"{bot_name} is already running 🤖",
            [
                (
                    "cleanup",
                    "Clean up old Bobs and continue launching ScreenBot",
                ),
                ("show", "Show the running Bob"),
            ],
            "cancel",
        )

        if choice == "cleanup":
            start_after_cleanup()

        elif choice == "show":
            SHOW_REQUEST_FILE.write_text(
                str(time.time())
            )

            print(
                "👋 Asked the running Bob to show itself."
            )

            sys.exit(0)

        else:
            print(
                "🤖 Bob is already running. Not launching another."
            )

            sys.exit(0)
    else:
        show_startup()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
