"""sims_fill.py — 埋め尽くす型と、吸い込まれる型

  fillwave  形の中でボールが増え続け、いっぱいになると色の波が走って、最後に弾ける
  blackhole 8 色のボールが、育っていくブラックホールから逃げ回る。最後まで残った 1 個が勝ち
"""

import math

import numpy as np
import pygame
import pymunk

from engine import ARP_PAT, ARP_PROG, CX, CY, H, W, Particles, hsv, mix, penta
from sims_pack import _ball, _space, _steps


# ============================================================ fillwave
def _outline(kind, size=430.0, n=96):
    """形の輪郭（閉じた多角形の頂点）。中心は (CX, CY)。"""
    pts = []
    if kind == "heart":
        for i in range(n):
            a = i / n * math.tau
            x = 16 * math.sin(a) ** 3
            y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
            pts.append((CX + x * size / 16.5, CY + (y - 1.5) * size / 16.5))
    elif kind == "hexagon":
        for i in range(6):
            a = math.radians(30 + 60 * i)
            pts.append((CX + math.cos(a) * size, CY + math.sin(a) * size))
    elif kind == "diamond":
        pts = [(CX, CY - size * 1.05), (CX + size * 0.82, CY), (CX, CY + size * 1.05), (CX - size * 0.82, CY)]
    else:                                       # circle
        for i in range(n):
            a = i / n * math.tau
            pts.append((CX + math.cos(a) * size, CY + math.sin(a) * size))
    return pts


def _area(pts):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))) / 2


