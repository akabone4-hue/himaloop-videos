"""sims_ring.py — 円形アリーナ系: 大きくなるボール / リング脱出 / 脱出するたび増殖"""

import math

import numpy as np

import melodies
from engine import ARP_PAT, ARP_PROG, CX, CY, H, W, Particles, hsv, mix, penta, wrap_angle


# ============================================================ 1. バウンドするたび大きくなる
def run_grow(v, rng):
    song = rng.choice(melodies.ALL)
    notes = melodies.pitches(song)
    R = 470.0
    r = 24.0
    x, y = CX + rng.uniform(-150, 150), CY - rng.uniform(80, 220)
    vx, vy = rng.choice([-1, 1]) * rng.uniform(260, 420), rng.uniform(-100, 100)
    g = 1500.0
    hue0 = rng.random()
    bounces = 0
    pts = []                     # 壁に当たった点（ボールと線で結ぶ）
    parts = Particles()
    flash = 0.0
    done_at = None
    while True:
        for _ in range(v.sub):
            if done_at is None:
                vy += g * v.dt
                x += vx * v.dt
                y += vy * v.dt
                dx, dy = x - CX, y - CY
                d = math.hypot(dx, dy) or 1e-6
                if d + r > R:
                    nx, ny = dx / d, dy / d
                    vn = vx * nx + vy * ny
                    if vn > 0:
                        vx -= 2 * vn * nx
                        vy -= 2 * vn * ny
                        # 少しだけ向きを散らして、同じ軌道の繰り返しを防ぐ
                        a = rng.uniform(-0.12, 0.12)
                        vx, vy = vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a)
                        sp = math.hypot(vx, vy)
                        want = max(sp, 760.0)
                        vx, vy = vx / sp * want, vy / sp * want
                        if v.audio.note(v.t, notes[bounces % len(notes)], 0.55, "piano",
                                        channel="b", min_gap=0.055):
                            bounces += 1
                            col = hsv(hue0 + bounces * 0.031, 0.85, 1.0)
                            pts.append((CX + nx * R, CY + ny * R, col))
                            parts.burst(rng, (CX + nx * R, CY + ny * R), col, n=10, speed=360)
                            flash = 1.0
                            r += 2.6 + r * 0.026
                    d = min(d, R - r) if R - r > 0 else 0.0
                    x, y = CX + nx * max(R - r, 0), CY + ny * max(R - r, 0)
                if r >= R - 3:
                    r = R - 3
                    done_at = v.t
                    v.audio.note(v.t, notes[0] - 12, 0.9, "piano")
                    v.audio.note(v.t, notes[0], 0.7, "piano")
            parts.step(v.dt)
        flash = max(0.0, flash - 4.0 / v.fps)

        if not v.dry:
            col = hsv(hue0 + bounces * 0.031, 0.85, 1.0)
            v.begin(fade=0.90)
            v.circle(mix((0, 0, 0), col, 0.55), (x, y), r, target=v.trail)
            for px, py, pc in pts[-70:]:
                v.line(mix((0, 0, 0), pc, 0.75), (px, py), (x, y))
            v.circle(col, (x, y), r, outline=(255, 255, 255))
            ring = mix((235, 235, 235), col, flash)
            v.circle(ring, (CX, CY), R + 6 + int(6 * flash), width=6 + int(6 * flash))
            parts.draw(v)
            v.text("Ball gets bigger", 96, (CX, 215))
            v.text("every bounce", 96, (CX, 300))
            v.text(f"{bounces}", 150, (CX, CY + R + 150), color=col)
            if done_at is not None:
                v.text("FULL!", 190, (CX, CY), color=(255, 255, 255), outline=6)
        v.end(glow=0.55)
        if done_at is not None and v.t - done_at > 1.6:
            break
        if v.t > 75:
            break
    return {"song": song, "result": f"{bounces} bounces"}


