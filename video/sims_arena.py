"""sims_arena.py — 対戦系: 陣取り合戦 / HP バトル"""

import math

import numpy as np
import pygame

from engine import CX, CY, Particles, mix, penta

TEAMS = [("RED", (255, 77, 90)), ("BLUE", (61, 139, 255)), ("GREEN", (61, 220, 132)), ("YELLOW", (255, 201, 60)),
         ("PURPLE", (178, 102, 255)), ("ORANGE", (255, 140, 50)), ("CYAN", (60, 220, 230)), ("PINK", (255, 110, 190))]


# ============================================================ 4. 陣取り合戦
# 4 色はそれぞれ違う条件で始まる（最初の数が多いほど、増え方が遅い）。どの色がどの条件かは毎回入れ替わる。
# 秒数は 120 回の試算で勝率がほぼ均等（21〜31%）になるよう決めた。変えると片寄るので、変えたら試算し直すこと。
#   (最初の個数, 増える間隔[秒], 増え方, 画面に出す説明)
TRAITS = [
    (9, None, None, "9 balls, never grows"),
    (5, 7.0, "+1", "5 balls, +1 every 7s"),
    (2, 4.0, "+1", "2 balls, +1 every 4s"),
    (1, 8.5, "x2", "1 ball, x2 every 8.5s"),
]


# colorwar2: 数・大きさ・速さで勝負する条件（最初の個数, 増える間隔, 増え方, 説明, 大きさの倍率, 速さの倍率）。
# 倍率は試算で勝率をそろえて決める（下の値を変えたら、試算し直すこと）。
TRAITS2 = [
    (1, None, None, "1 giant, very fast", 4.0, 3.0),
    (2, None, None, "2 balls, fast", 1.0, 2.0),
    (8, None, None, "8 balls, slow", 1.0, 0.52),
    (4, None, None, "4 balls, normal", 1.0, 1.03),
]


def run_colorwar2(v, rng):
    """陣取り合戦の別バージョン: 大きい 1 個／速い 2 個／遅い 8 個／ふつう 4 個。
    registry からは外してある: だれも増えないので 36 秒間ほとんど勢力が動かず、見ていて退屈だった。
    使うなら、増える条件（colorwar の TRAITS のような）を足してから。"""
    return run_colorwar(v, rng, traits=TRAITS2)


