"""sims_more.py — 武器バトル（1 対 1） / ブロック掘りレース"""

import math

import pygame

from engine import CX, CY, Particles, mix, penta

# 武器はすべて自前の図形。当てるたびに武器ごとの能力が伸びる。
WEAPONS = {
    "SWORD": {"len": 160, "spin": 6.0, "dmg": 6, "col": (110, 190, 255)},     # 当てるたび威力 +1
    "DAGGER": {"len": 105, "spin": 11.0, "dmg": 5, "col": (110, 240, 150)},     # 当てるたび回転が速くなる
    "SPEAR": {"len": 225, "spin": 4.4, "dmg": 10, "col": (255, 205, 80)},      # 当てるたび長くなる
    "HAMMER": {"len": 120, "spin": 2.7, "dmg": 11, "col": (255, 110, 110)},    # 当てるたび威力 +2、大きく吹き飛ばす
}


def _seg_point(px, py, x1, y1, x2, y2):
    ex, ey = x2 - x1, y2 - y1
    t = ((px - x1) * ex + (py - y1) * ey) / ((ex * ex + ey * ey) or 1e-9)
    t = min(1.0, max(0.0, t))
    return x1 + ex * t, y1 + ey * t


def _seg_seg(a, b):
    """線分どうしの最短距離と、その中点。"""
    best = (1e9, 0.0, 0.0)
    for (px, py), s in ((a[0:2], b), (a[2:4], b), (b[0:2], a), (b[2:4], a)):
        qx, qy = _seg_point(px, py, *s)
        d = math.hypot(px - qx, py - qy)
        if d < best[0]:
            best = (d, (px + qx) / 2, (py + qy) / 2)
    return best


