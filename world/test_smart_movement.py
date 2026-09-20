import os

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtWidgets import QApplication

import main as main_module
import ScreenBot as screenbot_module
from main import scan_delay_range
from world.movement import MovementEngine
from world.parking import ParkingEngine
from world.vision import VisionEngine


DEJAVU_FONT = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)


class StubPrompt:
    def __init__(self, result):
        self.result = result

    def ask(self, title, body, choices, default_key):
        return self.result


class FakeVision:
    def __init__(
        self,
        scores,
        default_score=0.90,
        text_scores=None,
    ):
        self.scores = scores
        self.default_score = default_score
        self.text_scores = text_scores or {}

    def score_region(self, screenshot, x, y, width, height):
        location = (x + 30, y + 30)
        score = self.scores.get(
            location,
            self.scores.get(location[0], self.default_score),
        )

        return {
            "score": score,
            "text": self.text_scores.get(
                location,
                self.text_scores.get(location[0], 0.0),
            ),
            "visual": score,
        }

    def prepare_scan(self, screenshot, own_rect=None):
        return None


class SmartParkingTests(unittest.TestCase):
    def test_escape_mode_ignores_normal_travel_limit(self):
        # Given: Bob is blocking busy content and only a distant region is safe.
        parking = ParkingEngine(
            vision=FakeVision({600: 0.05}),
            bot_width=100,
            bot_height=100,
            step=100,
            max_score=0.22,
            max_travel=200,
            padding=30,
        )

        # When: parking evaluates Bob's current location.
        decision = parking.plan_parking(
            screenshot="screen",
            territory_x=0,
            territory_y=0,
            territory_width=800,
            territory_height=100,
            current_x=0,
        )

        # Then: escape selects the safe destination beyond the normal limit.
        self.assertTrue(decision["escape_mode"])
        self.assertEqual(600, decision["destination"]["x"])

    def test_excluded_area_is_never_chosen(self):
        # Given: the only blank area is where Bob is parked.
        parking = ParkingEngine(
            vision=FakeVision(
                {200: 0.00},
                default_score=0.90,
            ),
            bot_width=100,
            bot_height=100,
            step=100,
            max_score=0.22,
            max_travel=1000,
            padding=30,
        )

        without = parking.plan_parking(
            screenshot="screen",
            territory_x=0,
            territory_y=0,
            territory_width=400,
            territory_height=100,
            current_x=0,
        )

        self.assertEqual(200, without["destination"]["x"])

        # When: that same area is excluded for the second search.
        with_exclusion = parking.plan_parking(
            screenshot="screen",
            territory_x=0,
            territory_y=0,
            territory_width=400,
            territory_height=100,
            current_x=0,
            exclude_rect=(150, 0, 200, 100),
        )

        # Then: it is never offered as a destination.
        self.assertIsNone(with_exclusion["destination"])

    def test_escape_mode_can_choose_a_text_free_vertical_destination(self):
        # Given: only a blank row above Bob is safe inside the territory.
        parking = ParkingEngine(
            vision=FakeVision({(0, 300): 0.05}),
            bot_width=100,
            bot_height=100,
            step=100,
            max_score=0.22,
            max_travel=200,
            padding=30,
        )

        # When: the full two-dimensional territory is evaluated.
        decision = parking.plan_parking(
            screenshot="screen",
            territory_x=0,
            territory_y=0,
            territory_width=800,
            territory_height=500,
            current_x=0,
            current_y=0,
        )

        # Then: escape can move vertically to the text-free target.
        self.assertTrue(decision["escape_mode"])
        self.assertEqual((0, 300), (
            decision["destination"]["x"],
            decision["destination"]["y"],
        ))

    def test_escape_mode_detects_short_text_at_current_location(self):
        # Given: the combined score is low but OCR sees a short label under Bob.
        parking = ParkingEngine(
            vision=FakeVision(
                {0: 0.10, 600: 0.05},
                text_scores={0: 0.06},
            ),
            bot_width=100,
            bot_height=100,
            step=100,
            max_score=0.22,
            max_travel=200,
            padding=30,
        )

        # When: parking evaluates Bob's current location.
        decision = parking.plan_parking(
            screenshot="screen",
            territory_x=0,
            territory_y=0,
            territory_width=800,
            territory_height=100,
            current_x=0,
        )

        # Then: the text overlap triggers escape to a blank destination.
        self.assertTrue(decision["escape_mode"])
        self.assertEqual(600, decision["destination"]["x"])

    def test_normal_roaming_prefers_near_safe_space(self):
        # Given: Bob is safe, with a nearby safe space and a marginally
        # lower-scoring but distant alternative.
        parking = ParkingEngine(
            vision=FakeVision({0: 0.10, 200: 0.11, 800: 0.08}),
            bot_width=100,
            bot_height=100,
            step=100,
            max_score=0.22,
            max_travel=1000,
            padding=30,
        )

        # When: parking plans ordinary roaming.
        decision = parking.plan_parking(
            screenshot="screen",
            territory_x=0,
            territory_y=0,
            territory_width=1000,
            territory_height=100,
            current_x=0,
        )

        # Then: it keeps the normal move natural instead of taking a giant trip.
        self.assertFalse(decision["escape_mode"])
        self.assertEqual(200, decision["destination"]["x"])

    def test_normal_roaming_reaches_beyond_old_limit(self):
        # Given: only a much better blank destination lies beyond 350 pixels.
        parking = ParkingEngine(
            vision=FakeVision({0: 0.10, 500: 0.00}),
            bot_width=100,
            bot_height=100,
            step=100,
            max_score=0.22,
            padding=30,
        )

        # When: parking plans an ordinary roam.
        decision = parking.plan_parking(
            screenshot="screen",
            territory_x=0,
            territory_y=0,
            territory_width=800,
            territory_height=100,
            current_x=0,
        )

        # Then: the expanded normal range allows the better safe destination.
        self.assertFalse(decision["escape_mode"])
        self.assertGreater(decision["destination"]["x"], 350)


