"""sims_tower.py — 3 つの塔: 10 階を最初に壊すのはどれ？

3 色の塔が並び、それぞれ条件が違う（少数で始まり階ごとに 3 倍／中くらいで階ごとに 2 倍／
大勢で始まり階ごとに決まった数だけ増える）。ボールが床に当たるたびに床の体力が 1 減り、0 になると
床が抜けて下の階へ落ちる。床は下の階ほど固い。

どの塔もほぼ同じ時刻に 10 階へ届く「切りのいい数の組み合わせ」を、あらかじめ探して PRESETS に入れてある。
そこへ当たり方のばらつきが乗るので、どれが勝つかは毎回変わる。画面の粒は見た目用で、
個数が多いときは一部だけを描く（床の減り方は個数どおりに計算する）。
"""

import math

import numpy as np
import pygame

from engine import CX, H, W, mix

FLOORS = 10
HIT_RATE = 2.0                 # ボール 1 個が 1 秒に床へ当たる回数
# 条件の組み合わせ（3 倍の塔の個数, 2 倍の塔の個数, 足し算の塔の個数, 床の体力を上の階から）。
# どれも切りのいい数で、3 つの塔が計算上ほぼ同時（差 1% 以内、右の秒数）に 10 階へ届く。
# 候補を総当たりして見つけた組なので、数字を変えると釣り合いが崩れる。変えるなら _finish_time で確かめること。
PRESETS = [
    (5, 20, 250, [100, 250, 500, 1200, 3000, 5000, 12000, 20000, 40000, 80000]),    # 37.7 / 37.5 / 37.6
    (6, 20, 200, [100, 300, 600, 1200, 2500, 4000, 8000, 15000, 25000, 50000]),     # 31.9 / 31.7 / 31.8
    (4, 15, 200, [100, 300, 500, 800, 2000, 5000, 8000, 20000, 40000, 80000]),      # 45.1 / 45.0 / 44.8
    (5, 20, 300, [100, 300, 500, 1000, 2000, 5000, 8000, 20000, 60000, 100000]),    # 37.2 / 37.3 / 37.0
]
COLORS = [("CYAN", (40, 220, 240)), ("PINK", (255, 60, 200)), ("LIME", (190, 240, 40))]
TOP, BOTTOM = 470, 1570
TW, GAP = 300, 30
MAX_DOTS = 320


def _count(rule, start, k):
    """k 階ぶん壊したあとの個数。"""
    kind, val = rule
    return start * val ** k if kind == "x" else start + val * k


def _finish_time(rule, start, hp):
    """ばらつきがないとしたときの、10 階を壊し終わる秒数。"""
    return sum(h / (_count(rule, start, k) * HIT_RATE) for k, h in enumerate(hp))


def _sig3(n):
    """有効数字 3 けたに丸める（12,345 → 12,300）。"""
    n = float(n)
    if n < 1000:
        return int(round(n))
    mag = 10 ** (int(math.floor(math.log10(n))) - 2)
    return int(round(n / mag) * mag)


def _fmt(n):
    n = _sig3(n)
    if n >= 10 ** 9:
        return f"{n / 10 ** 9:.1f}B"
    if n >= 10 ** 6:
        return f"{n / 10 ** 6:.1f}M"
    return f"{n:,}"


