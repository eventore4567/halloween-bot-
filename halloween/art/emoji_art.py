"""Original emoji pack, drawn from scratch with Pillow.

Every icon is uploaded once as an *application emoji* (Developer Portal >
your app > Emojis), so it works in every server without Nitro and without
any server emoji slot. Animated icons are exported as GIF.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from .canvas import Canvas, Grad, gif_bytes, png_bytes

INK = (30, 16, 40)
WHITE = (255, 255, 255)
ORANGE = (247, 133, 36)
ORANGE_L = (255, 186, 82)
ORANGE_D = (205, 88, 22)
PURPLE = (139, 82, 224)
PURPLE_L = (196, 150, 255)
PURPLE_D = (84, 46, 150)
GREEN = (108, 214, 92)
GREEN_L = (178, 245, 128)
GREEN_D = (52, 140, 64)
GOLD = (255, 204, 64)
GOLD_L = (255, 238, 150)
GOLD_D = (206, 136, 26)
RED = (232, 62, 76)
RED_L = (255, 124, 124)
RED_D = (160, 30, 50)
BONE = (246, 238, 218)
BONE_D = (200, 186, 160)
GHOST = (250, 247, 255)
GHOST_D = (200, 192, 232)
TEAL = (96, 238, 214)
BLUE = (84, 166, 255)
BROWN = (150, 92, 52)
BROWN_D = (98, 56, 32)
GREY = (150, 150, 170)
NIGHT = (52, 34, 84)

OW = 4.0  # outline width used by most parts


# ---------------------------------------------------------------------------
# Characters & creatures
# ---------------------------------------------------------------------------

def pumpkin_body(c, face="happy", glow=1.0, cx=64, cy=72, s=1.0):
    def X(v): return cx + (v - 64) * s
    def Y(v): return cy + (v - 72) * s
    c.poly([(X(60), Y(32)), (X(62), Y(14)), (X(74), Y(10)), (X(72), Y(22)), (X(68), Y(34))],
           Grad(GREEN_L, GREEN_D), INK, OW * s)
    c.arc((X(66), Y(4), X(92), Y(28)), 120, 260, GREEN_D, 3.5 * s)
    for box in ((16, 34, 70, 116), (58, 34, 112, 116)):
        c.ellipse((X(box[0]), Y(box[1]), X(box[2]), Y(box[3])),
                  Grad(ORANGE_L, ORANGE_D, "radial", (0.4, 0.3)), INK, OW * s)
    c.ellipse((X(36), Y(32), X(92), Y(118)), Grad(ORANGE_L, ORANGE_D, "radial", (0.45, 0.3)), INK, OW * s)
    c.arc((X(30), Y(40), X(54), Y(110)), 110, 250, ORANGE_D, 3 * s)
    c.arc((X(74), Y(40), X(98), Y(110)), -70, 70, ORANGE_D, 3 * s)
    c.ellipse((X(44), Y(42), X(56), Y(56)), (255, 230, 170, 150))
    if face is None:
        return
    inner = tuple(round(v * glow + 90 * (1 - glow)) for v in (255, 214, 70))
    if face == "happy":
        c.poly([(X(32), Y(70)), (X(44), Y(54)), (X(52), Y(72))], inner, INK, 3 * s)
        c.poly([(X(76), Y(72)), (X(84), Y(54)), (X(96), Y(70))], inner, INK, 3 * s)
        c.poly([(X(30), Y(84)), (X(98), Y(84)), (X(88), Y(100)), (X(78), Y(94)), (X(70), Y(104)),
                (X(58), Y(104)), (X(50), Y(94)), (X(40), Y(100))], inner, INK, 3 * s)
    elif face == "angry":
        c.poly([(X(30), Y(58)), (X(54), Y(70)), (X(36), Y(76))], inner, INK, 3 * s)
        c.poly([(X(98), Y(58)), (X(74), Y(70)), (X(92), Y(76))], inner, INK, 3 * s)
        pts = [(X(28), Y(86))]
        for i in range(9):
            pts.append((X(28 + i * 9 + 4.5), Y(86 + (12 if i % 2 == 0 else 0))))
        pts += [(X(100), Y(86)), (X(86), Y(108)), (X(42), Y(108))]
        c.poly(pts, inner, INK, 3 * s)


def draw_pumpkin(c, t):
    pumpkin_body(c, "happy")


def draw_pumpkin_lit(c, t):
    flicker = 0.62 + 0.38 * math.sin(t * math.tau * 2) * math.sin(t * math.tau * 3 + 1)
    pumpkin_body(c, "happy", glow=flicker)


def draw_pumpkin_angry(c, t):
    pumpkin_body(c, "angry")


def ghost_shape(c, dy=0.0, wave=0.0, fill=None, face=True, blush=True):
    pts = [(24, 112 + dy)]
    # wavy tail
    for i in range(6):
        x = 24 + (i + 0.5) * 80 / 6
        y = 112 + dy + (-8 if i % 2 == 0 else 2) + 4 * math.sin(wave + i)
        pts.append((x, y))
    pts.append((104, 112 + dy))
    pts.append((104, 60 + dy))
    for k in range(13):
        a = math.radians(-k * 15)
        pts.append((64 + 40 * math.cos(a), 60 + dy + 46 * math.sin(a)))
    c.poly(pts, fill or Grad(GHOST, GHOST_D, "v"), INK, OW)
    c.ellipse((36, 24 + dy, 56, 40 + dy), (255, 255, 255, 200))
    if face:
        c.ellipse((42, 48 + dy, 56, 68 + dy), INK)
        c.ellipse((72, 48 + dy, 86, 68 + dy), INK)
        c.ellipse((46, 51 + dy, 51, 57 + dy), WHITE)
        c.ellipse((76, 51 + dy, 81, 57 + dy), WHITE)
        c.ellipse((58, 72 + dy, 70, 88 + dy), INK)
        if blush:
            c.ellipse((32, 68 + dy, 44, 76 + dy), (255, 150, 190, 200))
            c.ellipse((84, 68 + dy, 96, 76 + dy), (255, 150, 190, 200))


def draw_ghost(c, t):
    ghost_shape(c, dy=-4 * math.sin(t * math.tau) - 2, wave=t * math.tau)


def draw_ghost_static(c, t):
    ghost_shape(c)


def draw_bat(c, t):
    flap = math.sin(t * math.tau)
    bob = -3 * flap
    tip = 34 - 22 * flap
    for side in (-1, 1):
        def X(v): return 64 + side * v
        c.poly([(X(14), 62 + bob), (X(40), tip + bob), (X(62), 40 + bob + flap * 8), (X(58), 62 + bob),
                (X(50), 70 + bob), (X(42), 66 + bob), (X(32), 76 + bob), (X(26), 70 + bob), (X(16), 76 + bob)],
               Grad(PURPLE, PURPLE_D), INK, OW)
    c.ellipse((40, 44 + bob, 88, 94 + bob), Grad((110, 70, 180), NIGHT, "radial"), INK, OW)
    c.poly([(44, 52 + bob), (46, 30 + bob), (58, 46 + bob)], NIGHT, INK, 3)
    c.poly([(84, 52 + bob), (82, 30 + bob), (70, 46 + bob)], NIGHT, INK, 3)
    c.ellipse((49, 58 + bob, 61, 70 + bob), GOLD)
    c.ellipse((67, 58 + bob, 79, 70 + bob), GOLD)
    c.ellipse((53, 61 + bob, 58, 68 + bob), INK)
    c.ellipse((71, 61 + bob, 76, 68 + bob), INK)
    c.poly([(57, 78 + bob), (60, 86 + bob), (62, 78 + bob)], WHITE)
    c.poly([(66, 78 + bob), (68, 86 + bob), (71, 78 + bob)], WHITE)


def skull_shape(c, cx=64, cy=60, s=1.0, color=None, eyes=INK, glow_eyes=None):
    def X(v): return cx + (v - 64) * s
    def Y(v): return cy + (v - 60) * s
    col = color or Grad(BONE, BONE_D, "radial")
    c.rect((X(40), Y(76), X(88), Y(108)), col, INK, OW * s, radius=10 * s)
    c.ellipse((X(22), Y(14), X(106), Y(94)), col, INK, OW * s)
    c.rect((X(38), Y(78), X(90), Y(92)), col)
    c.ellipse((X(34), Y(46), X(58), Y(72)), eyes)
    c.ellipse((X(70), Y(46), X(94), Y(72)), eyes)
    if glow_eyes:
        c.ellipse((X(41), Y(53), X(51), Y(65)), glow_eyes)
        c.ellipse((X(77), Y(53), X(87), Y(65)), glow_eyes)
    c.poly([(X(64), Y(74)), (X(58), Y(86)), (X(70), Y(86))], eyes)
    for x in (52, 60, 68, 76):
        c.line([(X(x), Y(94)), (X(x), Y(106))], INK, 3 * s)
    c.ellipse((X(40), Y(24), X(58), Y(36)), (255, 255, 255, 170))


def draw_skull(c, t):
    skull_shape(c)


def draw_skull_fire(c, t):
    for i, col in enumerate(((150, 80, 255), (220, 120, 255))):
        k = 1 - i * 0.3
        pts = []
        for j in range(9):
            x = 20 + j * 11
            h = (36 + 14 * math.sin(j * 1.7 + t * math.tau * 2)) * k
            pts.append((x, 50 - h if j % 2 == 0 else 50 - h * 0.45))
        pts += [(108, 70), (20, 70)]
        c.poly(pts, col)
    skull_shape(c, cy=66, s=0.9, eyes=(60, 20, 90), glow_eyes=(170, 100, 255))


def draw_cauldron(c, t):
    for x, sign in ((30, -1), (98, 1)):
        c.poly([(x - 6, 96), (x + 6, 96), (x + sign * 10, 120), (x + sign * 2, 120)], (60, 56, 70), INK, 3)
    c.ellipse((14, 44, 114, 120), Grad((90, 86, 104), (34, 30, 44), "radial"), INK, OW)
    c.ellipse((10, 38, 118, 60), (60, 56, 72), INK, OW)
    c.ellipse((18, 42, 110, 58), Grad(GREEN_L, GREEN_D, "v"))
    c.ellipse((26, 72, 40, 92), (255, 255, 255, 60))
    for i in range(4):
        ph = (t + i / 4) % 1
        x = 34 + i * 18 + 4 * math.sin(ph * math.tau + i)
        y = 50 - ph * 44
        r = 5 + 4 * math.sin(ph * math.pi)
        c.circle(x, y, r, (GREEN_L[0], GREEN_L[1], GREEN_L[2], int(255 * (1 - ph * 0.7))), INK, 2.5)
    c.ellipse((40, 44, 56, 50), (255, 255, 255, 140))


def draw_crystal(c, t):
    c.poly([(30, 106), (98, 106), (88, 88), (40, 88)], Grad(GOLD_L, GOLD_D), INK, OW)
    c.rect((24, 104, 104, 118), Grad(GOLD, GOLD_D), INK, OW, radius=5)
    c.circle(64, 56, 42, Grad((214, 170, 255), (78, 36, 160), "radial", (0.4, 0.35)), INK, OW)
    for i in range(3):
        a = t * math.tau + i * math.tau / 3
        x, y = 64 + 22 * math.cos(a), 58 + 12 * math.sin(a)
        c.sparkle(x, y, 7 + 3 * math.sin(a * 2), (255, 255, 255, 230))
    c.ellipse((40, 26, 58, 40), (255, 255, 255, 170))


def draw_soul(c, t):
    fl = math.sin(t * math.tau)
    # flame drawn as a teardrop: point at the top, round at the bottom
    pts = [(64 + 6 * fl, 6), (84 + 3 * fl, 30), (100, 58)]
    for k in range(0, 181, 15):
        a = math.radians(k)
        pts.append((64 + 36 * math.cos(a), 78 + 36 * math.sin(a)))
    pts += [(28, 58), (40 + 3 * fl, 34), (46, 40), (52 + 4 * fl, 18)]
    c.poly(pts, Grad((190, 255, 246), (40, 170, 210), "v"), INK, OW)
    c.ellipse((38, 60, 90, 108), (200, 255, 250, 120))
    c.ellipse((46, 68, 58, 84), INK)
    c.ellipse((70, 68, 82, 84), INK)
    c.ellipse((49, 70, 54, 76), WHITE)
    c.ellipse((73, 70, 78, 76), WHITE)
    c.arc((54, 82, 74, 98), 20, 160, INK, 3.5)


def draw_spider(c, t):
    c.line([(64, 0), (64, 40)], (220, 220, 235), 2.5)
    for side in (-1, 1):
        for i, (a, b) in enumerate(((20, -10), (30, 6), (32, 24), (24, 40))):
            x1, y1 = 64 + side * 18, 66 + i * 6
            x2, y2 = 64 + side * (18 + a), 50 + b + i * 4
            x3, y3 = 64 + side * (24 + a + 8), y2 + 22
            c.line([(x1, y1), (x2, y2), (x3, y3)], INK, 5)
    c.ellipse((34, 54, 94, 112), Grad((80, 60, 100), (20, 14, 26), "radial"), INK, OW)
    c.ellipse((44, 34, 84, 66), Grad((90, 70, 110), (30, 20, 38), "radial"), INK, OW)
    for x in (54, 74):
        c.circle(x, 50, 7, RED)
        c.circle(x - 2, 48, 2.5, WHITE)
    c.poly([(54, 86), (64, 74), (74, 86), (64, 98)], RED)


def draw_web(c, t):
    col = (230, 230, 245)
    cx, cy = 10, 10
    for k in range(5):
        a = math.radians(k * 22.5)
        c.line([(cx, cy), (cx + 120 * math.cos(a), cy + 120 * math.sin(a))], col, 3)
    for r in (30, 56, 82, 108):
        pts = []
        for k in range(5):
            a = math.radians(k * 22.5)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        for p, q in zip(pts, pts[1:]):
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            mx -= (mx - cx) * 0.08
            my -= (my - cy) * 0.08
            c.line([p, (mx, my), q], col, 3)


def face_base(c, fill, ow=OW):
    c.ellipse((20, 26, 108, 118), fill, INK, ow)


def draw_vampire(c, t):
    c.poly([(8, 120), (24, 64), (64, 96), (104, 64), (120, 120)], Grad(RED, RED_D), INK, OW)
    face_base(c, Grad((246, 240, 250), (196, 186, 220), "radial"))
    c.poly([(20, 60), (36, 22), (64, 40), (92, 22), (108, 60), (90, 44), (64, 56), (38, 44)], (40, 30, 60), INK, OW)
    c.poly([(58, 42), (64, 56), (70, 42)], (40, 30, 60))
    for x in (46, 82):
        c.ellipse((x - 9, 62, x + 9, 78), WHITE, INK, 3)
        c.circle(x, 70, 5, RED)
    c.line([(36, 58), (54, 62)], INK, 3.5)
    c.line([(92, 58), (74, 62)], INK, 3.5)
    c.chord((44, 82, 84, 106), 0, 180, (120, 20, 40), INK, 3)
    c.poly([(52, 93), (56, 104), (60, 93)], WHITE)
    c.poly([(68, 93), (72, 104), (76, 93)], WHITE)


def draw_zombie(c, t):
    face_base(c, Grad((160, 222, 120), (84, 160, 80), "radial"))
    c.poly([(26, 52), (34, 26), (60, 20), (76, 30), (102, 30), (104, 54)], Grad((120, 90, 60), (70, 50, 30)), INK, OW)
    c.poly([(80, 46), (100, 42), (96, 58)], (238, 120, 140), INK, 3)
    c.line([(84, 44), (86, 54)], INK, 2)
    c.line([(90, 43), (92, 53)], INK, 2)
    c.circle(46, 72, 12, WHITE, INK, 3)
    c.circle(48, 74, 4.5, INK)
    c.line([(74, 64), (92, 80)], INK, 4.5)
    c.line([(92, 64), (74, 80)], INK, 4.5)
    pts = []
    for i in range(7):
        pts.append((44 + i * 7, 98 + (5 if i % 2 else -2)))
    c.line(pts, INK, 4)
    c.line([(32, 86), (40, 90)], (60, 120, 60), 3)


def draw_werewolf(c, t):
    fur = Grad((150, 120, 110), (80, 60, 60), "radial")
    for side in (-1, 1):
        c.poly([(64 + side * 18, 40), (64 + side * 44, 6), (64 + side * 44, 52)], fur, INK, OW)
        c.poly([(64 + side * 26, 38), (64 + side * 40, 18), (64 + side * 40, 44)], (230, 150, 150))
    c.poly([(16, 66), (26, 36), (64, 28), (102, 36), (112, 66), (104, 98), (64, 120), (24, 98)], fur, INK, OW)
    c.poly([(36, 84), (64, 70), (92, 84), (84, 112), (64, 120), (44, 112)], (210, 186, 170), INK, 3)
    for x in (44, 84):
        c.poly([(x - 12, 58), (x + 12, 58), (x, 70)], GOLD, INK, 3)
        c.circle(x, 62, 3.4, INK)
    c.line([(30, 50), (54, 56)], INK, 4)
    c.line([(98, 50), (74, 56)], INK, 4)
    c.ellipse((56, 76, 72, 88), INK)
    c.poly([(52, 98), (56, 110), (60, 100)], WHITE, INK, 2)
    c.poly([(68, 100), (72, 110), (76, 98)], WHITE, INK, 2)


def draw_witch(c, t):
    face_base(c, Grad((176, 236, 140), (90, 170, 90), "radial"))
    c.poly([(8, 56), (120, 56), (110, 46), (18, 46)], Grad(PURPLE, PURPLE_D), INK, OW)
    c.poly([(32, 48), (54, 6), (78, 2), (70, 16), (96, 48)], Grad(PURPLE, PURPLE_D), INK, OW)
    c.rect((32, 38, 96, 48), GOLD, INK, 3)
    c.rect((56, 36, 70, 50), (60, 40, 20), INK, 2.5)
    for x in (46, 82):
        c.circle(x, 74, 8, WHITE, INK, 3)
        c.circle(x + 1, 75, 3.5, INK)
    c.poly([(64, 74), (82, 94), (62, 92)], (120, 200, 110), INK, 3)
    c.circle(78, 96, 3, (120, 100, 60))
    c.arc((44, 88, 80, 112), 20, 160, INK, 4)


def draw_mummy(c, t):
    face_base(c, Grad(BONE, BONE_D, "radial"))
    for y, tilt in ((36, 4), (52, -5), (90, 6), (104, -4)):
        c.line([(22, y), (106, y + tilt)], BONE_D, 4)
        c.line([(22, y + 7), (106, y + 7 + tilt)], (255, 255, 255, 120), 2)
    c.rect((24, 60, 104, 84), (40, 26, 30), INK, 3, radius=6)
    c.circle(46, 72, 8, (255, 220, 80))
    c.circle(84, 72, 6, (255, 220, 80))
    c.circle(46, 72, 3, INK)
    c.circle(84, 72, 2.5, INK)


def draw_reaper(c, t):
    c.line([(108, 4), (98, 124)], (130, 90, 56), 6)
    c.poly([(108, 4), (60, 6), (24, 26), (72, 18), (104, 22)], Grad((230, 236, 245), (130, 140, 160)), INK, 3.5)
    c.poly([(14, 124), (24, 50), (64, 14), (104, 50), (114, 124)], Grad((70, 60, 90), (20, 16, 30)), INK, OW)
    c.ellipse((34, 42, 94, 106), (10, 6, 16))
    skull_shape(c, cx=64, cy=78, s=0.52)


def draw_demon(c, t):
    for side in (-1, 1):
        c.poly([(64 + side * 26, 36), (64 + side * 50, 4), (64 + side * 38, 44)], Grad(BONE, BONE_D), INK, OW)
    face_base(c, Grad(RED_L, RED_D, "radial"))
    c.line([(32, 56), (56, 66)], INK, 5)
    c.line([(96, 56), (72, 66)], INK, 5)
    for x in (46, 82):
        c.poly([(x - 10, 64), (x + 10, 64), (x, 76)], GOLD, INK, 3)
    c.arc((36, 66, 92, 106), 20, 160, INK, 5)
    c.poly([(48, 96), (52, 104), (56, 97)], WHITE)
    c.poly([(72, 97), (76, 104), (80, 96)], WHITE)


def draw_hunter(c, t):
    face_base(c, Grad((255, 216, 180), (220, 160, 120), "radial"))
    c.poly([(6, 52), (122, 52), (108, 40), (20, 40)], Grad((140, 90, 50), (80, 50, 30)), INK, OW)
    c.poly([(30, 44), (36, 12), (92, 12), (98, 44)], Grad((140, 90, 50), (80, 50, 30)), INK, OW)
    c.rect((32, 30, 96, 40), RED_D, INK, 2.5)
    for x in (48, 80):
        c.circle(x, 70, 5, INK)
    c.line([(38, 60), (56, 58)], INK, 4)
    c.line([(90, 60), (72, 58)], INK, 4)
    c.poly([(40, 88), (64, 82), (88, 88), (78, 94), (64, 90), (50, 94)], (110, 70, 40), INK, 2.5)
    c.line([(54, 104), (74, 104)], INK, 3.5)
    # wooden stake
    c.poly([(98, 120), (110, 76), (120, 80), (112, 124)], Grad((200, 150, 90), (130, 90, 50)), INK, 3)


def draw_frog(c, t):
    c.ellipse((14, 44, 114, 116), Grad(GREEN_L, GREEN_D, "radial"), INK, OW)
    for x in (38, 90):
        c.circle(x, 42, 20, Grad(GREEN_L, GREEN, "radial"), INK, OW)
        c.circle(x, 42, 12, WHITE, INK, 2.5)
        c.ellipse((x - 4, 34, x + 4, 50), INK)
    c.arc((30, 64, 98, 104), 20, 160, INK, 4.5)
    c.circle(40, 84, 6, (255, 150, 170, 170))
    c.circle(88, 84, 6, (255, 150, 170, 170))


def draw_eye(c, t):
    look = math.sin(t * math.tau) * 10
    blink = 1.0
    if 0.82 < t < 0.92:
        blink = abs((t - 0.87) / 0.05)
    h = 40 * max(0.08, blink)
    c.ellipse((10, 64 - h, 118, 64 + h), Grad(WHITE, (226, 214, 236), "radial"), INK, OW)
    if blink > 0.3:
        for a in (200, 230, 320, 340, 150):
            r = math.radians(a)
            c.line([(64 + 50 * math.cos(r), 64 + 30 * math.sin(r)), (64 + 30 * math.cos(r), 64 + 18 * math.sin(r))],
                   (232, 80, 90), 2)
        c.circle(64 + look, 64, 22 * min(1, blink * 1.3), Grad(GREEN_L, (40, 150, 80), "radial"), INK, 3)
        c.ellipse((64 + look - 5, 64 - 14, 64 + look + 5, 64 + 14), INK)
        c.circle(64 + look - 9, 56, 5, (255, 255, 255, 220))


def draw_bone(c, t):
    for (x, y) in ((24, 34), (38, 22), (90, 106), (104, 94)):
        c.circle(x, y, 16, Grad(BONE, BONE_D, "radial"), INK, OW)
    c.poly([(30, 40), (44, 28), (98, 88), (84, 100)], Grad(BONE, BONE_D, "d"), INK, OW)
    for (x, y) in ((24, 34), (38, 22), (90, 106), (104, 94)):
        c.circle(x, y, 13, Grad(BONE, BONE_D, "radial"))
    c.poly([(32, 40), (44, 30), (96, 88), (84, 98)], Grad(BONE, BONE_D, "d"))


def draw_mushroom(c, t):
    c.rect((48, 66, 80, 118), Grad(BONE, BONE_D, "h"), INK, OW, radius=12)
    c.chord((8, 14, 120, 106), 180, 360, Grad((206, 120, 255), PURPLE_D, "radial"), INK, OW)
    c.line([(12, 60), (116, 60)], INK, OW)
    for (x, y, r) in ((40, 36, 9), (68, 26, 7), (90, 42, 10), (60, 48, 5)):
        c.circle(x, y, r, (200, 255, 150))
    c.circle(58, 92, 4, INK)
    c.circle(72, 92, 4, INK)


def draw_feather(c, t):
    pts = [(100, 10), (114, 20), (80, 84), (40, 116), (30, 112), (54, 70)]
    c.poly(pts, Grad((90, 80, 140), (20, 16, 40), "d"), INK, OW)
    c.line([(108, 14), (24, 120)], (210, 200, 240), 3)
    for k in range(5):
        y = 40 + k * 14
        c.line([(96 - k * 12, y - 18), (82 - k * 12, y - 2)], (60, 50, 100), 2)


def draw_fang(c, t):
    c.poly([(26, 18), (102, 18), (96, 56), (78, 112), (66, 118), (54, 70), (40, 56)], Grad(WHITE, (210, 210, 230), "h"), INK, OW)
    c.ellipse((40, 22, 60, 34), (255, 255, 255, 220))
    drop = 8 * ((t * 2) % 1)
    c.circle(72, 104 + drop, 8, RED, INK, 3)
    c.poly([(66, 100 + drop), (72, 88 + drop), (78, 100 + drop)], RED)


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

def draw_candy(c, t):
    for side in (-1, 1):
        c.poly([(64 + side * 24, 64), (64 + side * 58, 34), (64 + side * 50, 64), (64 + side * 58, 94)],
               Grad(PURPLE_L, PURPLE_D), INK, OW)
        c.line([(64 + side * 46, 52), (64 + side * 52, 64), (64 + side * 46, 76)], PURPLE_D, 2.5, cap=False)
    c.circle(64, 64, 32, Grad(ORANGE_L, ORANGE_D, "radial"), INK, OW)
    for k in range(3):
        c.arc((44, 44, 84, 84), k * 120 + 20, k * 120 + 90, WHITE, 6)
    c.circle(64, 64, 8, (255, 240, 220))
    c.ellipse((44, 40, 60, 52), (255, 255, 255, 190))


def draw_candy_bag(c, t):
    c.poly([(34, 34), (94, 34), (112, 108), (100, 120), (28, 120), (16, 108)], Grad(ORANGE_L, ORANGE_D, "radial"), INK, OW)
    c.poly([(30, 34), (40, 12), (52, 24), (64, 8), (76, 24), (88, 12), (98, 34)], Grad(ORANGE, ORANGE_D), INK, OW)
    c.rect((30, 30, 98, 40), PURPLE, INK, 3, radius=4)
    c.poly([(44, 66), (52, 54), (58, 68)], INK)
    c.poly([(70, 68), (76, 54), (84, 66)], INK)
    c.poly([(40, 82), (88, 82), (80, 98), (64, 92), (48, 98)], INK)
    c.circle(26, 26, 9, Grad(PURPLE_L, PURPLE), INK, 3)
    c.circle(106, 20, 8, Grad(GREEN_L, GREEN), INK, 3)


def draw_lollipop(c, t):
    c.rect((60, 70, 70, 124), Grad(WHITE, BONE_D, "h"), INK, 3, radius=4)
    c.circle(64, 50, 40, Grad(PURPLE_L, PURPLE_D, "radial"), INK, OW)
    for k in range(4):
        c.arc((34 + k * 7, 20 + k * 7, 94 - k * 7, 80 - k * 7), k * 90, k * 90 + 200, GREEN_L, 6)
    skull_shape(c, cx=64, cy=50, s=0.36)


def draw_trophy(c, t):
    for side in (-1, 1):
        c.arc((64 + side * 36 - 18, 22, 64 + side * 36 + 18, 62), 0, 360, INK, 9)
        c.arc((64 + side * 36 - 18, 22, 64 + side * 36 + 18, 62), 0, 360, GOLD_D, 4.5)
    c.poly([(24, 14), (104, 14), (100, 46), (86, 72), (70, 82), (58, 82), (42, 72), (28, 46)], Grad(GOLD_L, GOLD_D, "h"), INK, OW)
    c.rect((54, 80, 74, 98), Grad(GOLD, GOLD_D), INK, OW)
    c.rect((34, 96, 94, 118), Grad((120, 70, 200), PURPLE_D), INK, OW, radius=4)
    c.rect((48, 102, 80, 110), GOLD_L, radius=2)
    c.star(64, 42, 15, 6.5, fill=WHITE)
    c.ellipse((34, 20, 46, 40), (255, 255, 255, 150))


def draw_medal(c, n, metal):
    c.poly([(30, 6), (54, 6), (70, 56), (46, 56)], Grad(PURPLE_L, PURPLE), INK, 3.5)
    c.poly([(98, 6), (74, 6), (58, 56), (82, 56)], Grad((255, 140, 100), ORANGE_D), INK, 3.5)
    c.circle(64, 82, 36, Grad(metal[0], metal[1], "radial"), INK, OW)
    c.circle(64, 82, 27, None, metal[1], 3)
    c.text((64, 84), str(n), "lilita", 42, WHITE, stroke=3, stroke_fill=metal[2])
    c.ellipse((42, 58, 56, 70), (255, 255, 255, 150))


def draw_medal1(c, t):
    draw_medal(c, 1, (GOLD_L, GOLD_D, (150, 90, 10)))


def draw_medal2(c, t):
    draw_medal(c, 2, ((245, 248, 255), (150, 160, 185), (90, 96, 120)))


def draw_medal3(c, t):
    draw_medal(c, 3, ((255, 190, 140), (184, 104, 52), (110, 60, 30)))


def draw_chest(c, t):
    c.rect((12, 56, 116, 116), Grad((190, 120, 70), BROWN_D), INK, OW, radius=6)
    c.chord((12, 20, 116, 92), 180, 360, Grad((210, 140, 80), BROWN), INK, OW)
    c.rect((12, 52, 116, 62), Grad(GOLD_L, GOLD_D), INK, 3)
    for x in (30, 98):
        c.rect((x - 6, 30, x + 6, 116), Grad(GOLD_L, GOLD_D, "h"), INK, 3)
    c.rect((52, 52, 76, 80), Grad(GOLD_L, GOLD_D), INK, 3.5, radius=4)
    c.circle(64, 63, 4, INK)
    c.poly([(62, 64), (66, 64), (67, 74), (61, 74)], INK)


def draw_gift(c, t):
    c.rect((18, 56, 110, 118), Grad(PURPLE_L, PURPLE_D), INK, OW, radius=4)
    c.rect((12, 40, 116, 60), Grad(PURPLE_L, PURPLE), INK, OW, radius=4)
    c.rect((54, 40, 74, 118), Grad(ORANGE_L, ORANGE_D, "h"), INK, 3.5)
    for side in (-1, 1):
        c.poly([(64, 40), (64 + side * 40, 12), (64 + side * 46, 36)], Grad(ORANGE_L, ORANGE_D), INK, OW)
    c.circle(64, 38, 10, Grad(ORANGE_L, ORANGE), INK, 3.5)
    c.sparkle(100, 82, 9, WHITE)


def draw_star(c, t):
    c.star(64, 68, 56, 24, fill=Grad(GOLD_L, GOLD_D, "radial"), outline=INK, width=OW)
    c.circle(54, 66, 4.5, INK)
    c.circle(74, 66, 4.5, INK)
    c.arc((56, 70, 72, 84), 20, 160, INK, 3)


def draw_sparkle(c, t):
    for i, (x, y, r) in enumerate(((52, 60, 40), (100, 28, 18), (100, 98, 14))):
        k = 0.65 + 0.35 * math.sin(t * math.tau + i * 2.1)
        c.sparkle(x, y, r * k, Grad(GOLD_L, GOLD, "radial"))
    c.outline(INK, 3)


def draw_fire(c, t):
    f = math.sin(t * math.tau)
    g = math.sin(t * math.tau * 2 + 1)
    def flame(scale, cols):
        pts = [(64 + 10 * f * scale, 120 - 112 * scale + 4 * g)]
        pts += [(64 + 30 * scale + 6 * g * scale, 120 - 70 * scale), (64 + 22 * scale, 120 - 84 * scale)]
        pts += [(64 + 44 * scale, 120 - 46 * scale)]
        for k in range(0, 181, 15):
            a = math.radians(k)
            pts.append((64 + 44 * scale * math.cos(a), 120 - 40 * scale + 34 * scale * math.sin(a)))
        pts += [(64 - 40 * scale, 120 - 58 * scale), (64 - 26 * scale - 6 * f * scale, 120 - 92 * scale),
                (64 - 14 * scale, 120 - 66 * scale)]
        c.poly(pts, Grad(*cols, "v"), INK if scale == 1 else None, OW if scale == 1 else 0)
    flame(1.0, ((255, 150, 40), (230, 50, 40)))
    flame(0.68, ((255, 240, 120), (255, 150, 40)))
    flame(0.36, ((255, 255, 230), (255, 230, 120)))


def draw_heart(c, t):
    beat = 1 + 0.06 * math.sin(t * math.tau * 2)
    pts = []
    for k in range(0, 360, 6):
        a = math.radians(k)
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((64 + x * 3.3 * beat, 62 + y * 3.3 * beat))
    c.poly(pts, Grad(RED_L, RED_D, "radial"), INK, OW)
    c.ellipse((32, 34, 50, 48), (255, 255, 255, 170))


def draw_lock(c, t):
    c.arc((34, 8, 94, 70), 180, 360, INK, 15)
    c.arc((34, 8, 94, 70), 180, 360, Grad((220, 220, 235), (130, 130, 150)), 8)
    c.rect((32, 38, 40, 56), (180, 180, 200), INK, 2)
    c.rect((88, 38, 96, 56), (180, 180, 200), INK, 2)
    c.rect((20, 50, 108, 118), Grad(GOLD_L, GOLD_D, "radial"), INK, OW, radius=12)
    c.circle(64, 78, 9, INK)
    c.poly([(60, 80), (68, 80), (70, 100), (58, 100)], INK)


def draw_check(c, t):
    c.circle(64, 64, 54, Grad(GREEN_L, GREEN_D, "radial"), INK, OW)
    c.line([(36, 66), (56, 86), (94, 44)], INK, 15)
    c.line([(36, 66), (56, 86), (94, 44)], WHITE, 9)


def draw_cross(c, t):
    c.circle(64, 64, 54, Grad(RED_L, RED_D, "radial"), INK, OW)
    for a, b in (((42, 42), (86, 86)), ((86, 42), (42, 86))):
        c.line([a, b], INK, 15)
    for a, b in (((42, 42), (86, 86)), ((86, 42), (42, 86))):
        c.line([a, b], WHITE, 9)


def draw_question(c, t):
    c.circle(64, 64, 54, Grad(PURPLE_L, PURPLE_D, "radial"), INK, OW)
    c.text((64, 68), "?", "lilita", 78, GOLD_L, stroke=4, stroke_fill=INK)


def draw_hourglass(c, t):
    sand = (232, 180, 90)
    c.rect((22, 6, 106, 20), Grad((190, 120, 70), BROWN_D), INK, OW, radius=4)
    c.rect((22, 108, 106, 122), Grad((190, 120, 70), BROWN_D), INK, OW, radius=4)
    glass = [(32, 20), (96, 20), (96, 30), (70, 62), (70, 66), (96, 98), (96, 108), (32, 108), (32, 98), (58, 66),
             (58, 62), (32, 30)]
    c.poly(glass, (200, 230, 255, 90), INK, OW)
    level = t
    top = 24 + 34 * level
    if level < 0.98:
        w = (62 - top) / 34 * 30
        c.poly([(64 - w, top), (64 + w, top), (64, 63)], sand)
    c.line([(64, 62), (64, 104)], sand, 3)
    hb = 104 - 30 * level
    w2 = (104 - hb) / 30 * 30
    c.poly([(64 - w2 - 2, 104), (64 + w2 + 2, 104), (64, hb)], sand)
    c.line([(40, 26), (44, 30)], (255, 255, 255, 180), 3)


def draw_book(c, t):
    c.rect((22, 12, 108, 118), Grad((70, 40, 120), (30, 16, 60)), INK, OW, radius=6)
    c.rect((26, 104, 108, 116), BONE, INK, 2.5, radius=3)
    c.rect((18, 10, 100, 110), Grad(PURPLE_L, PURPLE_D, "radial"), INK, OW, radius=8)
    c.circle(59, 58, 26, None, GOLD, 4)
    c.star(59, 59, 24, 9.5, fill=None, outline=GOLD, width=3.5)
    c.circle(59, 59, 6, GOLD_L)
    c.poly([(84, 104), (84, 126), (90, 120), (96, 126), (96, 104)], RED, INK, 2.5)
    for y in (18, 102):
        c.rect((22, y - 4, 32, y + 4), GOLD, INK, 2)


def potion(c, t, liquid, liquid_d):
    c.rect((50, 6, 78, 24), Grad((200, 150, 100), BROWN), INK, OW, radius=4)
    c.rect((54, 22, 74, 44), (226, 238, 255, 190), INK, OW)
    c.circle(64, 78, 44, Grad((240, 246, 255, 215), (170, 190, 230, 200), "radial"), INK, OW)
    wave = 4 * math.sin(t * math.tau)
    from PIL import ImageChops, ImageDraw
    body = c._new_mask()
    ImageDraw.Draw(body).ellipse(c._b((24, 38, 104, 118)), fill=255)
    below = c._new_mask()
    ImageDraw.Draw(below).polygon(c._p([(0, 78 + wave), (128, 78 - wave), (128, 128), (0, 128)]), fill=255)
    c.paint(ImageChops.multiply(body, below), Grad(liquid, liquid_d, "radial"))
    c.line([(30, 78 + wave * 0.8), (98, 78 - wave * 0.8)], (255, 255, 255, 170), 3)
    for i in range(3):
        ph = (t + i / 3) % 1
        c.circle(50 + i * 14, 108 - ph * 26, 3 + i, (255, 255, 255, int(200 * (1 - ph))))
    c.ellipse((34, 50, 50, 70), (255, 255, 255, 190))


def make_potion(liquid, liquid_d):
    return lambda c, t: potion(c, t, liquid, liquid_d)


def draw_wheel(c, t):
    cols = [ORANGE, PURPLE, GREEN, RED, GOLD, (90, 160, 255), (255, 120, 190), (60, 40, 100)]
    rot = t * 360 / 8
    c.circle(64, 66, 56, INK)
    for i, col in enumerate(cols):
        c.pie((12, 14, 116, 118), i * 45 + rot, (i + 1) * 45 + rot, col)
    for i in range(8):
        a = math.radians(i * 45 + rot)
        c.line([(64, 66), (64 + 52 * math.cos(a), 66 + 52 * math.sin(a))], INK, 2.5)
    c.circle(64, 66, 52, None, Grad(GOLD_L, GOLD_D), 6)
    c.circle(64, 66, 12, Grad(GOLD_L, GOLD_D, "radial"), INK, 3)
    c.poly([(52, 0), (76, 0), (64, 22)], Grad(RED_L, RED_D), INK, 3.5)


def draw_dice(c, t):
    c.rect((14, 14, 114, 114), Grad(WHITE, (210, 200, 230), "radial"), INK, OW, radius=22)
    for x, y in ((38, 38), (90, 38), (64, 64), (38, 90), (90, 90)):
        c.circle(x, y, 10, Grad(PURPLE_L, PURPLE_D, "radial"))


def draw_key(c, t):
    c.circle(36, 44, 26, Grad(GOLD_L, GOLD_D, "radial"), INK, OW)
    c.circle(36, 44, 10, (0, 0, 0, 0))
    c.circle(36, 44, 11, INK)
    c.poly([(54, 58), (62, 50), (118, 106), (110, 114)], Grad(GOLD_L, GOLD_D, "d"), INK, OW)
    c.poly([(96, 100), (108, 88), (116, 96), (104, 108)], GOLD, INK, 3)
    c.poly([(82, 86), (92, 76), (100, 84), (90, 94)], GOLD, INK, 3)


def draw_crown(c, t):
    c.poly([(12, 104), (16, 34), (42, 66), (64, 18), (86, 66), (112, 34), (116, 104)], Grad(GOLD_L, GOLD_D, "radial"), INK, OW)
    c.rect((12, 96, 116, 116), Grad(GOLD, GOLD_D), INK, OW, radius=4)
    for x, col in ((40, RED), (64, PURPLE_L), (88, GREEN)):
        c.circle(x, 106, 6, col, INK, 2)
    for x, y in ((16, 34), (64, 18), (112, 34)):
        c.circle(x, y, 7, Grad(WHITE, GOLD), INK, 2.5)
    c.ellipse((28, 70, 40, 90), (255, 255, 255, 140))


def draw_shield(c, t):
    pts = [(64, 8), (112, 22), (108, 72), (64, 122), (20, 72), (16, 22)]
    c.poly(pts, Grad(GOLD_L, GOLD_D), INK, OW)
    c.poly([(64, 20), (100, 30), (98, 70), (64, 108), (30, 70), (28, 30)], Grad(PURPLE_L, PURPLE_D, "radial"))
    c.star(64, 62, 22, 9, fill=GOLD_L, outline=INK, width=3)


def draw_coffin(c, t):
    pts = [(46, 6), (82, 6), (104, 36), (88, 122), (40, 122), (24, 36)]
    c.poly(pts, Grad((160, 100, 60), BROWN_D, "radial"), INK, OW)
    c.poly([(48, 14), (80, 14), (96, 38), (82, 114), (46, 114), (32, 38)], None, (210, 150, 90), 2.5)
    c.rect((59, 30, 69, 86), GOLD, INK, 2.5)
    c.rect((46, 44, 82, 54), GOLD, INK, 2.5)


def draw_tomb(c, t):
    c.rect((10, 106, 118, 122), Grad((110, 180, 90), (50, 110, 60)), INK, OW, radius=6)
    c.chord((22, 8, 106, 92), 180, 360, Grad((200, 200, 216), (120, 120, 140), "radial"), INK, OW)
    c.rect((22, 48, 106, 112), Grad((190, 190, 206), (110, 110, 130), "v"), INK, OW)
    c.rect((25, 46, 103, 54), (190, 190, 206))
    c.text((64, 62), "RIP", "lilita", 30, (70, 70, 90))
    c.line([(40, 84), (54, 92), (48, 100)], (90, 90, 110), 2.5)
    c.ellipse((32, 22, 50, 34), (255, 255, 255, 120))


def draw_moon(c, t):
    c.circle(64, 64, 52, Grad((255, 248, 200), (240, 200, 90), "radial"), INK, OW)
    c.circle(92, 46, 44, (0, 0, 0, 0))
    m = c._new_mask()
    from PIL import ImageDraw
    ImageDraw.Draw(m).ellipse(c._b((50, 2, 134, 86)), fill=255)
    # cut the crescent out of the full moon
    alpha = c.img.getchannel("A")
    from PIL import ImageChops
    c.img.putalpha(ImageChops.subtract(alpha, m))
    c.circle(42, 82, 6, (230, 190, 90))
    c.circle(30, 56, 4, (230, 190, 90))


def draw_candle(c, t):
    f = math.sin(t * math.tau * 2)
    c.rect((40, 50, 88, 120), Grad(WHITE, (220, 210, 236), "h"), INK, OW, radius=6)
    c.poly([(40, 56), (88, 56), (88, 70), (80, 82), (74, 70), (64, 92), (56, 70), (46, 78), (40, 68)], WHITE, INK, 3)
    c.line([(64, 50), (64, 40)], INK, 3)
    pts = [(64 + 4 * f, 6), (78, 32), (74, 44), (64, 48), (54, 44), (50, 32)]
    c.poly(pts, Grad((255, 230, 120), (255, 120, 40)), INK, 3)
    c.ellipse((60, 30, 68, 44), (255, 255, 230))


def draw_gem(c, t):
    pts = [(30, 30), (98, 30), (118, 56), (64, 118), (10, 56)]
    c.poly(pts, Grad((214, 160, 255), (100, 40, 190), "radial"), INK, OW)
    c.poly([(30, 30), (46, 56), (82, 56), (98, 30)], (230, 200, 255))
    c.line([(10, 56), (118, 56)], INK, 3)
    c.line([(46, 56), (64, 118), (82, 56)], INK, 2.5)
    k = 0.6 + 0.4 * math.sin(t * math.tau)
    c.sparkle(96, 22, 14 * k, WHITE)


def draw_lightning(c, t):
    c.poly([(72, 4), (22, 72), (58, 72), (44, 124), (106, 48), (68, 48), (86, 4)], Grad(GOLD_L, ORANGE, "v"), INK, OW)


def draw_scroll(c, t):
    c.rect((26, 22, 102, 106), Grad(BONE, BONE_D, "h"), INK, OW)
    for y in (22, 106):
        c.rect((14, y - 10, 114, y + 10), Grad((236, 214, 170), (180, 150, 100), "v"), INK, OW, radius=10)
    for y in (46, 60, 74, 88):
        c.line([(38, y), (90, y)], (150, 120, 90), 3)


def draw_joker(c, t):
    c.rect((20, 10, 92, 112), Grad(WHITE, (220, 210, 236)), INK, OW, radius=10)
    c.rect((36, 18, 108, 120), Grad(PURPLE_L, PURPLE_D, "radial"), INK, OW, radius=10)
    c.text((72, 70), "50", "lilita", 38, GOLD_L, stroke=3, stroke_fill=INK)


def draw_cookie(c, t):  # spooky gingerbread skull cookie
    c.circle(64, 64, 52, Grad((230, 170, 100), (170, 100, 50), "radial"), INK, OW)
    for x, y in ((40, 40), (88, 44), (44, 90), (90, 86), (64, 30)):
        c.circle(x, y, 6, (90, 50, 30))
    c.ellipse((46, 56, 82, 82), (255, 255, 255, 230))
    c.circle(57, 66, 4, INK)
    c.circle(71, 66, 4, INK)


def draw_tick_on(c, t):
    bar(c, "m", True)


def bar(c, part, on):
    top, bot = 44, 84
    fill = Grad((255, 196, 80), (240, 96, 40), "v") if on else Grad((84, 62, 120), (52, 36, 80), "v")
    hl = (255, 255, 255, 110) if on else (255, 255, 255, 30)
    if part == "l":
        c.rect((6, top, 140, bot), fill, INK, 4, radius=20)
        c.rect((20, top + 7, 140, top + 13), hl, radius=3)
    elif part == "r":
        c.rect((-12, top, 122, bot), fill, INK, 4, radius=20)
        c.rect((-12, top + 7, 106, top + 13), hl, radius=3)
    else:
        c.rect((-12, top, 140, bot), fill, INK, 4)
        c.rect((-12, top + 7, 140, top + 13), hl)


def make_bar(part, on):
    return lambda c, t: bar(c, part, on)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Spec:
    draw: Callable
    fallback: str
    frames: int = 1
    duration: int = 90
    outline: bool = True


PREFIX = "nh_"
EMOJIS: dict[str, Spec] = {
    # creatures
    "pumpkin": Spec(draw_pumpkin, "🎃"),
    "pumpkin_lit": Spec(draw_pumpkin_lit, "🎃", frames=10, duration=90),
    "pumpkin_angry": Spec(draw_pumpkin_angry, "🎃"),
    "ghost": Spec(draw_ghost, "👻", frames=12, duration=80),
    "ghost_still": Spec(draw_ghost_static, "👻"),
    "bat": Spec(draw_bat, "🦇", frames=8, duration=60),
    "skull": Spec(draw_skull, "💀"),
    "skull_fire": Spec(draw_skull_fire, "☠️", frames=8, duration=90),
    "vampire": Spec(draw_vampire, "🧛"),
    "zombie": Spec(draw_zombie, "🧟"),
    "werewolf": Spec(draw_werewolf, "🐺"),
    "witch": Spec(draw_witch, "🧙"),
    "mummy": Spec(draw_mummy, "🤕"),
    "reaper": Spec(draw_reaper, "💀"),
    "demon": Spec(draw_demon, "😈"),
    "hunter": Spec(draw_hunter, "🏹"),
    "spider": Spec(draw_spider, "🕷️"),
    "web": Spec(draw_web, "🕸️", outline=False),
    "frog": Spec(draw_frog, "🐸"),
    "eye": Spec(draw_eye, "👁️", frames=16, duration=90),
    "bone": Spec(draw_bone, "🦴"),
    "mushroom": Spec(draw_mushroom, "🍄"),
    "feather": Spec(draw_feather, "🪶"),
    "fang": Spec(draw_fang, "🩸", frames=8, duration=110),
    "soul": Spec(draw_soul, "🔥", frames=10, duration=80),
    # items
    "candy": Spec(draw_candy, "🍬"),
    "candy_bag": Spec(draw_candy_bag, "🎒"),
    "lollipop": Spec(draw_lollipop, "🍭"),
    "cookie": Spec(draw_cookie, "🍪"),
    "cauldron": Spec(draw_cauldron, "🧪", frames=12, duration=80),
    "crystal": Spec(draw_crystal, "🔮", frames=12, duration=90),
    "trophy": Spec(draw_trophy, "🏆"),
    "medal1": Spec(draw_medal1, "🥇"),
    "medal2": Spec(draw_medal2, "🥈"),
    "medal3": Spec(draw_medal3, "🥉"),
    "chest": Spec(draw_chest, "🧰"),
    "gift": Spec(draw_gift, "🎁"),
    "star": Spec(draw_star, "⭐"),
    "sparkle": Spec(draw_sparkle, "✨", frames=10, duration=90, outline=False),
    "fire": Spec(draw_fire, "🔥", frames=8, duration=80),
    "heart": Spec(draw_heart, "❤️", frames=10, duration=80),
    "lock": Spec(draw_lock, "🔒"),
    "check": Spec(draw_check, "✅"),
    "cross": Spec(draw_cross, "❌"),
    "question": Spec(draw_question, "❓"),
    "hourglass": Spec(draw_hourglass, "⏳", frames=16, duration=120),
    "book": Spec(draw_book, "📖"),
    "potion_red": Spec(make_potion((255, 110, 120), (180, 20, 50)), "🧪", frames=10, duration=100),
    "potion_green": Spec(make_potion((170, 255, 120), (40, 150, 60)), "🧪", frames=10, duration=100),
    "potion_blue": Spec(make_potion((130, 210, 255), (30, 90, 200)), "🧪", frames=10, duration=100),
    "potion_purple": Spec(make_potion((220, 160, 255), (100, 40, 180)), "🧪", frames=10, duration=100),
    "potion_gold": Spec(make_potion((255, 240, 140), (220, 140, 20)), "🧪", frames=10, duration=100),
    "wheel": Spec(draw_wheel, "🎡", frames=8, duration=70),
    "dice": Spec(draw_dice, "🎲"),
    "key": Spec(draw_key, "🗝️"),
    "crown": Spec(draw_crown, "👑"),
    "shield": Spec(draw_shield, "🛡️"),
    "coffin": Spec(draw_coffin, "⚰️"),
    "tomb": Spec(draw_tomb, "🪦"),
    "moon": Spec(draw_moon, "🌙"),
    "candle": Spec(draw_candle, "🕯️", frames=8, duration=90),
    "gem": Spec(draw_gem, "💎", frames=10, duration=100),
    "lightning": Spec(draw_lightning, "⚡"),
    "scroll": Spec(draw_scroll, "📜"),
    "joker": Spec(draw_joker, "🃏"),
    # progress bar pieces
    "bar_l1": Spec(make_bar("l", True), "🟧", outline=False),
    "bar_m1": Spec(make_bar("m", True), "🟧", outline=False),
    "bar_r1": Spec(make_bar("r", True), "🟧", outline=False),
    "bar_l0": Spec(make_bar("l", False), "⬛", outline=False),
    "bar_m0": Spec(make_bar("m", False), "⬛", outline=False),
    "bar_r0": Spec(make_bar("r", False), "⬛", outline=False),
}


def render_frame(name: str, t: float = 0.0, size: int = 128):
    spec = EMOJIS[name]
    c = Canvas(size, size, ss=4)
    if size != 128:
        # draw at 128 units scaled into the requested size
        c = Canvas(128, 128, ss=max(1, round(4 * size / 128)))
    spec.draw(c, t)
    if spec.outline:
        c.outline((24, 12, 32), 2.2)
    img = c.result()
    if img.size != (size, size):
        from PIL import Image
        img = img.resize((size, size), Image.LANCZOS)
    return img


@lru_cache(maxsize=None)
def render_emoji(name: str) -> bytes:
    """Bytes ready for ``create_application_emoji`` (PNG or animated GIF)."""
    spec = EMOJIS[name]
    if spec.frames == 1:
        return png_bytes(render_frame(name))
    frames = [render_frame(name, i / spec.frames) for i in range(spec.frames)]
    return gif_bytes(frames, duration=spec.duration)


@lru_cache(maxsize=None)
def emoji_image(name: str, size: int = 128):
    """Static RGBA image of an emoji for compositing into banners/cards."""
    return render_frame(name, 0.0, size)


def is_animated(name: str) -> bool:
    return EMOJIS[name].frames > 1
