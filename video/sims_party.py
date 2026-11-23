"""sims_party.py — 爆弾まわしと、釘の板

  bomb    8 色のボールが円の中を逃げ回る。爆弾は触れた相手に移る。導火線が尽きたとき持っていた色が脱落。最後の 1 個が勝ち
  plinko  600 個のボールを釘の板に落とす。下の仕切りに積もった山が、最後に色の波で数えられる
  merge   数字の付いたボールが落ちてくる。同じ数字どうしが触れるとまとまって倍になる。1024 ができたら終わり
  chain   折り返す帯に並んだ 1,000 個の点が、1 個のボールをきっかけに次々と弾け、最後に爆弾へ届く
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


# ============================================================ merge
MERGE_TOP = 10                                  # 2 の 10 乗 = 1024 ができたら終わり


def _merge_r(k):
    return 21.0 * 1.24 ** k


def run_merge(v, rng):
    """上の口が左右に動きながら、数字の付いたボールを落とす。同じ数字どうしが触れると 1 個にまとまって倍になる。
    1024 ができたら、全部が弾けて終わり。"""
    left, right = CX - 430.0, CX + 430.0
    top, floor_y = 430.0, 1610.0                 # 題名を画面の端から離すため、全体を少し下げてある
    sp = _space(gravity=1700.0)
    sp.iterations = 14
    st = sp.static_body
    dip = 150.0                                 # 底は V 字。大きい玉がまん中に集まって、同じ数字どうしが出会いやすい
    WALLS = (((left, top - 200), (left, floor_y - dip)), ((right, top - 200), (right, floor_y - dip)),
             ((left, floor_y - dip), (CX, floor_y)), ((CX, floor_y), (right, floor_y - dip)))
    for p, q in WALLS:
        s_ = pymunk.Segment(st, p, q, 6)
        s_.elasticity, s_.friction = 0.1, 0.05
        sp.add(s_)
    pairs = []

    def on_touch(arb, _space, _data):
        a, b = arb.shapes
        if a.level == b.level:
            pairs.append((a, b))

    sp.on_collision(2, 2, begin=on_touch)
    balls = {}                                  # shape → [body, レベル, できた時刻]

    def add(pos, k, t, vel=(0, 0)):
        r = _merge_r(k)
        b, c = _ball(sp, pos, r, vel=vel, elasticity=0.1, friction=0.05, mass=0.5 * 1.5 ** k)
        c.collision_type = 2
        c.level = k
        balls[c] = [b, k, t]
        return c

    def color(k):
        return hsv(0.58 - 0.065 * k, 0.78, 1.0) if k < MERGE_TOP else (255, 255, 255)

    n_steps, dt = _steps(v)
    next_drop = 0.5
    dropped = 0
    best = 1
    pops = []                                   # まとまった瞬間の輪 [x, y, 色, 経過, 半径]
    parts = Particles()
    done_at = burst_at = None
    nozzle_x = CX
    while True:
        t = v.t
        # 落とす口は一定の調子で左右に往復する
        nozzle_x = CX + math.sin(t * 1.9) * 330
        if done_at is None and t >= next_drop:
            # 落ちてくる数字は、いちばん大きい玉に合わせて上がっていく（小さい数字ばかりだと、いつまでも届かない）
            lo = max(1, best - 6)
            k = rng.choices((lo, lo + 1, lo + 2), weights=(6, 3, 1))[0]
            add((nozzle_x, top - 120), k, t, vel=(0, 500))
            dropped += 1
            next_drop += max(0.085, 0.30 - 0.012 * dropped)
            v.audio.play(t, 900, 0.10, "click", channel="d", min_gap=0.05)
        for _ in range(n_steps):
            sp.step(dt)
            if pairs and done_at is None:
                for a, b in pairs:
                    if a in balls and b in balls and balls[a][1] == balls[b][1]:
                        ba, bb = balls[a][0], balls[b][0]
                        k = balls[a][1] + 1
                        pos = ((ba.position.x + bb.position.x) / 2, (ba.position.y + bb.position.y) / 2)
                        vel = ((ba.velocity.x + bb.velocity.x) / 2, (ba.velocity.y + bb.velocity.y) / 2)
                        sp.remove(ba, a, bb, b)
                        del balls[a], balls[b]
                        add(pos, k, t, vel=vel)
                        pops.append([pos[0], pos[1], color(k), 0.0, _merge_r(k)])
                        v.audio.note(t, 48 + 3 * k + (k // 2), 0.25 + 0.05 * k, "marimba", channel=f"m{k}", min_gap=0.04)
                        if k > best:
                            best = k
                            v.audio.note(t, 60 + 2 * k, 0.6, "glock")
                        if k >= MERGE_TOP:
                            done_at = t
                            for i, mm in enumerate((60, 64, 67, 72, 76, 79)):
                                v.audio.note(t + 0.06 * i, mm, 0.8, "piano")
            pairs.clear()
        if done_at is not None and burst_at is None and t - done_at > 1.3:
            burst_at = t
            v.audio.play(t, 70, 1.0, "thud")
            for c, (b, k, _t0) in list(balls.items()):
                if k < MERGE_TOP:
                    parts.burst(rng, (b.position.x, b.position.y), color(k), n=10 + 3 * k, speed=700, life=0.9, size=7,
                                gravity=False)
                    sp.remove(b, c)
                    del balls[c]
        parts.step(1 / v.fps)
        for p_ in pops:
            p_[3] += 1 / v.fps
        pops = [p_ for p_ in pops if p_[3] < 0.35]
        height = min((b.position.y - _merge_r(k) for b, k, t0 in balls.values() if t - t0 > 1.0), default=floor_y)

        if not v.dry:
            v.begin(bg=(10, 10, 18))
            pygame.draw.polygon(v.surf, (17, 19, 32), [(left, top - 200), (right, top - 200), (right, floor_y - dip),
                                                       (CX, floor_y), (left, floor_y - dip)])
            for p, q in WALLS:
                v.line((235, 235, 240), p, q, 8)
            # 落とす口
            pygame.draw.rect(v.surf, (150, 155, 175), (int(nozzle_x - 34), int(top - 196), 68, 46), border_radius=8)
            pygame.draw.rect(v.surf, (90, 94, 112), (int(nozzle_x - 22), int(top - 156), 44, 16), border_radius=4)
            for x, y, col, age, r in pops:
                v.circle(mix(col, (17, 19, 32), age / 0.35), (x, y), r + 90 * age, width=4)
            for c, (b, k, _t0) in balls.items():
                r = _merge_r(k)
                x, y = b.position.x, b.position.y
                col = color(k)
                v.circle(mix(col, (255, 255, 255), 0.6), (x, y), r)
                v.circle(col, (x, y), r - 3)
                size = int(max(22, min(120, r * (1.15 if k < 3 else 0.95 if k < 6 else 0.75))))
                v.text(str(2 ** k), size, (x, y + 1), color=(12, 12, 18), outline=0)
            parts.draw(v)
            v.text("Same number = merge", 92, (CX, 150))
            if done_at is None:
                v.text(f"biggest: {2 ** best}", 80, (CX, floor_y + 110), color=color(best))
            else:
                v.text(f"{2 ** MERGE_TOP}!", 190, (CX, floor_y + 130), color=(255, 255, 255), outline=7)
        v.end(glow=0.22)
        if burst_at is not None and t - burst_at > 2.2:
            break
        if height < top - 150 and done_at is None:            # あふれた（このシードは使わない）
            if v.dry:
                v.frames = int(99 * v.fps)                    # 長さの範囲から外して、シード探しで選ばれないようにする
            return {"result": f"overflow at {t:.1f}s, biggest {2 ** best}", "overflow": True}
        if v.t > 75:
            break
    return {"result": f"{dropped} balls dropped, reached {2 ** best}"}


# ============================================================ chain
def run_chain(v, rng):
    """1,000 個の点が、折り返しながら下へ続く帯に並んでいる。上から落ちた 1 個のボールが最初の点に当たると、
    点は弾けて火花を飛ばし、火花が当たったとなりの点も弾ける。連鎖が帯をたどって、最後に大きな爆弾へ届く。"""
    total = 1000
    x0, x1 = 100.0, 980.0
    step = 25.0
    rows, bands = 4, 7
    band_h = (rows - 1) * step
    y0 = 430.0
    pitch = band_h + 90.0                        # 帯と帯のあいだは、火花が届かない広さ（届くのは約 58）
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    pts, order = [], []                          # 点の位置と、道のりの上での位置（0〜1。音の高さと色に使う）
    n_cols = int((x1 - x0) / step) + 1
    for b in range(bands):
        yb = y0 + b * pitch
        for c in range(n_cols):
            for r_ in range(rows):
                pts.append((x0 + c * step, yb + r_ * step))
                along = c if b % 2 == 0 else n_cols - 1 - c
                order.append((b * (n_cols + 3) + along) / (bands * (n_cols + 3)))
        if b < bands - 1:                        # 次の帯へのつなぎ（右端・左端を交互に）
            xe = x1 if b % 2 == 0 else x0
            sgn = -1 if b % 2 == 0 else 1
            for k in range(1, 4):                # 3 列 × 3 段で角を曲がる（細いと、ここで連鎖が切れやすい）
                for c in range(3):
                    pts.append((xe + sgn * c * step, yb + band_h + k * (pitch - band_h) / 4))
                    order.append((b * (n_cols + 3) + n_cols + k - 1) / (bands * (n_cols + 3)))
    P = np.array(pts) + nrng.uniform(-3.5, 3.5, (len(pts), 2))
    order = np.array(order)
    keep = np.ones(len(P), dtype=bool)
    surplus = len(P) - total
    if surplus > 0:                              # ちょうど 1,000 個にする（最初と最後の列は残す）
        inner = np.nonzero((order > 0.03) & (order < 0.97))[0]
        keep[nrng.choice(inner, surplus, replace=False)] = False
    P, order = P[keep], order[keep]
    n = len(P)
    state = np.zeros(n, dtype=np.int8)           # 0 = まだ, 1 = 火がついた, 2 = 弾けた
    lit_at = np.zeros(n)
    fuse0, fuse1 = 0.115, 0.05                  # 火がついてから弾けるまで。先へ進むほど短くなり、連鎖が速くなる
    F = np.zeros((0, 5))                         # 火花: x, y, vx, vy, 残り時間
    f_speed, f_life, f_n = 430.0, 0.11, 8
    last_b = bands - 1
    bomb_r = 78.0
    # 爆弾は最後の帯の終わりのすぐ下（火花が届く近さ）
    bomb = np.array([(x1 - 70.0) if last_b % 2 == 0 else (x0 + 70.0), y0 + last_b * pitch + band_h + bomb_r + 28.0])
    ball = np.array([x0 + 6.0, 250.0])           # 最初の 1 個は上から落ちてくる
    if rng.random() < 0.5:                       # 動画ごとに左右を入れ替える
        P[:, 0] = 2 * CX - P[:, 0]
        bomb[0] = 2 * CX - bomb[0]
        ball[0] = 2 * CX - ball[0]
    hue0 = rng.choice((0.62, 0.85, 0.45))        # 色の並びの始まり（青から／紫から／緑から）
    ball_v = np.array([0.0, 0.0])
    ball_on = True
    popped = 0
    rings = []                                   # 弾けた瞬間の輪 [x, y, 色, 経過]
    parts = Particles()
    boom_at = None
    flash = 0.0
    while True:
        t = v.t
        for _ in range(v.sub // 2):
            dt = 2 * v.dt
            if ball_on and t > 0.25:             # すぐ落ち始める（最初の 1 秒で何も起きないと、見てもらえない）
                ball_v[1] += 1500 * dt
                ball += ball_v * dt
                d = np.hypot(P[:, 0] - ball[0], P[:, 1] - ball[1])
                hit = (state == 0) & (d < 22)
                if hit.any():
                    state[hit] = 1
                    lit_at[hit] = t
                    ball_on = False
                    parts.burst(rng, tuple(ball), (255, 255, 255), n=16, speed=300, life=0.4, gravity=False)
            if len(F):
                F[:, 0:2] += F[:, 2:4] * dt
                F[:, 4] -= dt
                idx = np.nonzero(state == 0)[0]
                if len(idx):
                    D = np.hypot(F[:, None, 0] - P[None, idx, 0], F[:, None, 1] - P[None, idx, 1])
                    got = (D < 11.0).any(axis=0)
                    state[idx[got]] = 1
                    lit_at[idx[got]] = t
                if boom_at is None and (np.hypot(F[:, 0] - bomb[0], F[:, 1] - bomb[1]) < bomb_r).any():
                    boom_at = t
                    flash = 1.0
                    rest = state == 0                 # 爆風で、残っていた点も全部弾ける
                    state[rest] = 1
                    lit_at[rest] = t + nrng.uniform(0.0, 0.35, int(rest.sum()))
                    for _k in range(6):
                        parts.burst(rng, tuple(bomb), hsv(rng.random(), 0.8, 1.0), n=60, speed=1500, life=1.3, size=10,
                                    gravity=False)
                    v.audio.play(t, 50, 1.0, "thud")
                    v.audio.play(t, 75, 0.9, "thud")
                    for i, mm in enumerate((48, 55, 60, 64, 67, 72, 76)):
                        v.audio.note(t + 0.04 * i, mm, 0.8, "piano")
                F = F[F[:, 4] > 0]
            due = np.nonzero((state == 1) & (t - lit_at >= fuse0 + (fuse1 - fuse0) * order))[0]
            if len(due):
                state[due] = 2
                popped += len(due)
                ang = nrng.uniform(0, math.tau, (len(due), f_n))
                newf = np.zeros((len(due) * f_n, 5))
                newf[:, 0] = np.repeat(P[due, 0], f_n)
                newf[:, 1] = np.repeat(P[due, 1], f_n)
                newf[:, 2] = (np.cos(ang) * f_speed).ravel()
                newf[:, 3] = (np.sin(ang) * f_speed).ravel()
                newf[:, 4] = f_life
                F = np.vstack([F, newf])
                k = int(due[0])
                col = hsv(hue0 - 0.62 * float(order[k]), 0.85, 1.0)
                rings.append([float(P[k, 0]), float(P[k, 1]), col, 0.0])
                v.audio.note(t, penta(int(order[k] * 22), 50), 0.26, "marimba", channel="p", min_gap=0.05)
        parts.step(1 / v.fps)
        flash = max(0.0, flash - 2.5 / v.fps)
        for r_ in rings:
            r_[3] += 1 / v.fps
        rings = [r_ for r_ in rings if r_[3] < 0.3][-50:]

        if not v.dry:
            v.begin(bg=mix((8, 9, 16), (150, 110, 60), flash * 0.5))
            for i in np.nonzero(state < 2)[0]:
                if state[i] == 0:
                    v.circle(hsv(hue0 - 0.62 * float(order[i]), 0.75, 0.95), P[i], 8)
                else:                            # 火がついた点は白くふくらむ
                    v.circle((255, 255, 255), P[i], 8 + 7 * min(1.0, max(0.0, t - lit_at[i]) / fuse0))
            for x, y, col, age in rings:
                v.circle(mix(col, (8, 9, 16), age / 0.3), (x, y), 10 + 110 * age, width=3)
            for x, y, _vx, _vy, life in F:
                v.circle((255, 235, 170), (x, y), 2 + 3 * life / f_life)
            if boom_at is None:
                v.circle((235, 235, 240), bomb, bomb_r + 5)
                v.circle((16, 16, 22), bomb, bomb_r)
                v.text("BOMB", 44, bomb, color=(235, 235, 240), outline=0)
            else:
                age = t - boom_at
                for k in range(3):
                    rr = (age - 0.12 * k) * 1700
                    if rr > 0:
                        v.circle(mix((255, 240, 200), (8, 9, 16), min(1.0, age / 1.4)), bomb, rr, width=10)
            if ball_on:
                v.circle((255, 255, 255), ball, 15)
            parts.draw(v)
            v.text("1 ball, 1,000 dots", 100, (CX, 150))
            v.text("A spark sets off the next dot", 50, (CX, 232), color=(200, 205, 220), outline=3)
            v.text(f"{popped:,} / {n:,}", 84, (CX, 330))
        v.end(glow=0.3)
        if boom_at is not None and t - boom_at > 2.6:
            break
        if boom_at is None and t > 3 and not len(F) and not (state == 1).any():
            if v.dry:
                v.frames = int(99 * v.fps)       # 連鎖が途中で止まった（このシードは使わない）
            return {"result": f"chain stopped at {popped} (t={t:.1f})", "stopped": True}
        if v.t > 80:
            break
    return {"result": f"{popped} of {n} dots, then the bomb"}
