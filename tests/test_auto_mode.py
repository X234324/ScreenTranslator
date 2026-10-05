import os
import unittest

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from auto_mode import (
    ScreenBounds,
    TextRegion,
    TrayControls,
    TranslationOverlay,
    extract_text_regions,
    find_translation_path,
    MonitorThread,
    screen_changed,
    screen_preview,
    text_key,
    virtual_screen_bounds,
)


class FakeLanguage:
    def __init__(self, code):
        self.code = code
        self.translations_from = []


class FakeTranslation:
    def __init__(self, to_lang):
        self.to_lang = to_lang


class AutoModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_first_frame_and_changed_frame_trigger_detection(self):
        original = np.zeros((40, 40), dtype=np.uint8)
        changed = original.copy()
        changed[:5, :5] = 255

        self.assertTrue(screen_changed(None, original))
        self.assertFalse(screen_changed(original, original.copy()))
        self.assertTrue(screen_changed(original, changed))

    def test_overlay_changes_are_excluded_from_change_detection(self):
        region = TextRegion("Hello world", 10, 10, 30, 10, "你好，世界")
        monitor = MonitorThread(
            ScreenBounds(0, 0, 100, 50),
            lambda: (region,),
        )
        previous = np.zeros((50, 100), dtype=np.uint8)
        current = previous.copy()
        previous[10:20, 10:40] = 60
        current[10:20, 10:40] = 200
        monitor_info = {"left": 0, "top": 0, "width": 100, "height": 50}

        comparison_previous = screen_preview(
            monitor._exclude_translations(previous.copy(), monitor_info)
        )
        comparison_current = screen_preview(
            monitor._exclude_translations(current.copy(), monitor_info)
        )

        self.assertFalse(screen_changed(comparison_previous, comparison_current))

    def test_translation_cache_key_normalizes_whitespace_and_case(self):
        self.assertEqual(text_key("Hello   World", "en"), text_key(" hello world ", "en"))
        self.assertNotEqual(text_key("hello", "en"), text_key("hello", "fr"))

    def test_translation_path_uses_available_pivot_language(self):
        english, french, chinese = map(FakeLanguage, ("en", "fr", "zh"))
        french_to_english = FakeTranslation(english)
        english_to_chinese = FakeTranslation(chinese)
        french.translations_from.append(french_to_english)
        english.translations_from.append(english_to_chinese)

        self.assertEqual(
            find_translation_path([english, french, chinese], "fr", "zh"),
            [french_to_english, english_to_chinese],
        )
        self.assertEqual(find_translation_path([english, chinese], "fr", "zh"), [])

    def test_screen_bounds_captures_negative_monitor_origins(self):
        bounds = ScreenBounds(-1920, 0, 3840, 1080)
        self.assertEqual((bounds.left, bounds.width), (-1920, 3840))

    def test_ocr_words_are_grouped_with_screen_coordinates(self):
        data = {
            "text": ["Hello", "world", "bonjour", "today"],
            "conf": ["90", "88", "96", "91"],
            "left": [10, 60, 10, 10],
            "top": [20, 20, 80, 40],
            "width": [40, 45, 70, 40],
            "height": [15, 15, 15, 15],
            "block_num": [1, 1, 2, 1],
            "par_num": [1, 1, 1, 1],
            "line_num": [1, 1, 1, 2],
            "page_num": [1, 1, 1, 1],
        }

        regions = extract_text_regions(data, left=-1920, top=30)

        self.assertEqual(
            regions,
            [
                TextRegion("Hello world today", -1910, 50, 95, 35),
                TextRegion("bonjour", -1910, 110, 70, 15),
            ],
        )

    def test_translation_appears_at_the_matching_source_location(self):
        bounds = ScreenBounds(-100, -50, 800, 600)
        overlay = TranslationOverlay(bounds)
        overlay.show()
        self.app.processEvents()
        source = TextRegion("Hello world", 100, 120, 120, 24)
        overlay.set_translations([
            TextRegion(
                source.text,
                source.left,
                source.top,
                source.width,
                source.height,
                "你好，世界",
            )
        ])
        self.app.processEvents()
        first_label = next(iter(overlay._labels.values()))

        self.assertTrue(overlay.windowFlags() & Qt.FramelessWindowHint)
        self.assertTrue(overlay.windowFlags() & Qt.WindowStaysOnTopHint)
        self.assertTrue(overlay.windowFlags() & Qt.WindowTransparentForInput)
        self.assertEqual(overlay.geometry().getRect(), (-100, -50, 800, 600))
        self.assertEqual(len(overlay._labels), 1)
        self.assertIn("你好，世界", first_label.text())
        self.assertIn("Hello world", first_label.text())
        self.assertEqual(first_label.x(), source.left - bounds.left)
        self.assertEqual(first_label.y(), source.top - bounds.top)
        self.assertEqual(first_label.width(), source.width)
        self.assertEqual(overlay.mask_regions()[0].left, source.left)
        self.assertEqual(overlay.mask_regions()[0].top, source.top)
        overlay.set_translations([])
        self.assertTrue(first_label.isVisible())
        self.assertEqual(len(overlay.mask_regions()), 1)
        overlay.set_translations([
            TextRegion(
                source.text,
                source.left,
                source.top,
                source.width,
                source.height,
                "你好，世界",
            )
        ])
        self.assertIs(next(iter(overlay._labels.values())), first_label)
        self.assertEqual(len(overlay._labels), 1)

        image = QImage(overlay.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        overlay.render(image)
        label_center = first_label.geometry().center()
        self.assertGreater(image.pixelColor(label_center).alpha(), 0)
        self.assertEqual(image.pixelColor(10, 10).alpha(), 0)
        overlay.close()
        self.app.processEvents()

    def test_tray_menu_pauses_and_resumes_screen_monitoring(self):
        monitor = MonitorThread(ScreenBounds(0, 0, 800, 600), lambda: ())
        tray = TrayControls(self.app, monitor)

        tray.toggle_action.trigger()
        self.assertFalse(monitor._active.is_set())
        self.assertEqual(tray.toggle_action.text(), "继续翻译")

        tray.toggle_action.trigger()
        self.assertTrue(monitor._active.is_set())
        self.assertEqual(tray.toggle_action.text(), "暂停翻译")
        tray.tray.hide()


if __name__ == "__main__":
    unittest.main()
