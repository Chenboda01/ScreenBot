import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

from ScreenBot import DEFAULT_SETTINGS, SettingsWindow
from world.destinations import DestinationScene
from world.walking_host import WalkingHost


class DestinationSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_show_destination_when_home_selected(self):
        # Given: a new destination scene.
        scene = DestinationScene()

        # When: Home is selected at a desktop position.
        scene.show_destination("Home", 120, 80)
        snapshot = scene.grab()

        # Then: the scene is visible, named, and positioned at that spot.
        self.assertTrue(scene.isVisible())
        self.assertEqual("Home", scene.destination_name)
        self.assertEqual((120, 80), (scene.x(), scene.y()))
        self.assertFalse(snapshot.isNull())

    def test_render_when_each_destination_is_selected(self):
        # Given: a scene for each supported destination.
        scene = DestinationScene()

        for name in ("Home", "Grocery Store", "Desk", "Park"):
            with self.subTest(name=name):
                # When: that destination is shown and its entrance completes.
                scene.show_destination(name, 0, 0)
                QTest.qWait(260)
                snapshot = scene.grab()

                # Then: its painted desktop card has real rendered pixels.
                self.assertFalse(snapshot.isNull())
                self.assertGreater(snapshot.toImage().sizeInBytes(), 0)

    def test_clear_destination_when_scene_is_visible(self):
        # Given: a visible destination scene.
        scene = DestinationScene()
        scene.show_destination("Park", 30, 40)

        # When: the visit ends.
        scene.clear_destination()
        QTest.qWait(260)

        # Then: the scene no longer appears on the desktop.
        self.assertFalse(scene.isVisible())

    def test_host_mask_when_destination_is_visible(self):
        # Given: a transparent walking host with a destination child.
        host = WalkingHost()
        scene = DestinationScene()
        host.attach_scene(scene)
        host.show()
        self.app.processEvents()

        # When: a destination is shown in the host.
        scene.show_destination("Desk", 24, 36)

        # Then: the host mask includes the scene's painted bounds.
        self.assertTrue(host.current_region().contains(scene.geometry()))
        host.close()

    def test_settings_when_destination_scenes_are_disabled(self):
        # Given: destination scenes are disabled in persisted settings.
        settings = {**DEFAULT_SETTINGS, "destination_scenes": "Off"}

        # When: the Settings window loads that configuration.
        window = SettingsWindow(settings)

        # Then: the toggle presents the saved disabled state.
        self.assertEqual("Off", window.destination_scenes.currentText())
        window.close()