# ============================================================ 2. 回転するリングから脱出
def run_rings(v, rng):
    n_rings = 10
    radii = [160 + 34 * i for i in range(n_rings)]
    gap_half = [0.70 - 0.02 * i for i in range(n_rings)]             # 外側ほどすき間が狭い
    omega = [(1 if i % 2 == 0 else -1) * rng.uniform(0.9, 1.5) for i in range(n_rings)]
    rot = [rng.uniform(0, math.tau) for _ in range(n_rings)]
    hue0 = rng.random()
    br = 15.0
    x, y = CX + rng.uniform(-30, 30), CY + rng.uniform(-30, 30)
    a0 = rng.uniform(0, math.tau)
    vx, vy = math.cos(a0) * 620, math.sin(a0) * 620
    g = 850.0
    k = 0                         # いちばん内側の、まだ残っているリング
    parts = Particles()
    escaped_at = None
    hits = 0
    while True:
        for _ in range(v.sub):
            vy += g * v.dt
            x += vx * v.dt
            y += vy * v.dt
            for i in range(k, n_rings):
                rot[i] += omega[i] * v.dt
            if k < n_rings:
                dx, dy = x - CX, y - CY
                d = math.hypot(dx, dy) or 1e-6
                Rk = radii[k]
                if d - br > Rk + 5:                       # 完全に外へ出た → リングが壊れる
                    col = hsv(hue0 + k * 0.07, 0.8, 1.0)
                    for j in range(26):
                        a = rot[k] + j / 26 * math.tau
                        parts.burst(rng, (CX + math.cos(a) * Rk, CY + math.sin(a) * Rk), col, n=2, speed=260, life=0.8)
                    chord = ARP_PROG[(k + 1) % 4]                 # リングが壊れるたびに和音が次へ進む
                    v.audio.note(v.t, chord[0] - 12, 0.6, "piano", dur=1.0)
                    v.audio.note(v.t + 0.03, chord[2] + 12, 0.5, "piano", dur=1.0)
                    v.audio.note(v.t + 0.06, chord[4] + 12, 0.45, "piano", dur=1.0)
                    k += 1
                    if k == n_rings:
                        escaped_at = v.t
                elif d + br >= Rk - 5 and d < Rk:
                    nx, ny = dx / d, dy / d
                    vn = vx * nx + vy * ny
                    rel = wrap_angle(math.atan2(dy, dx) - rot[k])
                    in_gap = abs(rel) < gap_half[k] - math.asin(min(1.0, br / Rk)) * 0.75
                    if vn > 0 and not in_gap:
                        vx -= 2 * vn * nx
                        vy -= 2 * vn * ny
                        a = rng.uniform(-0.1, 0.1)
                        vx, vy = vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a)
                        sp = math.hypot(vx, vy)
                        want = min(max(sp, 680.0), 980.0)
                        vx, vy = vx / sp * want, vy / sp * want
                        x, y = CX + nx * (Rk - 5 - br), CY + ny * (Rk - 5 - br)
                        hits += 1
                        v.audio.note(v.t, ARP_PROG[k % 4][ARP_PAT[hits % 8]], 0.42, "marimba",
                                     channel="b", min_gap=0.07)
            parts.step(v.dt)

        if not v.dry:
            v.begin(fade=0.86)
            v.circle((255, 255, 255), (x, y), br * 0.8, target=v.trail)
            for i in range(k, n_rings):
                col = hsv(hue0 + i * 0.07, 0.8, 1.0)
                v.arc_band(col, (CX, CY), radii[i] - 7, radii[i] + 7,
                           rot[i] + gap_half[i], rot[i] + math.tau - gap_half[i])
            parts.draw(v)
            v.circle((255, 255, 255), (x, y), br)
            v.text("Can the ball escape?", 96, (CX, 245))
            if escaped_at is None:
                v.text(f"Rings left: {n_rings - k}", 76, (CX, CY + 480 + 170))
                v.text(f"{v.t:0.1f}s", 60, (CX, CY + 480 + 250), color=(200, 200, 200))
            else:
                v.text("ESCAPED!", 150, (CX, CY - 40), outline=6)
                v.text(f"{escaped_at:0.1f} seconds", 80, (CX, CY + 80))
        v.end(glow=0.6)
        if escaped_at is not None and v.t - escaped_at > 2.0:
            break
        if v.t > 90:
            break
    return {"result": f"escaped in {escaped_at:0.1f}s" if escaped_at else "did not escape"}