def run_colorwar(v, rng, traits=None):
    traits = traits or TRAITS
    G, cell = 24, 40
    side = G * cell
    ox, oy = CX - side // 2, CY - side // 2 + 20
    total_time = 36.0
    order = list(range(4))
    rng.shuffle(order)
    teams = [TEAMS[i] for i in order]
    trait = list(traits)
    rng.shuffle(trait)                # trait[team] = その色の条件
    owner = np.zeros((G, G), dtype=np.int8)
    half = G // 2
    owner[half:, :half] = 1          # owner[x][y]
    owner[:half, half:] = 2
    owner[half:, half:] = 3
    br = 16.0
    # 条件に 5 つ目・6 つ目（大きさの倍率・速さの倍率）があれば使う（colorwar2 用）
    rad = [br * (trait[t][4] if len(trait[t]) > 4 else 1.0) for t in range(4)]
    fast = [trait[t][5] if len(trait[t]) > 5 else 1.0 for t in range(4)]
    chord = [60, 64, 67, 72]

    balls = []
    for t in range(4):
        x0 = ox + (0 if t in (0, 2) else side / 2)
        y0 = oy + (0 if t in (0, 1) else side / 2)
        for _ in range(trait[t][0]):
            a = rng.uniform(0, math.tau)
            balls.append([t, x0 + rng.uniform(60, side / 2 - 60), y0 + rng.uniform(60, side / 2 - 60),
                          math.cos(a), math.sin(a)])
    next_grow = [trait[t][1] for t in range(4)]
    labels = []                       # 増えた瞬間に浮かぶ文字 [x, y, 文字, 色, 経過]
    winner = None
    grid_surf = None if v.dry else pygame.Surface((G, G))
    while True:
        speed = 500 * (1 + 0.7 * min(v.t / total_time, 1.0))
        for _ in range(v.sub):
            if winner is not None:
                break
            for b in balls:
                team = b[0]
                br = rad[team]
                b[1] += b[3] * speed * fast[team] * v.dt
                b[2] += b[4] * speed * fast[team] * v.dt
                if b[1] - br < ox:
                    b[1], b[3] = ox + br, abs(b[3])
                elif b[1] + br > ox + side:
                    b[1], b[3] = ox + side - br, -abs(b[3])
                if b[2] - br < oy:
                    b[2], b[4] = oy + br, abs(b[4])
                elif b[2] + br > oy + side:
                    b[2], b[4] = oy + side - br, -abs(b[4])
                cx0 = max(0, int((b[1] - br - ox) // cell))
                cx1 = min(G - 1, int((b[1] + br - ox) // cell))
                cy0 = max(0, int((b[2] - br - oy) // cell))
                cy1 = min(G - 1, int((b[2] + br - oy) // cell))
                bounced = False
                for gx in range(cx0, cx1 + 1):
                    for gy in range(cy0, cy1 + 1):
                        if owner[gx, gy] == team:
                            continue
                        rx, ry = ox + gx * cell, oy + gy * cell
                        nx = min(max(b[1], rx), rx + cell)
                        ny = min(max(b[2], ry), ry + cell)
                        dx, dy = b[1] - nx, b[2] - ny
                        if dx * dx + dy * dy < br * br:
                            owner[gx, gy] = team
                            if not bounced:
                                bounced = True
                                if abs(dx) > abs(dy):
                                    b[3] = abs(b[3]) if dx > 0 else -abs(b[3])
                                else:
                                    b[4] = abs(b[4]) if dy > 0 else -abs(b[4])
                                a = rng.uniform(-0.08, 0.08)
                                b[3], b[4] = (b[3] * math.cos(a) - b[4] * math.sin(a),
                                              b[3] * math.sin(a) + b[4] * math.cos(a))
                                # ほぼ水平・垂直の往復にはまらないようにする
                                if abs(b[3]) < 0.25:
                                    b[3] = math.copysign(0.25, b[3] or 1)
                                if abs(b[4]) < 0.25:
                                    b[4] = math.copysign(0.25, b[4] or 1)
                                n = math.hypot(b[3], b[4])
                                b[3], b[4] = b[3] / n, b[4] / n
                                v.audio.note(v.t, chord[team] + rng.choice([0, 0, 12]), 0.26, "pluck",
                                             channel=f"t{team}", min_gap=0.07)
        # ---- 決まった間隔で増える（色ごとの条件どおり）
        for t in range(4):
            if winner is None and next_grow[t] is not None and v.t >= next_grow[t] and v.t < total_time - 0.5:
                next_grow[t] += trait[t][1]
                mine = [b for b in balls if b[0] == t]
                src = mine if trait[t][2] == "x2" else [rng.choice(mine)]
                for b in src:
                    a = rng.uniform(0, math.tau)
                    balls.append([t, b[1], b[2], math.cos(a), math.sin(a)])
                    labels.append([b[1], b[2], trait[t][2], teams[t][1], 0.0])
                    if trait[t][2] == "x2" and len(src) > 4:
                        labels.pop()
                if trait[t][2] == "x2" and len(src) > 4:      # 数が多いときは文字を 1 つにまとめる
                    mx = sum(b[1] for b in src) / len(src)
                    my = sum(b[2] for b in src) / len(src)
                    labels.append([mx, my, "x2", teams[t][1], 0.0])
                v.audio.note(v.t, chord[t] + 12, 0.7, "pop")
        for lb in labels:
            lb[4] += 1 / v.fps
        labels = [lb for lb in labels if lb[4] < 0.9]
        counts = [int((owner == t).sum()) for t in range(4)]
        if winner is None and v.t >= total_time:
            winner = max(range(4), key=lambda t: counts[t])
            done_at = v.t
            for i, n in enumerate((60, 64, 67, 72)):
                v.audio.note(v.t + 0.08 * i, n, 0.8, "piano")

        if not v.dry:
            v.begin(bg=(14, 14, 20))
            pal = np.array([mix((0, 0, 0), c, 0.78) for _, c in teams], dtype=np.uint8)
            pygame.surfarray.blit_array(grid_surf, pal[owner])
            v.surf.blit(pygame.transform.scale(grid_surf, (side, side)), (ox, oy))
            pygame.draw.rect(v.surf, (255, 255, 255), (ox - 5, oy - 5, side + 10, side + 10), 5)
            for b in balls:
                r_ = rad[b[0]]
                v.circle((20, 20, 26), (b[1], b[2]), r_ + 4)
                v.circle((255, 255, 255), (b[1], b[2]), r_)
                v.circle(teams[b[0]][1], (b[1], b[2]), r_ - 5)
            for x, y, s_, col, age in labels:
                v.text(s_, 84, (x, y - 30 - 70 * age), outline=6, alpha=int(255 * (1 - age / 0.9)))
            v.text("Which color takes over?", 88, (CX, 190))
            # 勢力バー
            x = ox
            for t in range(4):
                w = side * counts[t] / (G * G)
                pygame.draw.rect(v.surf, teams[t][1], (int(x), 250, int(w) + 1, 44))
                if w > 110:
                    v.text(f"{100 * counts[t] / (G * G):.0f}%", 40, (x + w / 2, 273), outline=3)
                x += w
            pygame.draw.rect(v.surf, (255, 255, 255), (ox - 3, 247, side + 6, 50), 3)
            # 各色の条件（盤の並びと同じ 2x2）と、いまの個数
            for t in range(4):
                lx = ox + (0 if t in (0, 2) else side / 2) + 8
                ly = 338 + (0 if t in (0, 1) else 58)
                n_now = sum(1 for b in balls if b[0] == t)
                pygame.draw.rect(v.surf, teams[t][1], (int(lx), int(ly - 17), 34, 34), border_radius=6)
                f = v.font(40)
                img = f.render(trait[t][3], True, (255, 255, 255))
                v.surf.blit(img, (int(lx + 46), int(ly - img.get_height() / 2)))
                f2 = v.font(40)
                img2 = f2.render(f"x{n_now}", True, teams[t][1])
                v.surf.blit(img2, (int(lx + side / 2 - 30 - img2.get_width()), int(ly - img2.get_height() / 2)))
            left = max(0.0, total_time - v.t)
            if winner is None:
                v.text(f"{left:0.0f}", 110, (CX, oy + side + 110))
                if v.t < 3.0:         # 冒頭だけ、それぞれの陣地の上に条件を大きく出す
                    al = int(255 * min(1.0, (3.0 - v.t) / 0.6))
                    for t in range(4):
                        qx = ox + side * (0.25 if t in (0, 2) else 0.75)
                        qy = oy + side * (0.25 if t in (0, 1) else 0.75)
                        a_, b_ = trait[t][3].split(", ")
                        v.text(a_.upper(), 84, (qx, qy - 36), outline=6, alpha=al)
                        v.text(b_.upper(), 56, (qx, qy + 36), outline=5, alpha=al)
            else:
                v.text(f"{teams[winner][0]} WINS", 150, (CX, CY), color=teams[winner][1], outline=7)
                v.text(trait[winner][3], 64, (CX, CY + 120), outline=5)
        v.end(glow=0.25)
        if winner is not None and v.t - done_at > 2.2:
            break
    return {"result": f"{teams[winner][0]} ({trait[winner][3]}) wins with {100 * counts[winner] / (G * G):.0f}%",
            "winner_trait": traits.index(trait[winner])}


# ============================================================ 5. HP バトル
def run_battle(v, rng):
    n = 6
    order = rng.sample(range(len(TEAMS)), n)
    half0 = 450.0
    balls = []
    for i in range(n):
        a = i / n * math.tau + rng.uniform(-0.2, 0.2)
        d = rng.uniform(0, math.tau)
        balls.append({"name": TEAMS[order[i]][0], "col": TEAMS[order[i]][1], "hp": 100,
                      "x": CX + math.cos(a) * 290, "y": CY + math.sin(a) * 290,
                      "vx": math.cos(d) * 520, "vy": math.sin(d) * 520, "alive": True, "flash": 0.0})
    cooldown = {}
    popups = []                 # [x, y, text, life, color]
    parts = Particles()
    winner = None
    done_at = None

    def radius(b):
        return 34 + b["hp"] * 0.42

    while True:
        half = half0 if v.t < 8 else max(210.0, half0 - (v.t - 8) * 9.0)     # だんだん狭くなる
        for _ in range(v.sub):
            alive = [b for b in balls if b["alive"]]
            for b in alive:
                b["x"] += b["vx"] * v.dt
                b["y"] += b["vy"] * v.dt
                r = radius(b)
                hit_wall = False
                if b["x"] - r < CX - half:
                    b["x"], b["vx"], hit_wall = CX - half + r, abs(b["vx"]), True
                elif b["x"] + r > CX + half:
                    b["x"], b["vx"], hit_wall = CX + half - r, -abs(b["vx"]), True
                if b["y"] - r < CY - half:
                    b["y"], b["vy"], hit_wall = CY - half + r, abs(b["vy"]), True
                elif b["y"] + r > CY + half:
                    b["y"], b["vy"], hit_wall = CY + half - r, -abs(b["vy"]), True
                if hit_wall:
                    v.audio.play(v.t, 900, 0.12, "click", channel="w", min_gap=0.05)
            for i in range(len(alive)):
                for j in range(i + 1, len(alive)):
                    a, b = alive[i], alive[j]
                    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                    ra, rb = radius(a), radius(b)
                    d = math.hypot(dx, dy) or 1e-6
                    if d >= ra + rb:
                        continue
                    nx, ny = dx / d, dy / d
                    ma, mb = ra * ra, rb * rb
                    rel = (a["vx"] - b["vx"]) * nx + (a["vy"] - b["vy"]) * ny
                    if rel > 0:
                        imp = 2 * rel / (ma + mb)
                        a["vx"] -= imp * mb * nx
                        a["vy"] -= imp * mb * ny
                        b["vx"] += imp * ma * nx
                        b["vy"] += imp * ma * ny
                    overlap = ra + rb - d
                    a["x"] -= nx * overlap * mb / (ma + mb)
                    a["y"] -= ny * overlap * mb / (ma + mb)
                    b["x"] += nx * overlap * ma / (ma + mb)
                    b["y"] += ny * overlap * ma / (ma + mb)
                    key = (id(a), id(b))
                    if v.t - cooldown.get(key, -9) > 0.22 and winner is None:
                        cooldown[key] = v.t
                        hits = []
                        for tgt in (a, b):
                            dmg = rng.randint(3, 8)
                            crit = rng.random() < 0.10
                            if crit:
                                dmg *= 2
                            hits.append((tgt, dmg, crit))
                        # 相打ちで両方消えると勝者がいなくなるので、体力の多い側を 1 だけ残す
                        if all(t["hp"] - d <= 0 for t, d, _ in hits):
                            keep = max((a, b), key=lambda t: t["hp"])
                            hits = [(t, (t["hp"] - 1 if t is keep else d), c) for t, d, c in hits]
                        for tgt, dmg, crit in hits:
                            if dmg <= 0:
                                continue
                            tgt["hp"] = max(0, tgt["hp"] - dmg)
                            tgt["flash"] = 1.0
                            popups.append([tgt["x"], tgt["y"] - radius(tgt) - 10, f"-{dmg}", 0.7,
                                           (255, 255, 255) if not crit else (255, 220, 60)])
                        v.audio.play(v.t, 150 + 9000 / (ra + rb), 0.6, "thud", channel="h", min_gap=0.04)
                        parts.burst(rng, (a["x"] + nx * ra, a["y"] + ny * ra), (255, 255, 255), n=8, speed=300, life=0.35)
            for b in balls:
                if b["alive"]:
                    # 速度を一定の範囲に保つ（体力が減るほど速い）
                    sp = math.hypot(b["vx"], b["vy"]) or 1e-6
                    want = min(max(sp, 430 + (100 - b["hp"]) * 2.2), 900)
                    b["vx"], b["vy"] = b["vx"] / sp * want, b["vy"] / sp * want
                    if b["hp"] <= 0:
                        b["alive"] = False
                        parts.burst(rng, (b["x"], b["y"]), b["col"], n=46, speed=620, life=1.0, size=9)
                        for k, m in enumerate((67, 62, 55)):
                            v.audio.note(v.t + 0.07 * k, m, 0.7, "pop")
            parts.step(v.dt)
            alive = [b for b in balls if b["alive"]]
            if winner is None and len(alive) <= 1:
                winner = alive[0] if alive else None
                done_at = v.t
                for k, m in enumerate((60, 64, 67, 72)):
                    v.audio.note(v.t + 0.3 + 0.08 * k, m, 0.8, "piano")
                if winner is None:
                    winner = {"name": "NOBODY", "col": (255, 255, 255), "hp": 0}
        for p in popups:
            p[1] -= 90 / v.fps
            p[3] -= 1 / v.fps
        popups = [p for p in popups if p[3] > 0]

        if not v.dry:
            v.begin(bg=(16, 16, 22))
            pygame.draw.rect(v.surf, (26, 26, 36), (CX - half, CY - half, 2 * half, 2 * half))
            pygame.draw.rect(v.surf, (255, 255, 255), (CX - half - 6, CY - half - 6, 2 * half + 12, 2 * half + 12), 6)
            for b in balls:
                if not b["alive"]:
                    continue
                b["flash"] = max(0.0, b["flash"] - 5.0 / v.fps)
                r = radius(b)
                v.circle(mix(b["col"], (0, 0, 0), 0.45), (b["x"], b["y"]), r + 5)
                v.circle(mix(b["col"], (255, 255, 255), b["flash"] * 0.8), (b["x"], b["y"]), r)
                v.text(str(b["hp"]), int(max(30, r * 0.95)), (b["x"], b["y"]), outline=3)
            parts.draw(v)
            for p in popups:
                v.text(p[2], 58, (p[0], p[1]), color=p[4], outline=3)
            v.text("Last ball standing wins", 92, (CX, 245))
            for i, b in enumerate(balls):
                px = CX - (n - 1) * 45 + i * 90
                v.circle(b["col"] if b["alive"] else (60, 60, 66), (px, CY + half0 + 120), 28)
                if not b["alive"]:
                    v.line((230, 230, 230), (px - 20, CY + half0 + 100), (px + 20, CY + half0 + 140), 5)
            if done_at is not None and v.t - done_at > 0.3:
                v.text(f"{winner['name']} WINS", 150, (CX, CY), color=winner["col"], outline=7)
        v.end(glow=0.3)
        if done_at is not None and v.t - done_at > 2.4:
            break
        if v.t > 90:
            break
    return {"result": f"{winner['name']} wins" if winner else "no winner"}