def run_weapon(v, rng):
    names = rng.sample(list(WEAPONS), 2)
    half = 430.0
    R = 62.0
    fighters = []
    for i, name in enumerate(names):
        w = dict(WEAPONS[name])
        a = rng.uniform(0, math.tau)
        fighters.append({"name": name, "w": w, "col": w["col"], "hp": 100,
                         "x": CX + (-220 if i == 0 else 220), "y": CY + rng.uniform(-150, 150),
                         "vx": math.cos(a) * 560, "vy": math.sin(a) * 560,
                         "ang": rng.uniform(0, math.tau), "dir": rng.choice([-1, 1]),
                         "cool": 0.0, "flash": 0.0, "hits": 0})
    g = 650.0
    parry_cool = 0.0
    hitstop = 0.0
    popups = []
    parts = Particles()
    winner = None
    done_at = None

    def blade(f):
        ux, uy = math.cos(f["ang"]), math.sin(f["ang"])
        return (f["x"] + ux * R * 0.7, f["y"] + uy * R * 0.7,
                f["x"] + ux * (R + f["w"]["len"]), f["y"] + uy * (R + f["w"]["len"]))

    def stat(f):
        w = f["w"]
        return {"SWORD": f"DMG {w['dmg']}", "DAGGER": f"SPIN {w['spin']:.0f}",
                "SPEAR": f"LENGTH {w['len']:.0f}", "HAMMER": f"DMG {w['dmg']}"}[f["name"]]

    while True:
        for _ in range(v.sub):
            parts.step(v.dt)
            if hitstop > 0:                 # 当たった瞬間だけ一瞬止める（重さの演出）
                hitstop -= v.dt
                continue
            if winner is not None:
                continue
            parry_cool -= v.dt
            for f in fighters:
                f["cool"] -= v.dt
                f["ang"] += f["dir"] * f["w"]["spin"] * v.dt
                f["vy"] += g * v.dt
                f["x"] += f["vx"] * v.dt
                f["y"] += f["vy"] * v.dt
                if f["x"] - R < CX - half:
                    f["x"], f["vx"] = CX - half + R, abs(f["vx"])
                elif f["x"] + R > CX + half:
                    f["x"], f["vx"] = CX + half - R, -abs(f["vx"])
                if f["y"] - R < CY - half:
                    f["y"], f["vy"] = CY - half + R, abs(f["vy"])
                elif f["y"] + R > CY + half:
                    f["y"], f["vy"] = CY + half - R, -abs(f["vy"])
                sp = math.hypot(f["vx"], f["vy"]) or 1e-6
                want = min(max(sp, 480.0), 980.0)
                f["vx"], f["vy"] = f["vx"] / sp * want, f["vy"] / sp * want
            a, b = fighters
            dx, dy = b["x"] - a["x"], b["y"] - a["y"]
            d = math.hypot(dx, dy) or 1e-6
            if d < 2 * R:                   # 本体どうしの衝突
                nx, ny = dx / d, dy / d
                rel = (a["vx"] - b["vx"]) * nx + (a["vy"] - b["vy"]) * ny
                if rel > 0:
                    a["vx"] -= rel * nx
                    a["vy"] -= rel * ny
                    b["vx"] += rel * nx
                    b["vy"] += rel * ny
                push = (2 * R - d) / 2
                a["x"] -= nx * push
                a["y"] -= ny * push
                b["x"] += nx * push
                b["y"] += ny * push
            sa, sb = blade(a), blade(b)
            dist, mx, my = _seg_seg(sa, sb)
            if dist < 18 and parry_cool <= 0:        # 武器どうしがぶつかると弾き合う
                parry_cool = 0.28
                a["dir"], b["dir"] = -a["dir"], -b["dir"]
                parts.burst(rng, (mx, my), (255, 255, 200), n=10, speed=420, life=0.3, size=4, gravity=False)
                v.audio.play(v.t, 2200, 0.35, "click")
                v.audio.play(v.t, 3300, 0.25, "click")
            for atk, dfd, seg in ((a, b, sa), (b, a, sb)):
                if atk["cool"] > 0:
                    continue
                if atk["name"] == "HAMMER":
                    qx, qy = seg[2], seg[3]
                    reach = R + 36
                else:
                    qx, qy = _seg_point(dfd["x"], dfd["y"], *seg)
                    reach = R + 9
                ddx, ddy = dfd["x"] - qx, dfd["y"] - qy
                dd = math.hypot(ddx, ddy) or 1e-6
                if dd >= reach:
                    continue
                w = atk["w"]
                dmg = w["dmg"]
                dfd["hp"] = max(0, dfd["hp"] - dmg)
                dfd["flash"] = 1.0
                atk["cool"] = 0.32
                atk["hits"] += 1
                kb = 520 if atk["name"] == "HAMMER" else 300
                dfd["vx"] += ddx / dd * kb
                dfd["vy"] += ddy / dd * kb
                hitstop = 0.05
                popups.append([dfd["x"], dfd["y"] - R - 20, f"-{dmg}", 0.8, atk["col"]])
                parts.burst(rng, (qx, qy), (255, 255, 255), n=14, speed=460, life=0.4, size=6, gravity=False)
                v.audio.play(v.t, 150 if atk["name"] == "HAMMER" else 230, 0.75, "thud")
                v.audio.note(v.t, penta(min(atk["hits"], 14), 60), 0.35, "pluck")
                if atk["name"] == "SWORD":
                    w["dmg"] += 1
                elif atk["name"] == "DAGGER":
                    w["spin"] = min(30.0, w["spin"] * 1.13)
                elif atk["name"] == "SPEAR":
                    w["len"] = min(430.0, w["len"] + 16)
                else:
                    w["dmg"] += 2
                if dfd["hp"] <= 0:
                    winner = atk
                    done_at = v.t
                    parts.burst(rng, (dfd["x"], dfd["y"]), dfd["col"], n=60, speed=700, life=1.1, size=10)
                    for k, m in enumerate((67, 62, 55)):
                        v.audio.note(v.t + 0.07 * k, m, 0.7, "pop")
                    for k, m in enumerate((60, 64, 67, 72)):
                        v.audio.note(v.t + 0.45 + 0.08 * k, m, 0.8, "piano")
                    break
        for p in popups:
            p[1] -= 100 / v.fps
            p[3] -= 1 / v.fps
        popups = [p for p in popups if p[3] > 0]

        if not v.dry:
            v.begin(bg=(16, 16, 22))
            pygame.draw.rect(v.surf, (26, 26, 36), (CX - half, CY - half, 2 * half, 2 * half))
            pygame.draw.rect(v.surf, (255, 255, 255), (CX - half - 6, CY - half - 6, 2 * half + 12, 2 * half + 12), 6)
            for f in fighters:
                if winner is not None and f is not winner:
                    continue
                f["flash"] = max(0.0, f["flash"] - 5.0 / v.fps)
                x1, y1, x2, y2 = blade(f)
                wide = 22 if f["name"] == "HAMMER" else (14 if f["name"] == "DAGGER" else 18)
                v.line(mix(f["col"], (0, 0, 0), 0.5), (x1, y1), (x2, y2), wide + 8)
                v.line(mix(f["col"], (255, 255, 255), 0.55), (x1, y1), (x2, y2), wide)
                if f["name"] == "HAMMER":
                    v.circle(mix(f["col"], (0, 0, 0), 0.5), (x2, y2), 40)
                    v.circle(mix(f["col"], (255, 255, 255), 0.55), (x2, y2), 34)
                elif f["name"] == "SPEAR":
                    v.circle(mix(f["col"], (255, 255, 255), 0.8), (x2, y2), 15)
                v.circle(mix(f["col"], (0, 0, 0), 0.45), (f["x"], f["y"]), R + 5)
                v.circle(mix(f["col"], (255, 255, 255), f["flash"] * 0.8), (f["x"], f["y"]), R)
                v.text(str(f["hp"]), 64, (f["x"], f["y"]), outline=3)
            parts.draw(v)
            for p in popups:
                v.text(p[2], 72, (p[0], p[1]), color=p[4], outline=4)
            v.text(f"{names[0]} vs {names[1]}", 96, (CX, 215))
            for i, f in enumerate(fighters):                 # HP バーと能力値
                bx = CX - 460 + i * 480
                pygame.draw.rect(v.surf, (50, 50, 60), (bx, 290, 440, 40))
                pygame.draw.rect(v.surf, f["col"], (bx, 290, int(440 * f["hp"] / 100), 40))
                pygame.draw.rect(v.surf, (255, 255, 255), (bx - 3, 287, 446, 46), 3)
                v.text(stat(f), 56, (bx + 220, 376), color=f["col"], outline=3)
            if done_at is not None and v.t - done_at > 0.35:
                v.text(f"{winner['name']} WINS", 150, (CX, CY), color=winner["col"], outline=7)
        v.end(glow=0.3)
        if done_at is not None and v.t - done_at > 2.4:
            break
        if v.t > 90:
            break
    return {"result": f"{names[0]} vs {names[1]}: {winner['name'] if winner else 'nobody'} wins",
            "title_extra": f"{names[0]} vs {names[1]}"}


