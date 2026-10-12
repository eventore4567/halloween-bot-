import unittest
from io import BytesIO

from PIL import Image

from halloween import config
from halloween.art import banners, cards
from halloween.art.emoji_art import EMOJIS, render_emoji
from halloween.content import quiz_bank
from halloween.content.games import CARDS


class ArtTest(unittest.TestCase):
    def test_every_emoji_fits_discord_limits(self):
        for name, spec in EMOJIS.items():
            data = render_emoji(name)
            self.assertLess(len(data), 256 * 1024, name)
            img = Image.open(BytesIO(data))
            self.assertEqual(img.size, (128, 128), name)
            frames = getattr(img, "n_frames", 1)
            self.assertTrue(frames > 1 if spec.frames > 1 else frames == 1, name)
            self.assertRegex("nh_" + name, r"^[a-z0-9_]{2,32}$")

    def test_banners_are_animated_gifs(self):
        for key in banners.THEMES:
            data = banners.banner_bytes(key, **({"questions": quiz_bank.TOTAL} if key == "quiz" else {}))
            img = Image.open(BytesIO(data))
            self.assertEqual(img.format, "GIF")
            self.assertEqual(img.n_frames, banners.FRAMES)
            self.assertLess(len(data), 1_500_000, key)

    def test_generated_pictures(self):
        png = cards.profile_card("Zoé 🎃", "Vampire Noble", 3, 10, 200, "1 000", "1er / 3",
                                 [("crystal", "Quiz", "3")], None)
        self.assertEqual(Image.open(BytesIO(png)).size, (900, 360))
        pod = cards.podium([("A", "1", None)], "Test")
        self.assertEqual(Image.open(BytesIO(pod)).format, "PNG")
        wheel = Image.open(BytesIO(cards.wheel_gif(("t",), 0)))
        self.assertGreater(wheel.n_frames, 10)
        self.assertEqual(len(config.WHEEL), 8)
        reveal = Image.open(BytesIO(cards.card_reveal_gif(CARDS[0]["key"])))
        self.assertGreater(reveal.n_frames, 10)


if __name__ == "__main__":
    unittest.main()
