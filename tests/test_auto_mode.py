import unittest

import numpy as np

from auto_mode import (
    ScreenBounds,
    find_translation_path,
    screen_changed,
    text_key,
)


class FakeLanguage:
    def __init__(self, code):
        self.code = code
        self.translations_from = []


class FakeTranslation:
    def __init__(self, to_lang):
        self.to_lang = to_lang


class AutoModeTests(unittest.TestCase):
    def test_first_frame_and_changed_frame_trigger_detection(self):
        original = np.zeros((40, 40), dtype=np.uint8)
        changed = original.copy()
        changed[:5, :5] = 255

        self.assertTrue(screen_changed(None, original))
        self.assertFalse(screen_changed(original, original.copy()))
        self.assertTrue(screen_changed(original, changed))

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


if __name__ == "__main__":
    unittest.main()
