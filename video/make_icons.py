#!/usr/bin/env python3
"""make_icons.py — チャンネル用アイコンの候補を作る（1024x1024 の PNG）

  python video/make_icons.py            video/branding/ に書き出す

アイコンは丸く切り抜かれて小さく表示されるので、中央の円の中に収まる太い図形だけで構成する。
2 倍の大きさで描いてから縮小し、輪郭をなめらかにしている。
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

S = 2048
C = S // 2
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "branding")

DARK = (17, 17, 24)
WHITE = (255, 255, 255)
RED = (255, 77, 90)
BLUE = (61, 139, 255)
GREEN = (61, 220, 132)
YELLOW = (255, 201, 60)
INK = (20, 20, 28)


def arc_band(surf, color, center, r_in, r_out, a0, a1, steps=240):
    pts = [(center[0] + math.cos(a0 + (a1 - a0) * i / steps) * r_out,
            center[1] + math.sin(a0 + (a1 - a0) * i / steps) * r_out) for i in range(steps + 1)]
    pts += [(center[0] + math.cos(a0 + (a1 - a0) * i / steps) * r_in,
             center[1] + math.sin(a0 + (a1 - a0) * i / steps) * r_in) for i in range(steps, -1, -1)]
    pygame.draw.polygon(surf, color, pts)


def ball(surf, color, pos, r, outline=INK, width=34):
    pygame.draw.circle(surf, outline, pos, r + width)
    pygame.draw.circle(surf, color, pos, r)
    pygame.draw.circle(surf, tuple(min(255, c + 70) for c in color), (pos[0] - r * 0.33, pos[1] - r * 0.36), r * 0.2)


def save(surf, name):
    os.makedirs(OUT, exist_ok=True)
    pygame.image.save(pygame.transform.smoothscale(surf, (1024, 1024)), os.path.join(OUT, name))
    print(os.path.join(OUT, name))


def icon_escape():
    """リングのすき間からボールが飛び出す。"""
    s = pygame.Surface((S, S))
    s.fill(DARK)
    gap_c, gap_h = -math.pi / 4, 0.42
    arc_band(s, WHITE, (C, C), 520, 640, gap_c + gap_h, gap_c + math.tau - gap_h)
    for i in range(7):                                    # 尾
        d = 120 + i * 95
        k = (i + 1) / 8
        col = tuple(int(DARK[j] + (YELLOW[j] - DARK[j]) * k * 0.8) for j in range(3))
        pygame.draw.circle(s, col, (C + math.cos(gap_c) * d, C + math.sin(gap_c) * d), 40 + i * 9)
    ball(s, YELLOW, (C + math.cos(gap_c) * 800, C + math.sin(gap_c) * 800), 150, outline=WHITE, width=0)
    save(s, "icon_escape.png")


def icon_clash():
    """武器を交差させた 2 つのボール。"""
    s = pygame.Surface((S, S))
    s.fill(DARK)
    a, b = (600, 1340), (1448, 1340)
    for base, tip, col in ((a, (1300, 520), (190, 220, 255)), (b, (748, 520), (255, 195, 195))):
        pygame.draw.line(s, INK, base, tip, 170)
        pygame.draw.line(s, col, base, tip, 104)
        pygame.draw.circle(s, INK, tip, 85)
        pygame.draw.circle(s, col, tip, 52)
    star = []                                             # 交差点の火花（4 つの角を持つ星）
    for k in range(8):
        ang = k / 8 * math.tau - math.pi / 2
        r = 250 if k % 2 == 0 else 85
        star.append((C + math.cos(ang) * r, 900 + math.sin(ang) * r))
    pygame.draw.polygon(s, YELLOW, star)
    ball(s, BLUE, a, 300)
    ball(s, RED, b, 300)
    save(s, "icon_clash.png")


def icon_bold():
    """黄色地に、跳ねる赤いボール 1 個。小さくても見分けやすい。"""
    s = pygame.Surface((S, S))
    s.fill(YELLOW)
    pygame.draw.ellipse(s, (214, 160, 30), (C - 330, 1500, 660, 130))     # 影
    for i, (r, w) in enumerate(((560, 60), (700, 46))):                    # 弾んだ跡の弧
        arc_band(s, INK, (C + 90, 1040), r, r + w, math.radians(200 + i * 6), math.radians(250 - i * 6))
    ball(s, RED, (C + 60, 960), 400, width=52)
    save(s, "icon_bold.png")


def icon_quad():
    """4 色の陣取りと、白いボール。"""
    s = pygame.Surface((S, S))
    cols = [(YELLOW, 0, 0), (RED, 1, 0), (GREEN, 0, 1), (BLUE, 1, 1)]
    cell = 128
    for col, qx, qy in cols:
        pygame.draw.rect(s, tuple(int(c * 0.82) for c in col), (qx * C, qy * C, C, C))
    # 境目をギザギザにして「奪い合っている」感じを出す
    for i, shift in enumerate([1, -1, 2, 0, -2, 1, -1, 0, 1, 2, -1, 0, -2, 1, 0, -1]):
        y = i * cell
        left = YELLOW if y < C else GREEN
        right = RED if y < C else BLUE
        col = right if shift < 0 else left
        pygame.draw.rect(s, tuple(int(c * 0.82) for c in col),
                         (C + min(0, shift) * cell, y, abs(shift) * cell, cell))
    ball(s, WHITE, (C + 150, C - 120), 250, width=44)
    save(s, "icon_quad.png")


# ---------------------------------------------------------------- ジャンルを限定しない汎用アイコン
def icon_stare():
    """ぼーっと画面を見つめている顔。どんな動画のチャンネルにも合う。"""
    s = pygame.Surface((S, S))
    s.fill(YELLOW)
    lid = (232, 172, 34)
    for ex in (C - 400, C + 400):
        ey, r = C - 60, 340
        pygame.draw.circle(s, INK, (ex, ey), r + 50)
        pygame.draw.circle(s, WHITE, (ex, ey), r)
        pygame.draw.circle(s, INK, (ex + 70, ey + 90), 170)                 # 黒目（同じ方向をじっと見る）
        pygame.draw.circle(s, WHITE, (ex + 10, ey + 30), 52)
        s.set_clip(pygame.Rect(ex - r - 60, ey - r - 60, 2 * r + 120, int(r * 0.78) + 60))   # 半分閉じたまぶた
        pygame.draw.circle(s, INK, (ex, ey), r + 50)
        pygame.draw.circle(s, lid, (ex, ey), r)
        s.set_clip(None)
        pygame.draw.line(s, INK, (ex - r - 40, ey - int(r * 0.22)), (ex + r + 40, ey - int(r * 0.22)), 54)
    pygame.draw.line(s, INK, (C - 120, C + 560), (C + 120, C + 560), 60)    # 口
    pygame.draw.circle(s, INK, (C - 120, C + 560), 30)
    pygame.draw.circle(s, INK, (C + 120, C + 560), 30)
    save(s, "icon_stare.png")


def icon_eye():
    """目の中に再生マーク。「つい見てしまう」を表す。"""
    s = pygame.Surface((S, S))
    s.fill(DARK)
    half_w, half_h = 800, 470
    upper = [(C + x, C - (1 - (x / half_w) ** 2) * half_h) for x in range(-half_w, half_w + 1, 16)]
    lower = [(C + x, C + (1 - (x / half_w) ** 2) * half_h) for x in range(half_w, -half_w - 1, -16)]
    pygame.draw.polygon(s, WHITE, upper + lower)
    pygame.draw.circle(s, BLUE, (C, C), 390)
    pygame.draw.circle(s, INK, (C, C), 390, 40)
    tri = [(C - 110, C - 190), (C - 110, C + 190), (C + 220, C)]
    pygame.draw.polygon(s, WHITE, tri)
    save(s, "icon_eye.png")


def icon_dots():
    """4 色の丸。いろいろな種類の動画がある、という意味。"""
    s = pygame.Surface((S, S))
    s.fill(DARK)
    d, r = 370, 320
    for col, sx, sy in ((RED, -1, -1), (YELLOW, 1, -1), (GREEN, -1, 1), (BLUE, 1, 1)):
        pygame.draw.circle(s, col, (C + sx * d, C + sy * d), r)
        pygame.draw.circle(s, tuple(min(255, c + 70) for c in col), (C + sx * d - 110, C + sy * d - 120), 62)
    save(s, "icon_dots.png")


def icon_rings():
    """吸い込まれるような同心円。小さくしても模様がつぶれない。"""
    s = pygame.Surface((S, S))
    s.fill(YELLOW)
    for i, r in enumerate((940, 780, 620, 460, 300)):
        pygame.draw.circle(s, INK if i % 2 == 0 else YELLOW, (C, C), r)
    pygame.draw.circle(s, RED, (C, C), 150)
    save(s, "icon_rings.png")


if __name__ == "__main__":
    pygame.init()
    icon_escape()
    icon_clash()
    icon_bold()
    icon_quad()
    icon_stare()
    icon_eye()
    icon_dots()
    icon_rings()