def run_fillwave(v, rng):
    """壁に当たるたびに 1 個増える。形がいっぱいになったら、左から右へ色の波が走って虹色に並び、最後に弾ける。"""
    kind = rng.choice(["heart", "hexagon", "circle", "diamond"])
    pts = _outline(kind)
    br = 11.0
    cap = int(_area(pts) * 0.70 / (math.pi * br * br))
    sp = _space(gravity=0.0)
    sp.iterations = 10
    walls = []
    for p, q in zip(pts, pts[1:] + pts[:1]):
        seg = pymunk.Segment(sp.static_body, p, q, 6)
        seg.elasticity, seg.friction = 1.0, 0.0
        seg.collision_type = 1
        sp.add(seg)
        walls.append(seg)
    # 壁に当たった瞬間は物理エンジンから受け取る（コマごとに調べると、コマ数によって見落とす回数が変わってしまう）
    touched = {}                                # ボールの body → 壁へ向かう向き

    def on_wall(arb, _space, _data):
        for s_ in arb.shapes:
            if s_.collision_type == 2:
                nrm = arb.normal if arb.shapes[0] is s_ else -arb.normal
                touched[s_.body] = (nrm.x, nrm.y)

    sp.on_collision(1, 2, begin=on_wall)
    hue0 = rng.random()
    balls = []                                  # [body, shape, 色, 次に増えてよい時刻, 波が通ったか]
    a = rng.uniform(0, math.tau)
    b, c = _ball(sp, (CX, CY - 40), br, vel=(math.cos(a) * 560, math.sin(a) * 560), elasticity=1.0, friction=0.0)
    c.collision_type = 2
    balls.append([b, c, hsv(hue0, 0.9, 1.0), 0.2, False])
    n_steps, dt = _steps(v)
    xs = [p[0] for p in pts]
    x_min, x_max = min(xs), max(xs)
    full_at = wave_done = burst_at = None
    seq = 0
    wave_x = None
    while True:
        for _ in range(n_steps):
            sp.step(dt)
        t = v.t
        if full_at is None:
            born = 0
            limit = max(2, len(balls) // 40)
            # 増えるほど、1 個が次に増えるまでの待ち時間を長くする（最初は速く、あとはなだらかに埋まっていく）
            wait = 0.35 + 3.4 * len(balls) / cap
            for item in list(balls):
                if len(balls) >= cap or born >= limit:
                    break
                body = item[0]
                if t < item[3] or body not in touched:
                    continue
                nx, ny = touched[body]          # 壁へ向かう向き。新しい球は壁から離れる側に出す
                col = hsv(hue0 + t * 0.045 + rng.uniform(-0.02, 0.02), 0.9, 1.0)
                ang = math.atan2(-ny, -nx) + rng.uniform(-0.9, 0.9)
                nb, nc = _ball(sp, (body.position.x - nx * br * 2.1, body.position.y - ny * br * 2.1), br,
                               vel=(math.cos(ang) * 520, math.sin(ang) * 520), elasticity=1.0, friction=0.0)
                nc.collision_type = 2
                item[3] = t + wait * rng.uniform(0.8, 1.2)
                balls.append([nb, nc, col, t + wait * rng.uniform(0.8, 1.2), False])
                born += 1
            touched.clear()
            if born and v.audio.note(t, ARP_PROG[(seq // 8) % 4][ARP_PAT[seq % 8]], 0.3, "marimba", channel="s", min_gap=0.07):
                seq += 1
            crowded = len(balls) > cap * 0.5
            for body, _c, _col, _n, _w in balls:
                spd = body.velocity.length
                if spd > 700:
                    body.velocity = body.velocity * (700 / spd)
                elif spd < 260 and not crowded:
                    ang = rng.uniform(0, math.tau)
                    body.velocity = (math.cos(ang) * 320, math.sin(ang) * 320)
            if len(balls) >= cap:
                full_at = t
                sp.damping = 0.05               # いっぱいになったら動きを落ち着かせる
                v.audio.note(t, 84, 0.7, "piano")
        elif wave_done is None:
            # 色の波: 左から右へ線が進み、通った球が位置に応じた虹色に変わる
            k = (t - full_at - 0.7) / 2.4
            if k >= 0:
                wave_x = x_min - 20 + (x_max - x_min + 40) * min(1.0, k)
                changed = 0
                for item in balls:
                    if not item[4] and item[0].position.x <= wave_x:
                        item[4] = True
                        u = (item[0].position.x - x_min) / (x_max - x_min)
                        item[2] = hsv(hue0 + 0.85 * u, 0.9, 1.0)
                        changed += 1
                if changed:
                    v.audio.note(t, penta(min(int(k * 20), 19), 60), 0.34, "glock", channel="w", min_gap=0.055, dur=0.5)
                if k >= 1.0:
                    wave_done = t
        elif burst_at is None and t - wave_done > 0.9:
            burst_at = t
            sp.damping = 1.0
            for seg in walls:
                sp.remove(seg)
            for body, _c, _col, _n, _w in balls:
                dx, dy = body.position.x - CX, body.position.y - CY
                d = math.hypot(dx, dy) or 1.0
                kk = rng.uniform(500, 1300)
                body.velocity = (dx / d * kk, dy / d * kk)
            v.audio.play(t, 85, 1.0, "thud")
            for i, mm in enumerate((48, 55, 60, 64, 67, 72)):
                v.audio.note(t + 0.03 * i, mm, 0.8, "piano")

        if not v.dry:
            v.begin(bg=(0, 0, 0))
            for body, _c, col, _n, _w in balls:
                x, y = body.position.x, body.position.y
                if -30 < x < W + 30 and -30 < y < H + 30:
                    v.circle(col, (x, y), br)
            if burst_at is None:
                pygame.draw.lines(v.surf, (245, 245, 245), True, pts, 6)
            if wave_x is not None and wave_done is None:
                glow = pygame.Surface((70, 1000), pygame.SRCALPHA)
                for i in range(70):
                    pygame.draw.line(glow, (255, 255, 255, int(120 * (i / 70) ** 2)), (i, 0), (i, 1000))
                v.surf.blit(glow, (int(wave_x) - 70, int(CY) - 500))
                pygame.draw.line(v.surf, (255, 255, 255), (wave_x, CY - 500), (wave_x, CY + 500), 4)
            v.text("Every wall hit = +1", 92, (CX, 215))
            pct = min(100, int(100 * len(balls) / cap))
            v.text(f"{pct}%" if full_at is None else "FULL", 150, (CX, CY + 640))
        v.end(glow=0.26)
        if burst_at is not None and v.t - burst_at > 2.4:
            break
        if v.t > 80:
            break
    return {"result": f"{kind}: 1 -> {len(balls)} balls, then the wave"}


# ============================================================ blackhole
HOLE_BALLS = [("RED", (255, 77, 90)), ("BLUE", (61, 139, 255)), ("GREEN", (61, 220, 132)), ("YELLOW", (255, 201, 60)),
              ("PURPLE", (178, 102, 255)), ("ORANGE", (255, 140, 50)), ("CYAN", (60, 220, 230)), ("PINK", (255, 110, 190))]


def run_blackhole(v, rng):
    """円の中心でブラックホールが育っていく。吸い込まれたボールは脱落。最後まで残った 1 個が勝ち。"""
    R = 450.0
    br = 22.0
    n = len(HOLE_BALLS)
    names = HOLE_BALLS[:]
    rng.shuffle(names)
    P = np.zeros((n, 2))
    V = np.zeros((n, 2))
    for i in range(n):
        a = i * math.tau / n + rng.uniform(-0.15, 0.15)
        d = rng.uniform(300, 400)
        P[i] = (CX + math.cos(a) * d, CY + math.sin(a) * d)
        va = a + math.pi / 2 * rng.choice((-1, 1)) + rng.uniform(-0.5, 0.5)
        V[i] = (math.cos(va) * 520, math.sin(va) * 520)
    alive = np.ones(n, dtype=bool)
    out_order = []
    grow = rng.uniform(5.2, 6.2)                # ブラックホールが 1 秒に大きくなる量（ピクセル）
    pull = 2.4e7                                # 引き寄せる強さ
    rh = 26.0
    parts = Particles()
    C = np.array([CX, CY], dtype=float)
    done_at = None
    eaten_fx = []                               # 吸い込まれた瞬間の輪 [色, 経過]
    while True:
        t = v.t
        for _ in range(v.sub):
            if done_at is not None:
                break
            dt = v.dt
            rh += (grow + 0.16 * t) * dt                         # だんだん速く育つ
            D = C - P
            d = np.hypot(D[:, 0], D[:, 1]) + 1e-6
            acc = pull / (d * d + 160.0 ** 2)
            V += D / d[:, None] * acc[:, None] * dt
            sp_ = np.hypot(V[:, 0], V[:, 1]) + 1e-6
            V *= (np.clip(sp_, 430, 640) / sp_)[:, None]         # 速さは一定の幅に保つ（止まらせない）
            P += V * dt
            # 壁
            D = P - C
            d = np.hypot(D[:, 0], D[:, 1]) + 1e-6
            N = D / d[:, None]
            vn = (V * N).sum(axis=1)
            hit = alive & (d + br > R) & (vn > 0)
            if hit.any():
                V[hit] -= 2 * vn[hit, None] * N[hit]
                P[hit] = C + N[hit] * (R - br)
                v.audio.note(t, ARP_PROG[len(out_order) % 4][int(hit.argmax()) % 5], 0.22, "marimba", channel="b", min_gap=0.09)
            # ボールどうし
            for i in range(n):
                if not alive[i]:
                    continue
                for j in range(i + 1, n):
                    if not alive[j]:
                        continue
                    dx, dy = P[j] - P[i]
                    dist = math.hypot(dx, dy)
                    if 0 < dist < 2 * br:
                        nx, ny = dx / dist, dy / dist
                        rel = (V[i, 0] - V[j, 0]) * nx + (V[i, 1] - V[j, 1]) * ny
                        if rel > 0:
                            V[i] -= rel * np.array([nx, ny])
                            V[j] += rel * np.array([nx, ny])
                        push = (2 * br - dist) / 2
                        P[i] -= push * np.array([nx, ny])
                        P[j] += push * np.array([nx, ny])
            # 吸い込み
            d = np.hypot(P[:, 0] - CX, P[:, 1] - CY)
            for i in np.nonzero(alive & (d < rh + br * 0.2))[0]:
                if alive.sum() <= 1:
                    break
                alive[i] = False
                out_order.append(int(i))
                col = names[int(i)][1]
                eaten_fx.append([col, 0.0])
                parts.burst(rng, (float(P[i, 0]), float(P[i, 1])), col, n=22, speed=260, life=0.5, gravity=False)
                v.audio.play(t, 220, 0.7, "pop")
                v.audio.note(t, 40 + 2 * len(out_order), 0.6, "piano", dur=0.7)
                P[i] = (-9999, -9999)
            if alive.sum() <= 1 and done_at is None:
                done_at = t
                for k, mm in enumerate((60, 64, 67, 72, 76)):
                    v.audio.note(t + 0.07 * k, mm, 0.8, "piano")
        parts.step(1 / v.fps)
        for fx in eaten_fx:
            fx[1] += 1 / v.fps
        eaten_fx = [fx for fx in eaten_fx if fx[1] < 0.5]

        if not v.dry:
            v.begin(bg=(0, 0, 0))
            v.circle((245, 245, 245), (CX, CY), R + 4, width=5)
            for k in range(6, 0, -1):                             # ブラックホールのまわりの光
                v.circle(mix((0, 0, 0), (150, 90, 255), 0.09 * (7 - k)), (CX, CY), rh + 7 * k)
            v.circle((0, 0, 0), (CX, CY), rh)
            v.circle((200, 150, 255), (CX, CY), rh, width=3)
            for col, age in eaten_fx:
                v.circle(mix(col, (0, 0, 0), age / 0.5), (CX, CY), rh + 90 * age, width=6)
            parts.draw(v)
            for i in range(n):
                if alive[i]:
                    for k in range(5, 0, -1):                     # 短い尾（すぐ消える）
                        tail = P[i] - V[i] * 0.012 * k
                        v.circle(mix((0, 0, 0), names[i][1], 0.5 - 0.08 * k), tail, br - 2.5 * k)
                    v.circle((255, 255, 255), P[i], br + 3)
                    v.circle(names[i][1], P[i], br)
            v.text("Don't fall in", 100, (CX, 170))
            for i, (name, col) in enumerate(names):               # 上の一覧（吸い込まれた色は暗くなる）
                px = CX - (n - 1) * 58 + i * 116
                v.circle(col if alive[i] else mix((0, 0, 0), col, 0.22), (px, 280), 26)
                if not alive[i]:
                    v.text(str(n - out_order.index(i)), 34, (px, 281), color=(170, 170, 180), outline=2)
            if done_at is not None:
                w = int(np.nonzero(alive)[0][0])
                v.text(f"{names[w][0]} WINS", 150, (CX, CY + 640), color=names[w][1], outline=7)
            else:
                v.text(f"{int(alive.sum())} left", 110, (CX, CY + 640))
        v.end(glow=0.3)
        if done_at is not None and v.t - done_at > 2.6:
            break
        if v.t > 80:
            break
    w = int(np.nonzero(alive)[0][0])
    return {"result": f"{names[w][0]} wins", "winner": names[w][0]}
