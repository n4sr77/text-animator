"""Coverage for the six professional mood presets."""
import unittest
try:
    import moviepy  # noqa: F401
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False

class TestMoodPresetRegistry(unittest.TestCase):
    def test_all_six_are_registered_and_labeled(self):
        from text_animator.presets import PRESETS, PRESET_LABELS
        expected = {
            "impact_strike": "Action · Impact Strike",
            "cinematic_rush": "Action · Cinematic Rush",
            "soft_flow": "Calm · Soft Flow",
            "serenity": "Calm · Serenity",
            "melancholy_fade": "Sad · Melancholy Fade",
            "rainy_memories": "Sad · Rainy Memories",
        }
        for key, label in expected.items():
            self.assertIn(key, PRESETS)
            self.assertEqual(PRESET_LABELS[key], label)
            self.assertTrue(PRESETS[key].description)
        self.assertEqual(len(PRESETS), 17)

    @unittest.skipUnless(HAS_MOVIEPY, "moviepy not installed")
    def test_each_builds_video(self):
        from text_animator.presets import PRESETS
        from text_animator.presets.base import RenderContext
        from text_animator.fonts import get_default_font
        _font_name, font = get_default_font()
        ctx = RenderContext(["Test"], (640,360), str(font), 48, "white",
            (12,14,20), 1.4, 0.1, 0.2, 12)
        for key in ("impact_strike","cinematic_rush","soft_flow","serenity","melancholy_fade","rainy_memories"):
            with self.subTest(preset=key):
                clip, duration = PRESETS[key].build(ctx)
                self.assertGreater(duration, 1.0)
                self.assertEqual(clip.size, ctx.size)
                clip.close()