# ============================================================ 3. 脱出するたびに 2 個増える
def run_multiply(v, rng):
    R = 400.0
    gap_half = 0.58
    omega = rng.choice([-1, 1]) * rng.uniform(1.0, 1.4)
    rot = rng.uniform(0, math.tau)
    br = 13.0
    g = 1100.0
    cap = 220                    # 中にいる数がこれに達したらリングが壊れてフィナーレ
    hue0 = rng.random()
    P = np.array([[CX, CY - 60.0]])
    a0 = rng.uniform(0, math.tau)
    V = np.array([[math.cos(a0) * 600, math.sin(a0) * 600]])
    inside = np.array([True])
    hue = np.array([hue0])
    total = 1
    broke_at = None
    final_n = cap
    parts = Particles()
    C = np.array([CX, CY], dtype=float)
    # 跳ねる音は、でたらめな音ではなく決まった分散和音を順番に鳴らす（C → G → Am → F）
    prog, pat = ARP_PROG, ARP_PAT
    seq, last_note = 0, -9.0

    def bounce_note(t, n_in):
        nonlocal seq, last_note
        grid = 0.09
        tt = t if n_in < 5 else math.ceil(t / grid) * grid      # 数が増えたら拍にそろえる
        if tt - last_note < (0.07 if n_in < 5 else grid - 1e-6):
            return
        last_note = tt
        v.audio.note(tt, prog[(seq // 8) % 4][pat[seq % 8]], 0.34, "marimba")
        seq += 1

    while True:
        for _ in range(v.sub):
            rot += omega * v.dt
            V[:, 1] += g * v.dt
            P += V * v.dt
            D = P - C
            d = np.hypot(D[:, 0], D[:, 1]) + 1e-9
            N = D / d[:, None]
            vn = (V * N).sum(axis=1)
            if broke_at is None:
                ang = np.arctan2(D[:, 1], D[:, 0])
                rel = (ang - rot + np.pi) % (2 * np.pi) - np.pi
                in_gap = np.abs(rel) < gap_half - 0.03
                hit = inside & (d + br >= R - 5) & (d < R) & (vn > 0) & ~in_gap
                if hit.any():
                    V[hit] -= 2 * vn[hit, None] * N[hit]
                    sp = np.hypot(V[hit, 0], V[hit, 1])
                    want = np.clip(sp, 640, 1000)
                    V[hit] *= (want / sp)[:, None]
                    P[hit] = C + N[hit] * (R - 5 - br)
                    bounce_note(v.t, int(inside.sum()))
                # 外に出た球はリングの外側で跳ね返る（中には戻らない）
                ext = ~inside & (d - br < R + 5) & (vn < 0)
                if ext.any():
                    V[ext] -= 1.6 * vn[ext, None] * N[ext]
                    P[ext] = C + N[ext] * (R + 5 + br)
                out = inside & (d - br > R + 5)
                n_out = int(out.sum())
                if n_out:
                    inside[out] = False
                    for i in np.nonzero(out)[0]:
                        parts.burst(rng, (float(P[i, 0]), float(P[i, 1])), hsv(float(hue[i]), 0.75, 1.0),
                                    n=8, speed=300, life=0.45)
                    k = 2 * n_out
                    ang2 = np.array([rng.uniform(0, math.tau) for _ in range(k)])
                    spd = np.array([rng.uniform(420, 700) for _ in range(k)])
                    P = np.vstack([P, np.tile(C, (k, 1)) + np.array([[rng.uniform(-20, 20), rng.uniform(-20, 20)] for _ in range(k)])])
                    V = np.vstack([V, np.column_stack([np.cos(ang2) * spd, np.sin(ang2) * spd])])
                    inside = np.concatenate([inside, np.ones(k, dtype=bool)])
                    hue = np.concatenate([hue, hue0 + (total + np.arange(k)) * 0.013])
                    total += k
                    v.audio.note(v.t, prog[(seq // 8) % 4][0] + 24, 0.42, "piano", channel="p", min_gap=0.09, dur=0.5)
                    v.audio.play(v.t, 620, 0.22, "pop", channel="pp", min_gap=0.05)
                if int(inside.sum()) >= cap:
                    # フィナーレ: リングが割れ、中のボールがそれぞれ 3 個に弾けて花火のように飛び散る
                    broke_at = v.t
                    idx = np.nonzero(inside)[0]
                    k = 2 * len(idx)
                    ang2 = np.array([rng.uniform(0, math.tau) for _ in range(k)])
                    spd = np.array([rng.uniform(350, 1250) for _ in range(k)])
                    out_dir = P[idx] - C
                    out_dir /= (np.hypot(out_dir[:, 0], out_dir[:, 1])[:, None] + 1e-9)
                    V[idx] = out_dir * np.array([rng.uniform(500, 1100) for _ in idx])[:, None]
                    V[idx, 1] -= 250
                    P = np.vstack([P, np.repeat(P[idx], 2, axis=0)])
                    V = np.vstack([V, np.column_stack([np.cos(ang2) * spd, np.sin(ang2) * spd - 250])])
                    hue = np.concatenate([hue, np.repeat(hue[idx], 2) + np.array([rng.uniform(-0.06, 0.06) for _ in range(k)])])
                    inside = np.zeros(len(P), dtype=bool)
                    final_n = len(P)
                    for j in range(60):
                        a = j / 60 * math.tau
                        parts.burst(rng, (CX + math.cos(a) * R, CY + math.sin(a) * R), (255, 255, 255), n=4,
                                    speed=420, life=1.0)
                    v.audio.play(v.t, 85, 1.0, "thud")
                    for i, n in enumerate((48, 55, 60, 64, 67, 72, 76, 79, 84)):
                        v.audio.note(v.t + 0.035 * i, n, 0.75, "piano")
            # 画面外へ落ちた球を捨てる
            keep = P[:, 1] < H + 80
            if not keep.all():
                P, V, inside, hue = P[keep], V[keep], inside[keep], hue[keep]
            parts.step(v.dt)

        n_in = int(inside.sum())
        if not v.dry:
            v.begin(fade=0.80)
            for i in range(len(P)):
                v.circle(hsv(float(hue[i]), 0.75, 0.55), P[i], br * 0.75, target=v.trail)
            if broke_at is None:
                v.arc_band((240, 240, 240), (CX, CY), R - 7, R + 7, rot + gap_half, rot + math.tau - gap_half)
            for i in range(len(P)):
                v.circle(hsv(float(hue[i]), 0.75, 1.0), P[i], br)
            parts.draw(v)
            v.text("Every escape", 96, (CX, 215))
            v.text("= 2 new balls", 96, (CX, 300))
            shown = n_in if broke_at is None else final_n
            v.text(f"{shown}", 170, (CX, CY + R + 190), color=hsv(hue0 + total * 0.013, 0.6, 1.0))
            v.text("balls", 60, (CX, CY + R + 290), color=(200, 200, 200))
        v.end(glow=0.5)
        if broke_at is not None and v.t - broke_at > 2.4:
            break
        if broke_at is None and len(P) == 0:      # 全部外へ出てしまった（起こらないはずの保険）
            break
        if v.t > 90:
            break
    return {"result": f"1 -> {cap} balls, then every ball bursts into 3"}
