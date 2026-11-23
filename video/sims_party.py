"""sims_party.py — 爆弾まわしと、釘の板

  bomb    8 色のボールが円の中を逃げ回る。爆弾は触れた相手に移る。導火線が尽きたとき持っていた色が脱落。最後の 1 個が勝ち
  plinko  600 個のボールを釘の板に落とす。下の仕切りに積もった山が、最後に色の波で数えられる
"""

import math

import numpy as np
import pygame
import pymunk

from engine import CX, CY, Particles, hsv, mix, penta
from sims_fill import HOLE_BALLS
from sims_pack import _ball, _space, _steps


# ============================================================ bomb
def run_bomb(v, rng):
    """爆弾は 1 個だけで、消えない。持っているボールが別のボールに触れると移る。
    導火線が尽きると持ち主が吹き飛び、爆弾は転がり出て、次に触れたボールにくっつく。"""
    R = 450.0
    C = np.array([CX, CY + 20.0])
    br = 30.0
    bomb_r = 24.0
    n = len(HOLE_BALLS)
    names = HOLE_BALLS[:]
    rng.shuffle(names)
    P = np.zeros((n + 1, 2))                    # 最後の 1 行は爆弾（だれも持っていないとき）
    V = np.zeros((n + 1, 2))
    for i in range(n):
        a = i * math.tau / n + rng.uniform(-0.15, 0.15)
        P[i] = C + np.array([math.cos(a), math.sin(a)]) * rng.uniform(300, 380)
        va = rng.uniform(0, math.tau)
        V[i] = (math.cos(va), math.sin(va))
    P[n] = C
    V[n] = (P[0] - C) / float(np.hypot(*(P[0] - C)))       # 最初の爆弾は、中央から 1 個めがけて転がる
    alive = np.ones(n, dtype=bool)
    out_order = []
    fuses = [4.0, 4.0, 4.0, 3.5, 3.5, 3.0, 3.0]  # 何回目の爆発かで導火線の長さが決まる（だんだん短い）
    fuse = fuses[0]
    holder = None                               # 爆弾を持っているボール
    free_since = 0.0                            # 爆弾が転がり出た時刻（すぐには拾えない）
    last_pass = -9.0
    passes = 0
    last_tick = None
    speed = 430.0
    parts = Particles()
    booms = []                                  # 爆発の輪 [x, y, 色, 経過]
    links = []                                  # 爆弾が移った線 [x0, y0, x1, y1, 経過]
    flash = 0.0
    done_at = None
    while True:
        t = v.t
        for _ in range(v.sub):
            if done_at is not None:
                break
            dt = v.dt
            idx = [i for i in range(n) if alive[i]]
            # 向きを少しずつ変える: 持ち主は一番近い相手へ、ほかは持ち主から離れる
            if holder is not None:
                others = [i for i in idx if i != holder]
                d = [float(np.hypot(*(P[i] - P[holder]))) for i in others]
                tgt = others[int(np.argmin(d))]
                want = (P[tgt] - P[holder]) / (min(d) + 1e-6)
                V[holder] = V[holder] * (1 - 2.6 * dt) + want * 2.6 * dt
                for i, di in zip(others, d):
                    if di < 300:
                        away = (P[i] - P[holder]) / (di + 1e-6)
                        V[i] = V[i] * (1 - 1.5 * dt) + away * 1.5 * dt
            for i in idx + ([n] if holder is None else []):
                s_ = float(np.hypot(*V[i])) + 1e-9
                V[i] /= s_
                k = 1.22 if i == holder else (2.3 if i == n else 1.0)
                P[i] += V[i] * speed * k * dt
                # 壁
                D = P[i] - C
                d_ = float(np.hypot(*D)) + 1e-9
                rr = bomb_r if i == n else br
                if d_ + rr > R:
                    N = D / d_
                    vn = float(V[i] @ N)
                    if vn > 0:
                        V[i] -= 2 * vn * N
                    P[i] = C + N * (R - rr)
            # ボールどうし
            for a_ in range(len(idx)):
                i = idx[a_]
                for j in idx[a_ + 1:]:
                    D = P[j] - P[i]
                    dist = float(np.hypot(*D))
                    if 0 < dist < 2 * br:
                        N = D / dist
                        rel = float((V[i] - V[j]) @ N)
                        if rel > 0:
                            V[i] -= rel * N
                            V[j] += rel * N
                        push = (2 * br - dist) / 2
                        P[i] -= push * N
                        P[j] += push * N
                        if holder in (i, j) and t - last_pass > 0.4:      # 触れた相手に爆弾が移る
                            new = j if holder == i else i
                            links.append([*P[holder], *P[new], 0.0])
                            holder = new
                            last_pass = t
                            passes += 1
                            v.audio.note(t, penta(passes % 10, 60), 0.5, "marimba")
            # 転がっている爆弾を拾う
            if holder is None and t - free_since > 0.12:
                for i in idx:
                    if float(np.hypot(*(P[i] - P[n]))) < br + bomb_r:
                        holder = i
                        last_pass = t
                        last_tick = None
                        v.audio.note(t, 55, 0.6, "marimba")
                        v.audio.play(t, 300, 0.4, "click")
                        break
            # 導火線（持たれているあいだだけ進む）
            if holder is not None:
                fuse -= dt
                tick = math.ceil(fuse * (4 if fuse < 1.0 else 1))
                if tick != last_tick:
                    last_tick = tick
                    v.audio.play(t, 1500 if fuse < 1.0 else 1100, 0.45, "click")
                if fuse <= 0:
                    col = names[holder][1]
                    alive[holder] = False
                    out_order.append(holder)
                    parts.burst(rng, tuple(P[holder]), col, n=70, speed=900, life=0.9, size=9, gravity=False)
                    parts.burst(rng, tuple(P[holder]), (255, 220, 120), n=40, speed=600, life=0.6, size=6, gravity=False)
                    booms.append([*P[holder], col, 0.0])
                    flash = 1.0
                    v.audio.play(t, 55, 1.0, "thud")
                    v.audio.play(t, 82, 0.8, "thud")
                    v.audio.play(t, 180, 0.6, "pop")
                    v.audio.note(t, 36 + 2 * len(out_order), 0.6, "piano", dur=0.8)
                    # 爆風: ほかのボールは爆発から離れる向きへ弾かれ、爆弾は一番近いボールのほうへ飛び出す
                    best = None
                    for i in range(n):
                        if alive[i]:
                            D = P[i] - P[holder]
                            d_ = float(np.hypot(*D)) + 1e-9
                            V[i] = D / d_
                            if best is None or d_ < best[0]:
                                best = (d_, D / d_)
                    P[n] = P[holder]
                    if best is not None:
                        V[n] = best[1]
                    P[holder] = (-9999, -9999)
                    holder = None
                    free_since = t
                    if alive.sum() <= 1:
                        done_at = t
                        for k, mm in enumerate((60, 64, 67, 72, 76)):
                            v.audio.note(t + 0.35 + 0.07 * k, mm, 0.8, "piano")
                    else:
                        fuse = fuses[min(len(out_order), len(fuses) - 1)]
        parts.step(1 / v.fps)
        flash = max(0.0, flash - 4.0 / v.fps)
        for b in booms:
            b[3] += 1 / v.fps
        booms = [b for b in booms if b[3] < 0.6]
        for ln in links:
            ln[4] += 1 / v.fps
        links = [ln for ln in links if ln[4] < 0.25]

        if not v.dry:
            bg = mix((8, 8, 14), (120, 60, 30), flash * 0.4)
            v.begin(bg=bg)
            v.circle((16, 18, 30), C, R + 4)
            v.circle((245, 245, 245), C, R + 4, width=5)
            for x, y, col, age in booms:
                v.circle(mix((255, 240, 200), col, min(1, age / 0.3)), (x, y), 30 + 620 * age, width=max(2, int(14 * (1 - age / 0.6))))
            parts.draw(v)
            for x0, y0, x1, y1, age in links:
                v.line(mix((255, 230, 150), (16, 18, 30), age / 0.25), (x0, y0), (x1, y1), 8)
            danger = holder is not None and fuse < 1.0
            for i in range(n):
                if not alive[i]:
                    continue
                if i == holder:                 # 持ち主のまわりの赤い輪（導火線が短いほど速く脈打つ）
                    pulse = 0.5 + 0.5 * math.sin(t * (30 if danger else 12))
                    v.circle(mix((255, 60, 40), (255, 220, 120), pulse), P[i], br + 12 + 5 * pulse, width=6)
                v.circle((255, 255, 255), P[i], br + 3)
                v.circle(names[i][1], P[i], br)
            # 爆弾（黒い玉 + 導火線の火 + 残り秒）
            bp = P[holder] if holder is not None else P[n]
            if done_at is None:
                v.circle((255, 255, 255), bp, bomb_r - 3)
                v.circle((14, 14, 18), bp, bomb_r - 6)
                spark = (bp[0] + 15, bp[1] - 19)
                v.line((200, 170, 120), (bp[0] + 8, bp[1] - 12), spark, 4)
                v.circle(mix((255, 120, 30), (255, 240, 150), 0.5 + 0.5 * math.sin(t * 40)), spark, 6 + 2 * math.sin(t * 31))
                if holder is not None:
                    v.text(str(max(1, math.ceil(fuse))), 34, bp, color=(255, 90, 70) if danger else (255, 255, 255), outline=0)
            v.text("Hot potato", 110, (CX, 150))
            v.text("Touch to pass the bomb", 46, (CX, 226), color=(200, 205, 220), outline=3)
            for i, (name, col) in enumerate(names):               # 上の一覧（脱落した色は暗くなる）
                px = CX - (n - 1) * 58 + i * 116
                v.circle(col if alive[i] else mix((0, 0, 0), col, 0.22), (px, 310), 26)
                if not alive[i]:
                    v.text(str(n - out_order.index(i)), 34, (px, 311), color=(170, 170, 180), outline=2)
            # 導火線の棒
            if done_at is None:
                full = fuses[min(len(out_order), len(fuses) - 1)]
                bw = 700
                pygame.draw.rect(v.surf, (40, 42, 56), (CX - bw // 2, int(C[1] + R + 60), bw, 26), border_radius=13)
                k = max(0.0, fuse / full)
                colb = mix((255, 60, 40), (255, 200, 80), k)
                pygame.draw.rect(v.surf, colb, (CX - bw // 2, int(C[1] + R + 60), max(4, int(bw * k)), 26), border_radius=13)
                v.text(f"{int(alive.sum())} left", 100, (CX, C[1] + R + 170))
            else:
                w = int(np.nonzero(alive)[0][0])
                v.text(f"{names[w][0]} WINS", 150, (CX, C[1] + R + 150), color=names[w][1], outline=7)
        v.end(glow=0.3)
        if done_at is not None and v.t - done_at > 2.8:
            break
        if v.t > 90:
            break
    w = int(np.nonzero(alive)[0][0])
    return {"result": f"{names[w][0]} wins", "winner": names[w][0]}


# ============================================================ plinko
def run_plinko(v, rng):
    """ボールを 1 か所から落とし続ける。釘で左右に散って、下の 13 個の仕切りに積もる。
    全部落ちたら、左から右へ色の波が走って 1 列ずつ数え、最後に底が開いて全部流れ落ちる。"""
    total = 600
    bins = 13
    dx, dy = 68.0, 60.0
    rows = 12
    left = CX - bins * dx / 2
    right = CX + bins * dx / 2
    top = 430.0
    bin_top = top + rows * dy - 6
    floor_y = 1740.0
    br, pr = 8.0, 7.0
    sp = _space(gravity=1000.0)
    sp.iterations = 12
    sp.damping = 0.07                           # 空気の抵抗。落ちる速さに上限ができ、釘で大きく跳ねなくなる
    st = sp.static_body
    for x in (left, right):
        s_ = pymunk.Segment(st, (x, 260), (x, floor_y), 4)
        s_.elasticity, s_.friction = 0.4, 0.3
        sp.add(s_)
    for k in range(1, bins):
        s_ = pymunk.Segment(st, (left + k * dx, bin_top), (left + k * dx, floor_y), 3)
        s_.elasticity, s_.friction = 0.2, 0.3
        sp.add(s_)
    floor = pymunk.Segment(st, (left, floor_y), (right, floor_y), 5)
    floor.elasticity, floor.friction = 0.1, 0.6
    sp.add(floor)
    # じょうご（落とす場所を 1 か所にそろえる）
    for sx in (-1, 1):
        s_ = pymunk.Segment(st, (CX + sx * 150, 270), (CX + sx * 40, 372), 4)
        s_.elasticity, s_.friction = 0.2, 0.2
        sp.add(s_)
    pegs = []
    for r_ in range(rows):
        y = top + r_ * dy
        xs = [left + k * dx for k in range(1, bins)] if r_ % 2 == 0 else [left + dx / 2 + k * dx for k in range(bins)]
        for x in xs:
            c = pymunk.Circle(st, pr, (x, y))
            c.elasticity, c.friction = 0.3, 0.2
            c.collision_type = 1
            c.row = r_
            sp.add(c)
            pegs.append([x, y, r_, -9.0])
    peg_of = {(round(p[0]), round(p[1])): p for p in pegs}
    hits = []

    def on_peg(arb, _space, _data):
        for s_ in arb.shapes:
            if s_.collision_type == 1:
                hits.append((round(s_.offset.x), round(s_.offset.y)))

    sp.on_collision(1, 2, begin=on_peg)
    balls = []                                  # [body, 色]
    plain = (205, 215, 235)
    n_steps, dt = _steps(v)
    dropped = 0
    next_drop = 0.6
    last_drop = None
    wave_at = None
    counts = None
    shown = 0                                   # 波が通り過ぎた仕切りの数
    curve_at = open_at = None
    while True:
        t = v.t
        # 落とす間隔: 最初はゆっくり（1 個ずつの道筋が見える）、だんだん速く
        while dropped < total and t >= next_drop:
            # 3 つの位置から順に落とす（同じ場所に続けて出すと、前の玉と重なってしまう）
            b, c = _ball(sp, (CX + (dropped % 3 - 1) * 22 + rng.uniform(-2, 2), 318), br, vel=(rng.uniform(-20, 20), 320),
                         elasticity=0.3, friction=0.2)
            c.collision_type = 2
            balls.append([b, plain])
            dropped += 1
            last_drop = t
            rate = 2.0 + 34.0 * min(1.0, dropped / 90.0)
            next_drop += 1.0 / rate
        for _ in range(n_steps):
            sp.step(dt)
        for key in hits:
            p = peg_of.get(key)
            if p is not None:
                p[3] = t
                v.audio.note(t, penta(11 - p[2] + (int(p[0]) // 68) % 3, 60), 0.16, "marimba", channel=f"r{p[2]}", min_gap=0.07)
        hits.clear()
        if dropped >= total and wave_at is None and t - last_drop > 5.2:
            wave_at = t
            counts = [0] * bins
            for it in balls:
                k = min(bins - 1, max(0, int((it[0].position.x - left) // dx)))
                counts[k] += 1
                it.append(k)
        if wave_at is not None and curve_at is None:
            k_now = int((t - wave_at) / 0.22)
            while shown < min(bins, k_now + 1):
                col = hsv(0.62 - 0.62 * shown / (bins - 1), 0.85, 1.0)
                for it in balls:
                    if it[2] == shown:
                        it[1] = col
                # 山の高さで音の高さが決まる（上って下る旋律になる）
                v.audio.note(t, penta(int(round(counts[shown] / max(counts) * 12)), 60), 0.6, "glock")
                shown += 1
            if shown >= bins and t - wave_at > bins * 0.22 + 0.5:
                curve_at = t
                for k, mm in enumerate((60, 64, 67, 72, 76, 79)):
                    v.audio.note(t + 0.06 * k, mm, 0.7, "piano")
        if curve_at is not None and open_at is None and t - curve_at > 2.2:
            open_at = t
            sp.remove(floor)
            v.audio.play(t, 70, 0.9, "thud")
        if open_at is not None:
            for it in balls:
                if floor_y < it[0].position.y < floor_y + 30:
                    v.audio.note(t, penta(rng.randrange(8), 72), 0.1, "glock", channel="out", min_gap=0.03)

        if not v.dry:
            v.begin(bg=(8, 10, 18))
            pygame.draw.rect(v.surf, (14, 17, 30), (int(left), 262, int(right - left), int(floor_y - 262)))
            for x in (left, right):
                v.line((235, 235, 240), (x, 260), (x, floor_y), 6)
            for sx in (-1, 1):
                v.line((235, 235, 240), (CX + sx * 150, 270), (CX + sx * 40, 372), 6)
            for k in range(1, bins):
                v.line((120, 130, 160), (left + k * dx, bin_top), (left + k * dx, floor_y), 4)
            if open_at is None:
                v.line((235, 235, 240), (left, floor_y), (right, floor_y), 8)
            for x, y, r_, ht in pegs:
                g = max(0.0, 1 - (t - ht) / 0.25)
                v.circle(mix((150, 160, 190), (255, 240, 170), g), (x, y), pr + 2 * g)
            for it in balls:
                p = it[0].position
                if p.y < 1960:
                    v.circle(it[1], (p.x, p.y), br)
            if counts is not None and open_at is None:
                for k in range(shown):
                    col = hsv(0.62 - 0.62 * k / (bins - 1), 0.85, 1.0)
                    v.text(str(counts[k]), 40, (left + (k + 0.5) * dx, floor_y + 44), color=col, outline=2)
            if curve_at is not None and open_at is None:
                # 山の頂上をなめらかにつないだ線
                a = min(1.0, (t - curve_at) / 0.6)
                tops = []
                for k in range(bins):
                    ys = [it[0].position.y for it in balls if it[2] == k]
                    tops.append((left + (k + 0.5) * dx, (min(ys) - br - 14) if ys else floor_y - 14))
                m = max(2, int(len(tops) * a))
                for p0, p1 in zip(tops[:m], tops[1:m]):
                    v.line((255, 255, 255), p0, p1, 7)
            v.text(f"Where do {total} balls land?", 84, (CX, 140))
            v.text(f"{dropped} / {total}", 64, (CX, 215), color=(200, 205, 220), outline=3)
        v.end(glow=0.22)
        if open_at is not None and t - open_at > 2.4:
            break
        if v.t > 80:
            break
    return {"result": f"counts {counts}", "counts": counts}