class MovementEngineTests(unittest.TestCase):
    def test_vertical_target_moves_without_horizontal_drift(self):
        # Given: Bob is already aligned with a destination above him.
        movement = MovementEngine()
        movement.set_target(40, 100)

        # When: the engine advances one walking step.
        new_x, new_y, done = movement.step_to(40, 90)

        # Then: it progresses vertically without changing the horizontal position.
        self.assertEqual((40, 93, False), (new_x, new_y, done))


class VisionScanTests(unittest.TestCase):
    def test_blank_region_overwrites_own_area(self):
        # Given: a dark image standing in for Bob's own painted pixels.
        image = Image.new("RGB", (400, 200), "black")
        vision = VisionEngine()

        # When: Bob's own rectangle is blanked for the scan.
        vision.blank_region(image, (50, 40, 100, 80))

        # Then: only that rectangle turns blank.
        self.assertEqual((255, 255, 255), image.getpixel((60, 50)))
        self.assertEqual((255, 255, 255), image.getpixel((149, 119)))
        self.assertEqual((0, 0, 0), image.getpixel((20, 20)))
        self.assertEqual((0, 0, 0), image.getpixel((151, 121)))

    def test_prepare_scan_excludes_own_region_from_scoring(self):
        # Given: an image with a label exactly where Bob stands.
        image = Image.new("RGB", (500, 200), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(DEJAVU_FONT, 56)
        draw.text((160, 70), "HELLO", fill="black", font=font)

        temp = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
        )
        temp.close()
        path = Path(temp.name)
        image.save(path)

        # When: the same region is scored with and without Bob's rect blanked.
        with_content = VisionEngine()
        with_content.prepare_scan(path)
        content = with_content.score_region(path, 150, 60, 220, 100)

        blanked = VisionEngine()
        blanked.prepare_scan(path, own_rect=(145, 55, 240, 110))
        covered = blanked.score_region(path, 150, 60, 220, 100)

        path.unlink()

        # Then: Bob's own pixels never look like content to himself.
        self.assertGreater(content["text"], 0.0)
        self.assertEqual(0.0, covered["text"])


class CloseChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

        cls.temp_dir = Path(tempfile.mkdtemp())

        screenbot_module.CHATS_FILE = (
            cls.temp_dir / "chats.json"
        )

        screenbot_module.SETTINGS_FILE = (
            cls.temp_dir / "settings.json"
        )

        screenbot_module.MEMORY_FILE = (
            cls.temp_dir / "memory.json"
        )

    def setUp(self):
        self.app.setQuitOnLastWindowClosed(True)

        for name in ("chats.json", "settings.json"):
            path = self.temp_dir / name

            if path.exists():
                path.unlink()

    def tearDown(self):
        self.app.setQuitOnLastWindowClosed(True)

    def make_bot(self, choice):
        bot = main_module.ScreenBot10("local")
        bot.close_prompt = StubPrompt(choice)
        return bot

    def test_keep_closes_ui_but_keeps_the_server(self):
        # Given: Bob is open and the user chooses to keep the server on.
        bot = self.make_bot("keep")

        # When: his window is closed.
        bot.close()

        # Then: the UI is gone and the process is meant to stay alive.
        self.assertTrue(bot.background_mode)
        self.assertFalse(bot.session_ending)
        self.assertFalse(bot.walking_host.isVisible())
        self.assertFalse(self.app.quitOnLastWindowClosed())

        bot.smart_walk_loop()
        self.assertIsNone(bot.parking_worker)

        bot.autonomous_speak()
        self.assertIsNone(bot.worker)

        bot.close()
        bot.walking_host.close()

    def test_kill_ends_the_session(self):
        # Given: Bob is open and the user chooses to kill the server.
        bot = self.make_bot("kill")

        # When: his window is closed.
        bot.close()

        # Then: the session ends and the UI is gone.
        self.assertTrue(bot.session_ending)
        self.assertFalse(bot.walking_host.isVisible())

        bot.walking_host.close()

    def test_background_mode_never_reopens_the_closed_ui(self):
        # Given: Bob was closed and is running in the background.
        bot = self.make_bot("keep")
        bot.close()

        self.assertTrue(bot.background_mode)
        self.assertFalse(bot.walking_host.isVisible())
        self.assertIsNone(bot.walking_host.bob)

        # When: anything tries to show the mini Bob again.
        bot.show_mini()
        main_module.ScreenBot.show_mini(bot)

        # Then: no second Bob may appear.
        self.assertFalse(bot.walking_host.isVisible())
        self.assertFalse(bot.isVisible())

        bot.close()
        bot.walking_host.close()

    def test_background_mode_off_keeps_bob_open_instead(self):
        # Given: background mode is switched off in the settings.
        bot = self.make_bot("keep")
        bot.settings["background_mode"] = "Off"

        # When: the user picks "keep it open" while closing.
        bot.close()

        # Then: the close is cancelled and no server is left behind.
        self.assertFalse(bot.close_confirmed)
        self.assertFalse(bot.background_mode)
        self.assertTrue(bot.isVisible())
        self.assertTrue(bot.walking_host.isVisible())

        bot.close_confirmed = True
        bot.close()
        bot.walking_host.close()

    def test_dismissing_the_prompt_cancels_the_close(self):
        # Given: Bob is open and the user dismisses the close prompt.
        bot = self.make_bot("cancel")

        # When: his window is closed.
        bot.close()

        # Then: nothing closes and Bob stays on screen.
        self.assertFalse(bot.close_confirmed)
        self.assertFalse(bot.background_mode)
        self.assertTrue(bot.isVisible())

        bot.close_confirmed = True
        bot.close()
        bot.walking_host.close()


class TextSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def test_text_size_setting_scales_the_stylesheet(self):
        # Given: Bob with the default text size.
        bot = main_module.ScreenBot10("local")

        # When: the text size is set to Large.
        bot.settings["text_size"] = "Large"
        bot.apply_theme()

        # Then: the stylesheet uses the Large size and it persists.
        self.assertIn("17px", bot.styleSheet())
        self.assertEqual(
            "Large",
            bot.settings_for_disk()["text_size"],
        )

        bot.close_confirmed = True
        bot.close()
        bot.walking_host.close()

    def test_text_size_default_is_medium(self):
        # Given/When/Then: the default size is Medium and is selectable.
        self.assertEqual(
            "Medium",
            screenbot_module.DEFAULT_SETTINGS["text_size"],
        )

        self.assertIn(
            "Medium",
            screenbot_module.TEXT_SIZES,
        )


class ScanCadenceTests(unittest.TestCase):
    def test_scan_delay_ranges_depend_on_brain_mode(self):
        # Given: the two supported session brain modes.
        # When: their initial and awareness ranges are requested.
        # Then: Pro scans sooner than Local mode.
        self.assertEqual((2, 4), scan_delay_range("pro", initial=True))
        self.assertEqual((3, 5), scan_delay_range("pro", initial=False))
        self.assertEqual((8, 18), scan_delay_range("local", initial=True))
        self.assertEqual((10, 25), scan_delay_range("local", initial=False))


class UpdatePollingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pro_mode_polls_the_pages_manifest_every_five_minutes(self):
        # Given: a Pro ScreenBot session.
        bot = main_module.ScreenBot10("pro")
        bot.settings["update_check_minutes"] = 5

        # When: startup configures the update checker.
        bot.configure_update_timer()

        # Then: the timer rechecks the GitHub Pages manifest every five minutes.
        self.assertIsNotNone(bot.update_timer)
        self.assertEqual(
            5 * 60 * 1000,
            bot.update_timer.interval(),
        )

        bot.close_confirmed = True
        bot.close()
        bot.walking_host.close()

    def test_local_mode_does_not_create_an_update_timer(self):
        # Given: a Local ScreenBot session.
        bot = main_module.ScreenBot10("local")

        # When: startup completes.

        # Then: only Pro mode polls for paid update availability.
        self.assertIsNone(bot.update_timer)

        bot.close_confirmed = True
        bot.close()
        bot.walking_host.close()


if __name__ == "__main__":
    unittest.main()
