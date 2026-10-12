"""The shared GIF encoder keeps neon colours faithful, even ones that only flash for a moment."""
import unittest
from io import BytesIO

from PIL import Image, ImageDraw

from halloween.art.canvas import encode_gif


class GifQualityTest(unittest.TestCase):
    def test_brief_colours_survive(self):
        frames = []
        for i in range(20):
            img = Image.new("RGB", (200, 100), (14, 6, 24))
            d = ImageDraw.Draw(img)
            for x in range(0, 200, 2):  # a dark gradient that would eat the palette
                d.line((x, 60, x, 100), fill=(14 + x // 8, 6, 24 + x // 6))
            if i == 9:  # yellow sparks for a single frame in the middle
                d.ellipse((90, 20, 110, 40), fill=(255, 220, 60))
            d.line((10, 50, 190, 50), fill=(60, 230, 255), width=3)
            d.rectangle((i * 8, 80, i * 8 + 6, 86), fill=(200, 80, 255))  # something moves: no merged frames
            frames.append(img)
        gif = Image.open(BytesIO(encode_gif(frames, [60] * 20)))
        gif.seek(9)
        got = gif.convert("RGB")
        for xy, want in (((100, 30), (255, 220, 60)), ((100, 50), (60, 230, 255))):
            px = got.getpixel(xy)
            self.assertLess(max(abs(a - b) for a, b in zip(px, want)), 24, (xy, px))


if __name__ == "__main__":
    unittest.main()