# ============================================================ ブロック掘りレース
def run_bricks(v, rng):
    lanes = 4
    lane_w = 235
    x0 = CX - lanes * lane_w // 2
    cols, rows = 4, 11
    bw, bh = 56, 52
    top = 720
    bottom = top + rows * bh
    cols_team = rng.sample([(255, 77, 90), (61, 139, 255), (61, 220, 132), (255, 201, 60),
                            (178, 102, 255), (255, 140, 50)], lanes)
    names_all = {(255, 77, 90): "RED", (61, 139, 255): "BLUE", (61, 220, 132): "GREEN", (255, 201, 60): "YELLOW",
                 (178, 102, 255): "PURPLE", (255, 140, 50): "ORANGE"}
    # どのレーンも同じ並びのブロック（公平）
    layout = [[1 + (r // 4) + (1 if rng.random() < 0.2 else 0) for _ in range(cols)] for r in range(rows)]
    bricks = [[row[:] for row in layout] for _ in range(lanes)]
    br = 15.0
    g = 1500.0
    balls = []
    for i in range(lanes):
        lx = x0 + i * lane_w
        balls.append({"x": lx + lane_w / 2 + rng.uniform(-40, 40), "y": 520.0,
                      "vx": rng.choice([-1, 1]) * rng.uniform(160, 300), "vy": 0.0, "done": None})
    parts = Particles()
    winner = None
    done_at = None
    while True:
        for _ in range(v.sub):
            for i, b in enumerate(balls):
                if b["done"] is not None and b["y"] > bottom + 400:
                    continue
                lx = x0 + i * lane_w
                pad = (lane_w - cols * bw) / 2
                b["vy"] += g * v.dt
                b["x"] += b["vx"] * v.dt
                b["y"] += b["vy"] * v.dt
                if b["x"] - br < lx + 4:
                    b["x"], b["vx"] = lx + 4 + br, abs(b["vx"])
                elif b["x"] + br > lx + lane_w - 4:
                    b["x"], b["vx"] = lx + lane_w - 4 - br, -abs(b["vx"])
                if b["y"] - br < 470:
                    b["y"], b["vy"] = 470 + br, abs(b["vy"])
                r0 = max(0, int((b["y"] - br - top) // bh))
                r1 = min(rows - 1, int((b["y"] + br - top) // bh))
                hit = False
                for r in range(r0, r1 + 1):
                    for c in range(cols):
                        if bricks[i][r][c] <= 0 or hit:
                            continue
                        rx, ry = lx + pad + c * bw, top + r * bh
                        nx = min(max(b["x"], rx), rx + bw)
                        ny = min(max(b["y"], ry), ry + bh)
                        dx, dy = b["x"] - nx, b["y"] - ny
                        if dx * dx + dy * dy < br * br:
                            hit = True
                            bricks[i][r][c] -= 1
                            if abs(dx) > abs(dy):
                                b["vx"] = math.copysign(max(abs(b["vx"]), 220), dx)
                            else:
                                if dy < 0:          # 上から当たった → 一定の強さで跳ね上がる
                                    b["vy"] = -rng.uniform(430, 560)
                                    b["vx"] = rng.uniform(-330, 330)
                                else:
                                    b["vy"] = abs(b["vy"])
                            v.audio.note(v.t, penta(r, 55), 0.34, "pluck", channel=f"l{i}", min_gap=0.045)
                            if bricks[i][r][c] <= 0:
                                parts.burst(rng, (rx + bw / 2, ry + bh / 2), cols_team[i], n=7, speed=260, life=0.45, size=5)
                if b["done"] is None and b["y"] - br > bottom + 6:
                    b["done"] = v.t
                    if winner is None:
                        winner = i
                        done_at = v.t
                        for k, m in enumerate((60, 64, 67, 72, 76)):
                            v.audio.note(v.t + 0.07 * k, m, 0.8, "piano")
            parts.step(v.dt)

        if not v.dry:
            v.begin(bg=(16, 16, 22))
            for i in range(lanes):
                lx = x0 + i * lane_w
                pad = (lane_w - cols * bw) / 2
                pygame.draw.rect(v.surf, (26, 26, 36), (lx + 4, 470, lane_w - 8, bottom - 470 + 120))
                pygame.draw.rect(v.surf, cols_team[i], (lx + 4, 470, lane_w - 8, bottom - 470 + 120), 4)
                for r in range(rows):
                    for c in range(cols):
                        hp = bricks[i][r][c]
                        if hp <= 0:
                            continue
                        shade = mix((70, 74, 96), (200, 205, 230), min(1.0, hp / 4))
                        rect = (int(lx + pad + c * bw + 2), top + r * bh + 2, bw - 4, bh - 4)
                        pygame.draw.rect(v.surf, shade, rect, border_radius=6)
                        v.text(str(hp), 30, (rect[0] + rect[2] / 2, rect[1] + rect[3] / 2), color=(20, 20, 28), outline=0)
                pygame.draw.rect(v.surf, mix(cols_team[i], (0, 0, 0), 0.6), (lx + 6, bottom + 10, lane_w - 12, 104))
                v.text("FINISH", 40, (lx + lane_w / 2, bottom + 62), outline=3)
            for i, b in enumerate(balls):
                if b["y"] < bottom + 110:
                    v.circle((255, 255, 255), (b["x"], b["y"]), br + 3)
                    v.circle(cols_team[i], (b["x"], b["y"]), br)
            parts.draw(v)
            v.text("First to break through wins", 84, (CX, 240))
            v.text("Pick a color!", 70, (CX, 350), color=(210, 210, 220))
            if winner is not None:
                v.text(f"{names_all[cols_team[winner]]} WINS", 150, (CX, 600), color=cols_team[winner], outline=7)
        v.end(glow=0.3)
        if done_at is not None and v.t - done_at > 2.4:
            break
        if v.t > 95:
            break
    return {"result": f"{names_all[cols_team[winner]]} wins" if winner is not None else "no finisher"}
