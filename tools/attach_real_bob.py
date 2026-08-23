from pathlib import Path


ROOT = Path.home() / "ScreenBot"
FILE = ROOT / "ScreenBot.py"


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"❌ Could not patch: {label}")

    return text.replace(old, new, 1)


def main():
    s = FILE.read_text()

    # Import WalkingHost.
    if "from world.walking_host import WalkingHost" not in s:
        s = replace_once(
            s,
            "from world.movement import MovementEngine\n",
            "from world.movement import MovementEngine\n"
            "from world.walking_host import WalkingHost\n",
            "WalkingHost import",
        )

    # Create the host.
    if "self.walking_host = WalkingHost()" not in s:
        s = replace_once(
            s,
            "        self.walking = False\n",
            "        self.walking = False\n"
            "        self.walking_host = WalkingHost()\n"
            "        self.walking_host.fit_to_screen(\n"
            "            QApplication.primaryScreen()\n"
            "        )\n"
            "        self.walking_host.show()\n",
            "walking host setup",
        )

    # Replace show_mini with a host-attaching version.
    start = s.find("    def show_mini(self):")
    end = s.find("\n    def show_expanded(self):", start)

    if start == -1 or end == -1:
        raise SystemExit("❌ Could not locate show_mini")

    new_show_mini = '''    def show_mini(self):
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
        ]:
            widget.hide()

        self.robot.show()
        self.mood.show()

        if self.parent() is not self.walking_host:
            self.walking_host.attach_bob(
                self,
                x=20,
                y=10,
            )

'''

    s = s[:start] + new_show_mini + s[end + 1:]

    # Make expanded mode detach the same Bob.
    marker = "    def show_expanded(self):\n        self.expanded = True\n"

    replacement = '''    def show_expanded(self):
        self.expanded = True

        if self.parent() is self.walking_host:
            self.walking_host.detach_bob(self)

        self.setWindowFlags(
            Qt.WindowType.Window
        )

        self.show()
'''

    s = replace_once(
        s,
        marker,
        replacement,
        "show_expanded detach",
    )

    FILE.write_text(s)

    print("✅ ONE REAL BOB attached to walking host")


if __name__ == "__main__":
    main()
