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


# towers2 用: （2 倍の塔の個数, 「毎秒 N 個ずつ増える」塔の N（最初も N 個）, 増えない塔の個数, 床の体力）。
# こちらも総当たりで見つけた、ほぼ同時に終わる組。
PRESETS_TIME = [
    # 90 回の試算で勝ちが 33 / 34 / 23 回（2 倍／毎秒／増えない）に分かれた組。
    # 「+82・1,520」は釣り合っていたが「中途半端な数字」と言われたので、80・1,500 にして 2 階の体力（270）で釣り合わせた。
    # 2 階の体力にとても敏感: 250 だと 2 倍の塔が半分以上勝ち、300 だと毎秒の塔が半分以上勝つ。
    (15, 80, 1500, [100, 270, 500, 800, 1500, 3000, 6000, 15000, 30000, 50000]),
]


def run_towers2(v, rng):
    """towers の別バージョン: 階ごとに 2 倍／毎秒決まった数ずつ増える／最初から大勢で増えない。"""
    a2, per_sec, big, hp_list = rng.choice(PRESETS_TIME)
    return run_towers(v, rng, setup=([("x", 2, a2), ("s", per_sec, per_sec), ("=", 0, big)], hp_list), luck=0.02)


def run_towers(v, rng, setup=None, luck=0.0):
    """luck: 塔ごとの当たりやすさのばらつき（0.02 なら ±2%）。個数が多い塔は当たり数のばらつきが小さく、
    計算上わずかに遅いだけで毎回負けてしまうので、その差を埋めるために towers2 で使っている。"""
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    if setup is None:
        a3, a2, ad, hp_list = rng.choice(PRESETS)
        specs = [("x", 3, a3), ("x", 2, a2), ("+", ad, ad)]
    else:
        specs, hp_list = setup
    specs = list(specs)
    rng.shuffle(specs)

    def _hp(k):
        return float(hp_list[k])

    towers = []
    for i, (kind, val, start) in enumerate(specs):
        rule = (kind, val)
        label = {"x": f"x{val} per floor", "+": f"+{_fmt(val)} per floor", "s": f"+{_fmt(val)} per second",
                 "=": "never grows"}[kind]
        x0 = CX - (3 * TW + 2 * GAP) / 2 + i * (TW + GAP)
        towers.append({"rule": rule, "start": start, "n": float(start), "floor": 0, "hp": _hp(0), "label": label,
                       "x0": x0, "name": COLORS[i][0], "col": COLORS[i][1], "done": None, "flash": 0.0,
                       "P": np.zeros((0, 2)), "V": np.zeros((0, 2)), "tick": -9.0,
                       "luck": rng.uniform(1 - luck, 1 + luck)})
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
                if t["rule"][0] == "s":            # 時間で増える塔: 毎秒決まった数ずつ増える
                    t["n"] = t["start"] + t["rule"][1] * (now - 1.0)
                    if int(t["n"]) // 40 != len(t["P"]) // 40:
                        sync_dots(t)
                lam = t["n"] * HIT_RATE * dt * t["luck"]      # このコマで床に当たる回数（ばらつきつき）
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
                    if t["rule"][0] in ("x", "+"):
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
            "rules": [f"{_fmt(t['start'])} balls, {t['label']}" for t in towers], "winner_kind": w["rule"][0]}


# ============================================================ cannons: 3 つの砲台、壁を最初に壊すのは？
# 条件の組み合わせ（壁の体力, 砲台 1 門が 1 秒に撃つ数, 「何秒ごとに速さ 2 倍」, 「何秒ごとに 1 門追加」, 「最初から何門」）。
# どれも切りのいい数で、3 つが計算上ほぼ同時（右の秒数）に壁を壊す。総当たりで見つけた組なので、
# 数字を変えると釣り合いが崩れる。変えるなら下の _cannon_times で確かめること。
CANNON_PRESETS = [
    (1000, 5, 8, 3, 6),         # 33.6 / 33.2 / 33.3
    (1200, 4, 8, 2.5, 8),       # 38.0 / 37.5 / 37.5
    (1200, 3, 6, 1.5, 12),      # 33.4 / 33.9 / 33.3
    (4000, 5, 6, 1, 20),        # 39.3 / 39.5 / 40.0
    (1000, 2, 5, 1, 16),        # 30.7 / 31.1 / 31.2
]


def _cannon_times(H, r, D, E, n):
    """ばらつきがないとしたときの、3 つの砲台が壁を壊し終わる秒数（速さ 2 倍・門が増える・最初から多い）。"""
    t_a = D * math.log2(1 + H * math.log(2) / (r * D))
    t, dmg, k = 0.0, 0.0, 1
    while dmg + k * r * E < H:
        dmg, t, k = dmg + k * r * E, t + E, k + 1
    return t_a, t + (H - dmg) / (k * r), H / (n * r)