def run_towers(v, rng):
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    kinds = [("x", 3), ("x", 2), ("+", 0)]
    rng.shuffle(kinds)
    a3, a2, ad, hp_list = rng.choice(PRESETS)

    def _hp(k):
        return float(hp_list[k])

    towers = []
    for i, rule in enumerate(kinds):
        if rule == ("x", 3):
            start = a3
        elif rule[0] == "x":
            start = a2
        else:
            start, rule = ad, ("+", ad)
        label = f"x{rule[1]} per floor" if rule[0] == "x" else f"+{_fmt(rule[1])} per floor"
        x0 = CX - (3 * TW + 2 * GAP) / 2 + i * (TW + GAP)
        towers.append({"rule": rule, "start": start, "n": float(start), "floor": 0, "hp": _hp(0), "label": label,
                       "x0": x0, "name": COLORS[i][0], "col": COLORS[i][1], "done": None, "flash": 0.0,
                       "P": np.zeros((0, 2)), "V": np.zeros((0, 2)), "tick": -9.0})
    fh = (BOTTOM - TOP) / FLOORS

    def floor_y(t):                               # いまの床の y（全部壊したら塔の底）
        return TOP + fh * min(FLOORS, t["floor"] + 1)

    def sync_dots(t):
        want = int(min(MAX_DOTS, max(1, round(t["n"])) if t["n"] < MAX_DOTS else MAX_DOTS))
        have = len(t["P"])
        if want > have:
            k = want - have
            fy = floor_y(t)
            P = np.column_stack([nrng.uniform(t["x0"] + 14, t["x0"] + TW - 14, k), nrng.uniform(TOP + 14, fy - 14, k)])
            ang = nrng.uniform(0, math.tau, k)
            spd = nrng.uniform(380, 620, k)
            V = np.column_stack([np.cos(ang) * spd, np.sin(ang) * spd])
            t["P"], t["V"] = np.vstack([t["P"], P]), np.vstack([t["V"], V])

    for t in towers:
        sync_dots(t)
    winner, win_at, margin = None, None, None
    chord = [60, 64, 67]
    while True:
        now = v.t
        dt = 1.0 / v.fps
        for i, t in enumerate(towers):
            if t["done"] is None and now > 1.0:
                lam = t["n"] * HIT_RATE * dt       # このコマで床に当たる回数（ばらつきつき）
                hits = nrng.poisson(lam) if lam < 50 else max(0.0, nrng.normal(lam, math.sqrt(lam)))
                t["hp"] -= hits
                if hits and now - t["tick"] > 0.085:
                    t["tick"] = now
                    v.audio.note(now, chord[i] + (12 if t["floor"] % 2 else 0), 0.2, "marimba")
                while t["hp"] <= 0 and t["done"] is None:
                    over = -t["hp"]
                    t["floor"] += 1
                    t["flash"] = 0.35
                    v.audio.play(now, 120, 0.55, "thud", channel=f"b{i}", min_gap=0.06)
                    v.audio.note(now, 60 + 2 * t["floor"] + chord[i] % 12, 0.5, "piano", channel=f"p{i}", min_gap=0.06,
                                 dur=0.6)
                    if t["floor"] >= FLOORS:
                        t["done"] = now
                        break
                    t["n"] = _count(t["rule"], t["start"], t["floor"])
                    t["hp"] = _hp(t["floor"]) - over
                    sync_dots(t)
            t["flash"] = max(0.0, t["flash"] - dt)
            # 見た目の粒: 重力なし。いまの床・天井・壁のあいだをまっすぐ跳ね回る（下に固まらない）
            P, V = t["P"], t["V"]
            fy = floor_y(t) - 8
            P += V * dt
            low = P[:, 1] > fy
            P[low, 1] = fy
            V[low, 1] = -np.abs(V[low, 1])
            high = P[:, 1] < TOP + 8
            P[high, 1] = TOP + 8
            V[high, 1] = np.abs(V[high, 1])
            left, right = P[:, 0] < t["x0"] + 10, P[:, 0] > t["x0"] + TW - 10
            P[left, 0], P[right, 0] = t["x0"] + 10, t["x0"] + TW - 10
            V[left, 0], V[right, 0] = np.abs(V[left, 0]), -np.abs(V[right, 0])
            flat = np.abs(V[:, 1]) < 120                     # ほぼ真横に飛ぶ粒は床に当たらないので、少し傾ける
            V[flat, 1] = np.where(V[flat, 1] >= 0, 200.0, -200.0)
        finished = sorted((t["done"], i) for i, t in enumerate(towers) if t["done"] is not None)
        if finished and winner is None:
            win_at, winner = finished[0]
            for k, m in enumerate((60, 64, 67, 72, 76)):
                v.audio.note(now + 0.07 * k, m, 0.8, "piano")
        if winner is not None and margin is None and len(finished) >= 2:
            margin = finished[1][0] - win_at

        if not v.dry:
            v.begin(bg=(5, 7, 13))
            v.text("3 towers, 3 rules", 92, (CX, 150))
            v.text(f"Who breaks floor {FLOORS} first?", 70, (CX, 232), color=(200, 205, 220), outline=4)
            for i, t in enumerate(towers):
                x0, col = t["x0"], t["col"]
                dim = mix((5, 7, 13), col, 0.28)
                cx = x0 + TW / 2
                v.text(_fmt(t["n"]), 78, (cx, 318), color=col, outline=4)
                v.text(t["label"], 40, (cx, 372), color=(215, 220, 232), outline=3)
                lvl = min(FLOORS, t["floor"] + 1)
                v.text(f"FLOOR {lvl}/{FLOORS}" if t["done"] is None else "DONE", 36, (cx, 420), color=mix((5, 7, 13), col, 0.65) if t["done"] is None else col,
                       outline=2)
                pygame.draw.rect(v.surf, dim, (int(x0), TOP, TW, BOTTOM - TOP), 3, border_radius=8)
                for k in range(t["floor"], FLOORS):            # まだ残っている床
                    y = int(TOP + fh * (k + 1))
                    cur = k == t["floor"]
                    c = mix(col, (255, 255, 255), t["flash"] / 0.35) if cur else dim
                    pygame.draw.line(v.surf, c, (int(x0) + 4, y), (int(x0) + TW - 4, y), 7 if cur else 3)
                    if cur:
                        v.text(_fmt(max(0, t["hp"])), 44, (cx, y + 34), color=(255, 255, 255), outline=3)
                    else:
                        v.text(_fmt(_hp(k)), 30, (cx, y - 22), color=mix((5, 7, 13), col, 0.5), outline=0)
                r = 6 if len(t["P"]) < 150 else 5
                for px, py in t["P"]:
                    pygame.draw.circle(v.surf, col, (int(px), int(py)), r)
                pygame.draw.rect(v.surf, col, (int(x0), TOP, TW, BOTTOM - TOP), 3, border_radius=8)
            clock = now if win_at is None else win_at
            v.text(f"{max(0.0, clock - 1.0):.1f}s", 64, (CX, BOTTOM + 118), color=(200, 205, 220), outline=3)
            if winner is not None:
                band = pygame.Surface((W, 300), pygame.SRCALPHA)
                band.fill((0, 0, 0, 185))
                v.surf.blit(band, (0, 880))
                v.text(f"{towers[winner]['name']} WINS", 150, (CX, 985), color=towers[winner]["col"], outline=7)
                if margin is not None:
                    v.text(f"by {margin:.2f}s", 84, (CX, 1100), outline=5)
        v.end(glow=0.4)
        if winner is not None and (now - win_at > 3.0 or (margin is not None and now - win_at > margin + 2.0)):
            break
        if now > 90:
            break
    w = towers[winner]
    rules = ", ".join(f"{_fmt(t['start'])} {t['label']}" for t in towers)
    return {"result": f"{w['name']} ({_fmt(w['start'])} {w['label']}) wins at {win_at - 1.0:.1f}s; {rules}",
            "rules": [f"{_fmt(t['start'])} balls, {t['label']}" for t in towers]}
