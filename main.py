#!/usr/bin/env python3
"""The world news of Sunday 22 November 2026, summed up in one image.

A pure standard-library Python program. It paints a newspaper front page
one pixel at a time -- its own 5x7 bitmap font stored as bit rows, its own
drawing helpers, its own PNG encoder -- and writes the result to
/output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png). No network, no files
read, no randomness except a fixed-seed generator, so two runs write the
same bytes.

The day it sums up, as reported on 22 November 2026:
  * The G20 summit opens in Johannesburg, the first ever held in Africa;
    the United States boycotts it and a leaders' declaration is adopted.
  * Iran says its missiles and drones hit US Patriot radars at the
    al-Riffa and Awali bases in Bahrain, in the Gulf war's latest round.
  * Mexican forces capture cartel kingpin Fausto Isidro Meza Flores,
    "El Chapo Isidro"; 11 people are killed in the violence that follows.
  * A magnitude 6.7 earthquake shakes Peru's Andes; no deaths reported.
  * The Pentagon moves to restrict US-Canada defence ties.
  * The world court finds Myanmar guilty of genocide against the Rohingya;
    Rohingya survivors hail the verdict.
  * Also: Trump vows a 10% cap on credit-card rates; Bitcoin rebounds 8%
    to near $60,000; Verstappen takes pole in Las Vegas; Australia edge
    England in a T20 thriller at the MCG; Japan and India agree live-fire
    drills; TikTok launches a deepfake detector.
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

PAPER = (246, 242, 230)
CARD = (255, 253, 246)
INK = (24, 22, 18)
RED = (176, 32, 26)
NAVY = (14, 22, 50)
GOLD = (214, 166, 42)
GREY = (98, 94, 86)
SKY = (24, 42, 92)

# The picture, one byte per colour channel.
canvas = bytearray(W * H * 3)


def set_px(x, y, colour):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        canvas[i], canvas[i + 1], canvas[i + 2] = colour


def fill_rect(x, y, w, h, colour):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            set_px(xx, yy, colour)


def border(x, y, w, h, colour, t=2):
    fill_rect(x, y, w, t, colour)
    fill_rect(x, y + h - t, w, t, colour)
    fill_rect(x, y, t, h, colour)
    fill_rect(x + w - t, y, t, h, colour)


def seg(x0, y0, x1, y1, colour, t=1):
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy), 1)
    r = t // 2
    for i in range(steps + 1):
        x = round(x0 + dx * i / steps)
        y = round(y0 + dy * i / steps)
        for yy in range(y - r, y - r + t):
            for xx in range(x - r, x - r + t):
                set_px(xx, yy, colour)


def filled_circle(cx, cy, r, colour):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                set_px(xx, yy, colour)


def fill_poly(points, colour):
    ys = [p[1] for p in points]
    for y in range(min(ys), max(ys) + 1):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for x in range(round(xs[i]), round(xs[i + 1]) + 1):
                set_px(x, y, colour)


def shade(x, y, w, h, top, bottom):
    for i in range(h):
        f = i / max(h - 1, 1)
        colour = tuple(round(top[k] + (bottom[k] - top[k]) * f)
                       for k in range(3))
        fill_rect(x, y + i, w, 1, colour)


def fixed_rand(n, seed=20261122):
    """Deterministic pseudo-random numbers in [0, 1)."""
    out, v = [], seed
    for _ in range(n):
        v = (v * 1103515245 + 12345) % (1 << 31)
        out.append(v / (1 << 31))
    return out


# ------------------------------------------------------------------ font
# A 5x7 bitmap font. Each glyph is 7 rows; each row is a 5-bit number,
# most-significant bit on the left. Only capitals, digits and the marks
# the headlines need.
GLYPHS = {
    "A": (14, 17, 17, 31, 17, 17, 17),
    "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (28, 18, 17, 17, 17, 18, 28),
    "E": (31, 16, 16, 30, 16, 16, 31),
    "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),
    "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17),
    "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17),
    "N": (17, 25, 21, 19, 17, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13),
    "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10),
    "X": (17, 10, 4, 4, 4, 10, 17),
    "Y": (17, 10, 4, 4, 4, 4, 4),
    "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (31, 2, 4, 2, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 2, 12),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 12, 12),
    ",": (0, 0, 0, 0, 12, 4, 8),
    "'": (4, 4, 8, 0, 0, 0, 0),
    "-": (0, 0, 0, 14, 0, 0, 0),
    "+": (0, 4, 4, 14, 4, 4, 0),
    "%": (25, 26, 2, 4, 8, 11, 19),
    ":": (0, 12, 12, 0, 12, 12, 0),
    ";": (0, 12, 12, 0, 12, 4, 8),
    "•": (0, 0, 14, 14, 14, 0, 0),
    "/": (1, 2, 2, 4, 8, 8, 16),
    "(": (2, 4, 8, 8, 8, 4, 2),
    ")": (8, 4, 2, 2, 2, 4, 8),
    "!": (4, 4, 4, 4, 4, 0, 4),
    "?": (14, 17, 1, 4, 4, 0, 4),
    "&": (12, 18, 20, 8, 21, 18, 13),
    "$": (4, 15, 20, 14, 5, 30, 4),
}


def glyph_width(s, scale):
    return len(s) * 6 * scale - scale if s else 0


def draw_text(x, y, s, scale, colour, bold=False):
    for ch in s:
        rows = GLYPHS.get(ch, GLYPHS["?"])
        for r in range(7):
            bits = rows[r]
            for col in range(5):
                if bits & (16 >> col):
                    fill_rect(x + col * scale, y + r * scale,
                              scale, scale, colour)
                    if bold:
                        fill_rect(x + col * scale + 1, y + r * scale,
                                  scale, scale, colour)
        x += 6 * scale
    return x


def draw_centred(y, s, scale, colour, bold=False, cx=W // 2):
    return draw_text(cx - glyph_width(s, scale) // 2, y, s, scale,
                     colour, bold)


def shrink_to_fit(s, max_w, start):
    scale = start
    while scale > 1 and glyph_width(s, scale) > max_w:
        scale -= 1
    return scale


def wrap_text(s, scale, max_w):
    lines, cur = [], ""
    for word in s.split():
        trial = word if not cur else cur + " " + word
        if glyph_width(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def para(x, y, s, scale, colour, max_w, leading=3, bold=False):
    for ln in wrap_text(s, scale, max_w):
        draw_text(x, y, ln, scale, colour, bold)
        y += (7 + leading) * scale
    return y


# ------------------------------------------------------------------ scenes
def scene_g20(x, y, w, h):
    """Dawn over Johannesburg: sun, skyline, a globe for the G20."""
    shade(x, y, w, h, (250, 178, 80), (214, 96, 44))
    filled_circle(x + 92, y + 46, 30, (255, 232, 160))
    rnd = fixed_rand(60)
    for i in range(26):  # birds
        bx = x + int(rnd[i] * (w - 40)) + 20
        by = y + int(rnd[i + 26] * 46) + 8
        seg(bx - 5, by, bx, by - 3, INK, 2)
        seg(bx, by - 3, bx + 5, by, INK, 2)
    # skyline silhouette
    bx = x
    heights = [30, 46, 34, 62, 40, 52, 30, 70, 38, 48, 34, 56, 28, 44]
    i = 0
    while bx < x + w - 34:
        bw = 30 + int(rnd[i % 26] * 24)
        bh = heights[i % len(heights)]
        fill_rect(bx, y + h - bh, bw, bh, (30, 18, 10))
        bx += bw + 4
        i += 1
    # Hillbrow-style tower
    fill_rect(x + w - 96, y + h - 108, 22, 108, (30, 18, 10))
    filled_circle(x + w - 85, y + h - 108, 12, (30, 18, 10))
    # globe, lower right, floating above the skyline
    gx, gy, gr = x + w - 78, y + 52, 34
    filled_circle(gx, gy, gr, (34, 96, 158))
    for k in range(-2, 3):
        seg(gx - gr, gy + k * 12, gx + gr, gy + k * 12, (200, 224, 244), 1)
    for k in (-1, 0, 1):
        seg(gx + k * 14, gy - gr, gx + k * 14, gy + gr, (200, 224, 244), 1)
    # ground band
    fill_rect(x, y + h - 8, w, 8, (30, 18, 10))


def scene_gulf(x, y, w, h):
    """Night over the Gulf: radar dome, missile streaks, a warship."""
    shade(x, y, w, h, (8, 12, 34), (16, 30, 66))
    rnd = fixed_rand(40)
    for i in range(24):
        sx = x + int(rnd[i] * (w - 8)) + 4
        sy = y + int(rnd[i + 16] * h * 0.4) + 3
        set_px(sx, sy, (205, 210, 232))
    # missile streaks slanting down
    for (sx, sy, ln) in [(40, 8, 52), (150, 2, 66), (240, 12, 48)]:
        ex, ey = x + sx - ln, y + sy + ln // 2
        seg(x + sx, y + sy, ex, ey, (255, 176, 84), 4)
        seg(ex, ey, ex - 10, ey + 6, (255, 92, 40), 5)
        filled_circle(ex - 12, ey + 7, 4, (255, 214, 120))
    # radar dome on a base
    dx, dy = x + 64, y + h - 46
    for r in range(30, 0, -1):
        for xx in range(dx - r, dx + r + 1):
            yy = dy - int(math.sqrt(max(r * r - (xx - dx) ** 2, 0)))
            set_px(xx, yy, (232, 236, 242))
    fill_rect(dx - 34, dy, 68, 10, (180, 186, 196))
    seg(dx, dy - 30, dx + 26, dy - 44, (255, 214, 120), 2)
    filled_circle(dx + 28, dy - 45, 3, (255, 214, 120))
    # warship silhouette on the sea
    sy = y + h - 22
    fill_rect(x + 150, sy, 150, 12, (6, 8, 16))
    fill_poly([(x + 150, sy), (x + 300, sy), (x + 288, sy + 12),
               (x + 162, sy + 12)], (6, 8, 16))
    fill_rect(x + 210, sy - 18, 34, 18, (6, 8, 16))
    seg(x + 227, sy - 18, x + 227, sy - 34, (6, 8, 16), 3)
    # sea lines
    for yy in (y + h - 8, y + h - 4):
        for xx in range(x + 6, x + w - 6, 14):
            seg(xx, yy, xx + 8, yy, (90, 120, 170), 1)


def scene_cartel(x, y, w, h):
    """Desert highway at dusk, a helicopter overhead."""
    shade(x, y, w, h, (236, 178, 108), (196, 120, 58))
    # mountains
    fill_poly([(x, y + h - 40), (x + 26, y + 52), (x + 58, y + h - 40)],
              (146, 84, 48))
    fill_poly([(x + 44, y + h - 40), (x + 78, y + 66), (x + 112, y + h - 40)],
              (120, 66, 38))
    # helicopter
    hx, hy = x + 46, y + 30
    seg(hx - 34, hy - 10, hx + 34, hy - 10, INK, 3)
    filled_circle(hx, hy, 10, INK)
    fill_poly([(hx + 8, hy - 4), (hx + 30, hy + 2), (hx + 8, hy + 6)], INK)
    seg(hx - 6, hy + 8, hx - 6, hy + 16, INK, 2)
    # road
    fill_poly([(x, y + h), (x + 30, y + h - 40), (x + 74, y + h - 40),
               (x + w, y + h)], (52, 48, 44))
    for i in range(4):
        yy = y + h - 34 + i * 9
        seg(x + 44 + i * 4, yy, x + 58 + i * 4, yy, (250, 240, 210), 2)
    # roadblock stripes, lower right
    bx, by = x + w - 46, y + h - 34
    for i in range(5):
        fill_rect(bx + i * 8, by, 4, 26, RED if i % 2 == 0 else (250, 250, 250))


def scene_quake(x, y, w, h):
    """Andes peaks with a seismograph trace across the scene."""
    shade(x, y, w, h, (168, 196, 224), (226, 232, 238))
    # peaks
    fill_poly([(x, y + h), (x + 34, y + 34), (x + 68, y + h)], (96, 110, 128))
    fill_poly([(x + 52, y + h), (x + 84, y + 18), (x + 116, y + h)],
              (70, 84, 102))
    fill_poly([(x + 26, y + 42), (x + 34, y + 34), (x + 42, y + 42),
               (x + 34, y + 48)], (250, 250, 250))
    fill_poly([(x + 76, y + 28), (x + 84, y + 18), (x + 92, y + 28),
               (x + 84, y + 34)], (250, 250, 250))
    # cracked ground
    seg(x + 10, y + h - 14, x + 40, y + h - 22, INK, 2)
    seg(x + 40, y + h - 22, x + 66, y + h - 12, INK, 2)
    seg(x + 66, y + h - 12, x + 96, y + h - 20, INK, 2)
    # seismograph strip
    fill_rect(x, y + 96, w, 44, (255, 255, 255))
    border(x, y + 96, w, 44, INK, 1)
    pts = [(0, 22), (8, 22), (12, 10), (16, 34), (20, 22), (30, 22),
           (34, 4), (38, 40), (42, 22), (54, 22), (58, 14), (62, 30),
           (66, 22), (78, 22), (82, 8), (86, 36), (90, 22), (100, 22)]
    for i in range(len(pts) - 1):
        seg(x + pts[i][0], y + 96 + pts[i][1],
            x + pts[i + 1][0], y + 96 + pts[i + 1][1], RED, 2)


def scene_flags(x, y, w, h):
    """The US and Canadian flags, split by a barrier stripe."""
    fill_rect(x, y, w, h, (20, 28, 60))
    # US flag, left
    ux, uy, uw, uh = x + 6, y + 18, 42, 28
    for i in range(7):
        fill_rect(ux, uy + i * 4, uw, 4,
                  (178, 34, 52) if i % 2 == 0 else (245, 245, 245))
    fill_rect(ux, uy, 18, 16, (30, 48, 110))
    for sy in (uy + 4, uy + 8, uy + 12):
        for sx in (ux + 3, ux + 9, ux + 15):
            set_px(sx, sy, (245, 245, 245))
    # Canada flag, right
    cx, cy, cw, ch = x + w - 48, y + 18, 42, 28
    fill_rect(cx, cy, 10, ch, RED)
    fill_rect(cx + cw - 10, cy, 10, ch, RED)
    fill_rect(cx + 10, cy, cw - 20, ch, (245, 245, 245))
    # maple leaf, simplified as a red starburst
    lx, ly = cx + cw // 2, cy + ch // 2
    for k in range(8):
        a = k * math.pi / 4
        seg(lx, ly, lx + int(math.cos(a) * 9), ly + int(math.sin(a) * 9),
            RED, 3)
    filled_circle(lx, ly, 3, RED)
    # diagonal barrier between them
    seg(x + 52, y + h - 12, x + w - 52, y + 12, GOLD, 6)
    for i in range(4):
        seg(x + 56 + i * 10, y + h - 16, x + 60 + i * 10, y + h - 26,
            INK, 2)


def scene_court(x, y, w, h):
    """A courthouse front and the flag of Myanmar."""
    shade(x, y, w, h, (30, 48, 96), (58, 84, 140))
    # pediment
    fill_poly([(x + 8, y + 34), (x + w // 2, y + 8), (x + w - 8, y + 34)],
              (240, 234, 220))
    fill_rect(x + 8, y + 34, w - 16, 6, (240, 234, 220))
    # columns
    for i in range(4):
        cx = x + 18 + i * 24
        fill_rect(cx, y + 42, 10, 62, (240, 234, 220))
        fill_rect(cx - 2, y + 40, 14, 4, (240, 234, 220))
        fill_rect(cx - 2, y + 102, 14, 4, (240, 234, 220))
    fill_rect(x + 8, y + 106, w - 16, 8, (240, 234, 220))
    # Myanmar flag, lower right
    fx, fy, fw, fh = x + w - 52, y + h - 40, 42, 27
    fill_rect(fx, fy, fw, 9, (254, 203, 0))
    fill_rect(fx, fy + 9, fw, 9, (52, 142, 66))
    fill_rect(fx, fy + 18, fw, 9, (234, 40, 46))
    sx, sy = fx + fw // 2, fy + fh // 2
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        seg(sx, sy, sx + int(math.cos(a) * 8), sy + int(math.sin(a) * 8),
            (250, 250, 250), 2)
    border(fx, fy, fw, fh, INK, 1)


def card(x, y, w, h):
    fill_rect(x, y, w, h, CARD)
    border(x, y, w, h, INK, 2)


def story_row(x, y, w, h, scene, kicker, head, sub):
    card(x, y, w, h)
    scene(x + 10, y + 10, 100, h - 20)
    border(x + 10, y + 10, 100, h - 20, INK, 1)
    tx = x + 124
    draw_text(tx, y + 14, kicker, 2, RED, True)
    para(tx, y + 36, head, 3, INK, w - 136, 3, True)
    para(tx, y + 124, sub, 2, GREY, w - 136, 2)


def main():
    fill_rect(0, 0, W, H, PAPER)
    border(8, 8, W - 16, H - 16, INK, 3)

    # ---- masthead
    draw_centred(22, "ONE IMAGE • ONE DAY • THE WHOLE WORLD", 3, GREY)
    draw_centred(50, "SUNDAY 22 NOVEMBER 2026",
                 shrink_to_fit("SUNDAY 22 NOVEMBER 2026", 960, 7), INK, True)
    draw_centred(112, "THE DAY'S WORLD NEWS IN A SINGLE FRONT PAGE", 2, GREY)
    fill_rect(24, 134, W - 48, 3, INK)
    fill_rect(24, 140, W - 48, 1, INK)

    # ---- lead story: G20 in Johannesburg
    card(24, 152, 636, 310)
    scene_g20(28, 156, 628, 148)
    border(28, 156, 628, 148, INK, 1)
    draw_text(40, 314, "SUMMIT • JOHANNESBURG", 2, RED, True)
    para(40, 334, "G20 OPENS IN AFRICA FOR THE FIRST TIME",
         4, INK, 604, 1, True)
    draw_text(40, 436, "US BOYCOTTS • DECLARATION ADOPTED",
              3, RED, True)

    # ---- Gulf: Iran claims strikes on US radars in Bahrain
    card(676, 152, 324, 310)
    scene_gulf(680, 156, 316, 118)
    border(680, 156, 316, 118, INK, 1)
    draw_text(692, 284, "GULF WAR • BAHRAIN", 2, RED, True)
    para(692, 304, "IRAN CLAIMS STRIKES ON US RADARS IN BAHRAIN",
         3, INK, 292, 2, True)
    para(692, 410, "MISSILES + DRONES HIT THE PATRIOT RADARS",
         2, GREY, 292, 2)

    # ---- middle row
    story_row(24, 478, 480, 176, scene_cartel, "MEXICO • SINALOA",
              "MEXICO CAPTURES CARTEL KINGPIN EL CHAPO ISIDRO",
              "11 KILLED IN VIOLENCE AFTER THE RAID ON MEZA FLORES.")
    story_row(520, 478, 480, 176, scene_quake, "EARTHQUAKE • PERU",
              "6.7 QUAKE SHAKES PERU'S ANDES",
              "NO DEATHS REPORTED IN THE ANDES.")

    # ---- bottom row
    story_row(24, 670, 480, 176, scene_flags, "DEFENCE • WASHINGTON",
              "PENTAGON MOVES TO CURB US-CANADA DEFENCE TIES",
              "WASHINGTON RESTRICTS CONTACTS WITH OTTAWA.")
    story_row(520, 670, 480, 176, scene_court, "JUSTICE • THE HAGUE",
              "MYANMAR GUILTY OF GENOCIDE, WORLD COURT RULES",
              "ROHINGYA HAIL THE LANDMARK VERDICT ON MYANMAR.")

    # ---- also today
    card(24, 862, 976, 116)
    draw_text(40, 876, "ALSO TODAY", 3, RED, True)
    para(40, 906,
         "TRUMP VOWS 10% CAP ON CREDIT CARD RATES • BITCOIN REBOUNDS 8% TO "
         "NEAR $60,000 • VERSTAPPEN ON POLE IN LAS VEGAS • AUSTRALIA EDGE "
         "ENGLAND IN MCG T20 THRILLER • JAPAN + INDIA AGREE LIVE-FIRE "
         "DRILLS • TIKTOK LAUNCHES DEEPFAKE DETECTOR",
         2, INK, 944, 2)

    draw_centred(990, "DRAWN BY AN AI AGENT FROM THE WIRE REPORTS OF 22 NOVEMBER 2026",
                 2, GREY)

    # ---- write the PNG
    raw = bytearray()
    for yy in range(H):
        raw.append(0)
        raw += canvas[yy * W * 3:(yy + 1) * W * 3]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(png)


if __name__ == "__main__":
    main()