def run_cannons(v, rng):
    """3 本のレーンで、砲台が上の壁を撃つ。1 発で壁の体力が 1 減る。条件はレーンごとに違う:
    1 門だが一定時間ごとに撃つ速さが 2 倍／一定時間ごとに 1 門ずつ増える／最初から何門もあって増えない。"""
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    H, rate, D, E, n_fixed = rng.choice(CANNON_PRESETS)
    kinds = ["double", "add", "fixed"]
    rng.shuffle(kinds)
    cols, rows = 15, 24
    bw = TW / cols                                 # レンガ 1 個の幅と高さ
    wall_h = rows * bw
    y_gun = BOTTOM - 46
    lanes = []
    for i, kind in enumerate(kinds):
        x0 = CX - (3 * TW + 2 * GAP) / 2 + i * (TW + GAP)
        label = {"double": f"x2 speed / {D:g}s", "add": f"+1 cannon / {E:g}s", "fixed": f"{n_fixed} cannons"}[kind]
        start = {"double": "1 cannon", "add": "1 cannon", "fixed": "no growth"}[kind]
        order = []                                 # レンガが壊れる順（下の段から。段の中はばらばら）
        for row in range(rows - 1, -1, -1):
            cs = list(range(cols))
            rng.shuffle(cs)
            order += [(c, row) for c in cs]
        lanes.append({"kind": kind, "x0": x0, "label": label, "start": start, "hp": float(H), "order": order,
                      "name": COLORS[i][0], "col": COLORS[i][1], "done": None, "shots": [], "level": 0, "guns": 1,
                      "tick": -9.0, "flash": 0.0, "sparks": []})

    def guns_and_rate(lane, t):
        """いまの門の数と、全体で 1 秒に撃つ数。"""
        if lane["kind"] == "double":
            return 1, rate * 2 ** (t / D)
        if lane["kind"] == "add":
            k = 1 + int(t / E)
            return k, rate * k
        return n_fixed, rate * n_fixed

    def gun_xs(lane, k):
        per_row = 10
        xs = []
        for j in range(k):
            row, col = divmod(j, per_row)
            in_row = min(per_row, k - row * per_row)
            xs.append((lane["x0"] + TW * (col + 0.5) / in_row, y_gun - row * 34))
        return xs

    winner, win_at, margin = None, None, None
    chord = [60, 64, 67]
    t0 = 1.0                                       # 最初の 1 秒は条件を読む時間
    while True:
        now = v.t
        dt = 1.0 / v.fps
        t = max(0.0, now - t0)
        for i, lane in enumerate(lanes):
            left = len(lane["order"]) * max(0.0, lane["hp"]) / H
            wall_bottom = TOP + wall_h * math.ceil(left / cols) / rows if lane["hp"] > 0 else TOP
            if lane["done"] is None and now > t0:
                k, per_sec = guns_and_rate(lane, t)
                lam = per_sec * dt
                shots = nrng.poisson(lam) if lam < 50 else max(0.0, nrng.normal(lam, math.sqrt(lam)))
                lane["hp"] -= shots
                if lane["kind"] == "double" and int(t / D) != lane["level"]:
                    lane["level"] = int(t / D)
                    lane["flash"] = 0.4
                    v.audio.note(now, 72 + 2 * lane["level"], 0.55, "piano", dur=0.5)
                if lane["kind"] == "add" and k != lane["guns"]:
                    lane["flash"] = 0.25
                    v.audio.play(now, 900 + 30 * k, 0.25, "click", channel=f"a{i}", min_gap=0.2)
                lane["guns"] = k
                if shots and now - lane["tick"] > 0.085:
                    lane["tick"] = now
                    v.audio.note(now, chord[i] + (12 if int(now * 4) % 2 else 0), 0.2, "marimba")
                xs = gun_xs(lane, k)
                for _ in range(int(min(shots, 5))):                 # 見た目の弾（多いときは一部だけ描く）
                    gx, gy = xs[int(nrng.integers(len(xs)))]
                    lane["shots"].append([gx + float(nrng.uniform(-4, 4)), gy - 20])
                if lane["hp"] <= 0:
                    lane["done"] = now
                    v.audio.play(now, 110, 0.7, "thud")
            for s in lane["shots"]:
                s[1] -= 2600 * dt
            hit = [s for s in lane["shots"] if s[1] <= wall_bottom]
            for s in hit[:3]:
                lane["sparks"].append([s[0], wall_bottom, 0.0])
            lane["shots"] = [s for s in lane["shots"] if s[1] > wall_bottom]
            for sp_ in lane["sparks"]:
                sp_[2] += dt
            lane["sparks"] = [sp_ for sp_ in lane["sparks"] if sp_[2] < 0.15][-30:]
            lane["flash"] = max(0.0, lane["flash"] - dt)
        finished = sorted((lane["done"], i) for i, lane in enumerate(lanes) if lane["done"] is not None)
        if finished and winner is None:
            win_at, winner = finished[0]
            for k_, m in enumerate((60, 64, 67, 72, 76)):
                v.audio.note(now + 0.07 * k_, m, 0.8, "piano")
        if winner is not None and margin is None and len(finished) >= 2:
            margin = finished[1][0] - win_at

        if not v.dry:
            v.begin(bg=(5, 7, 13))
            v.text("3 cannons, 3 rules", 92, (CX, 150))
            v.text("Who breaks the wall first?", 70, (CX, 232), color=(200, 205, 220), outline=4)
            for i, lane in enumerate(lanes):
                x0, col = lane["x0"], lane["col"]
                dim = mix((5, 7, 13), col, 0.3)
                cx = x0 + TW / 2
                v.text(lane["label"], 50, (cx, 322), color=col, outline=4)
                v.text(lane["start"], 36, (cx, 368), color=(215, 220, 232), outline=3)
                k, per_sec = guns_and_rate(lane, t)
                v.text(f"{_fmt(per_sec)} shots/s" if lane["done"] is None else "DONE", 38, (cx, 420),
                       color=mix((5, 7, 13), col, 0.75) if lane["done"] is None else col, outline=2)
                pygame.draw.rect(v.surf, dim, (int(x0), TOP, TW, BOTTOM - TOP), 3, border_radius=8)
                left = int(math.ceil(len(lane["order"]) * max(0.0, lane["hp"]) / H))
                brick = mix((5, 7, 13), col, 0.62)
                for c_, r_ in lane["order"][len(lane["order"]) - left:]:      # まだ残っているレンガ
                    pygame.draw.rect(v.surf, brick, (int(x0 + c_ * bw) + 1, int(TOP + r_ * bw) + 1, int(bw) - 2, int(bw) - 2),
                                     border_radius=3)
                if lane["hp"] > 0:
                    v.text(_fmt(lane["hp"]), 72, (cx, TOP + 70), outline=5)
                for sx, sy in lane["shots"]:
                    pygame.draw.line(v.surf, mix(col, (255, 255, 255), 0.6), (sx, sy), (sx, sy + 26), 4)
                for sx, sy, age in lane["sparks"]:
                    v.circle(mix((255, 255, 255), col, age / 0.15), (sx, sy), 6 + 60 * age)
                glow = lane["flash"] / 0.4
                for gx, gy in gun_xs(lane, k):
                    big = 1.0 + (0.22 * min(lane["level"], 6) if lane["kind"] == "double" else 0.0)
                    wdt = max(10, min(26, TW / max(1, min(k, 10)) - 6)) * big
                    body_c = mix(mix((60, 66, 80), col, 0.55), (255, 255, 255), min(1.0, glow))
                    pygame.draw.rect(v.surf, body_c, (int(gx - wdt / 2), int(gy - 6), int(wdt), 22), border_radius=5)
                    pygame.draw.rect(v.surf, body_c, (int(gx - wdt * 0.2), int(gy - 22), int(max(4, wdt * 0.4)), 20), border_radius=3)
                pygame.draw.rect(v.surf, col, (int(x0), TOP, TW, BOTTOM - TOP), 3, border_radius=8)
            clock = now if win_at is None else win_at
            v.text(f"{max(0.0, clock - t0):.1f}s", 64, (CX, BOTTOM + 118), color=(200, 205, 220), outline=3)
            if winner is not None:
                band = pygame.Surface((W, 300), pygame.SRCALPHA)
                band.fill((0, 0, 0, 185))
                v.surf.blit(band, (0, 880))
                v.text(f"{lanes[winner]['name']} WINS", 150, (CX, 985), color=lanes[winner]["col"], outline=7)
                if margin is not None:
                    v.text(f"by {margin:.2f}s", 84, (CX, 1100), outline=5)
        v.end(glow=0.4)
        if winner is not None and (now - win_at > 3.0 or (margin is not None and now - win_at > margin + 2.0)):
            break
        if now > 90:
            break
    w = lanes[winner]
    return {"result": f"{w['name']} ({w['label']}) wins at {win_at - t0:.1f}s; wall {H}, {rate} shots/s per cannon",
            "winner_kind": w["kind"]}
