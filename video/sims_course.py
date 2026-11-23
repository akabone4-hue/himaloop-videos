"""sims_course.py — コース系: マーブルレース / 曲に合わせて跳ねるボール"""

import math

import pygame

import melodies
from engine import CX, H, W, Particles, hsv, mix, penta
from sims_arena import TEAMS


# ============================================================ 6. マーブルレース
def _build_course(rng, length):
    pegs, segs = [], []          # (x, y, r) / (x1, y1, x2, y2)
    left, right = 70, 1010
    y = 520.0
    last = None
    while y < length - 500:
        kind = rng.choice([k for k in ("pegs", "pegs", "zigzag", "funnel", "bumpers") if k != last])
        last = kind
        if kind == "pegs":
            rows = rng.randint(4, 6)
            for r in range(rows):
                off = 0 if r % 2 == 0 else 67
                for c in range(8):
                    x = left + 60 + off + c * 134
                    if x < right - 30:
                        pegs.append((x, y, 13))
                y += 128
        elif kind == "zigzag":
            for i in range(rng.randint(2, 3)):
                if i % 2 == 0:
                    segs.append((left, y, 690, y + 190))
                else:
                    segs.append((right, y, 390, y + 190))
                y += 250
        elif kind == "funnel":
            gap = rng.uniform(150, 190)
            cx = rng.uniform(380, 700)
            segs.append((left, y, cx - gap / 2, y + 230))
            segs.append((right, y, cx + gap / 2, y + 230))
            y += 300
            pegs.append((cx, y, 30))
            y += 110
        else:
            placed = []
            for _ in range(40):
                bx, by = rng.uniform(left + 110, right - 110), y + rng.uniform(40, 420)
                if all(math.hypot(bx - px, by - py) > 210 for px, py in placed):
                    placed.append((bx, by))
                if len(placed) >= 5:
                    break
            pegs.extend((bx, by, 52) for bx, by in placed)
            y += 500
        y += 60
    return pegs, segs


def run_marble(v, rng):
    length = 9800.0
    left, right = 70, 1010
    pegs, segs = _build_course(rng, length)
    buckets = {}
    for p in pegs:
        buckets.setdefault(int(p[1] // 120), []).append(p)
    n = 8
    mr = 26.0
    order = list(range(8))
    rng.shuffle(order)
    marbles = []
    for i in range(n):
        marbles.append({"name": TEAMS[order[i]][0], "col": TEAMS[order[i]][1],
                        "x": left + 80 + i * ((right - left - 160) / (n - 1)), "y": 300 + rng.uniform(-40, 40),
                        "vx": rng.uniform(-60, 60), "vy": 0.0, "slow": 0.0, "rank": None})
    g = 1300.0
    cam = 0.0
    release = 1.4
    finished = []
    first_at = None
    parts = Particles()
    while True:
        for _ in range(v.sub):
            if v.t < release:
                break
            for m in marbles:
                m["vy"] += g * v.dt
                m["vx"] *= 1 - 0.12 * v.dt
                sp = math.hypot(m["vx"], m["vy"])
                if sp > 1350:
                    m["vx"], m["vy"] = m["vx"] / sp * 1350, m["vy"] / sp * 1350
                m["x"] += m["vx"] * v.dt
                m["y"] += m["vy"] * v.dt
                if m["x"] - mr < left:
                    m["x"], m["vx"] = left + mr, abs(m["vx"]) * 0.5
                elif m["x"] + mr > right:
                    m["x"], m["vx"] = right - mr, -abs(m["vx"]) * 0.5
                b = int(m["y"] // 120)
                for bk in (b - 1, b, b + 1):
                    for px, py, pr in buckets.get(bk, ()):
                        dx, dy = m["x"] - px, m["y"] - py
                        rr = mr + pr
                        if abs(dx) > rr or abs(dy) > rr:
                            continue
                        d = math.hypot(dx, dy) or 1e-6
                        if d < rr:
                            nx, ny = dx / d, dy / d
                            vn = m["vx"] * nx + m["vy"] * ny
                            if vn < 0:
                                m["vx"] -= 1.55 * vn * nx
                                m["vy"] -= 1.55 * vn * ny
                                if -vn > 140:
                                    v.audio.note(v.t, penta(int(px // 90) % 12, 60), min(0.5, 0.12 - vn / 2600),
                                                 "pluck", channel="pg", min_gap=0.035)
                            m["x"], m["y"] = px + nx * rr, py + ny * rr
                for x1, y1, x2, y2 in segs:
                    if m["y"] < min(y1, y2) - 40 or m["y"] > max(y1, y2) + 40:
                        continue
                    ex, ey = x2 - x1, y2 - y1
                    t = ((m["x"] - x1) * ex + (m["y"] - y1) * ey) / (ex * ex + ey * ey)
                    t = min(1.0, max(0.0, t))
                    qx, qy = x1 + ex * t, y1 + ey * t
                    dx, dy = m["x"] - qx, m["y"] - qy
                    d = math.hypot(dx, dy) or 1e-6
                    rr = mr + 8
                    if d < rr:
                        nx, ny = dx / d, dy / d
                        vn = m["vx"] * nx + m["vy"] * ny
                        if vn < 0:
                            m["vx"] -= 1.3 * vn * nx
                            m["vy"] -= 1.3 * vn * ny
                            if -vn > 260:
                                v.audio.play(v.t, 520, min(0.3, -vn / 3000), "click", channel="sg", min_gap=0.05)
                        m["x"], m["y"] = qx + nx * rr, qy + ny * rr
                # 止まってしまった球を軽く弾く
                if math.hypot(m["vx"], m["vy"]) < 30 and m["rank"] is None:
                    m["slow"] += v.dt
                    if m["slow"] > 0.6:
                        m["vx"] += rng.choice([-1, 1]) * rng.uniform(150, 260)
                        m["vy"] -= 160
                        m["slow"] = 0.0
                else:
                    m["slow"] = 0.0
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = marbles[i], marbles[j]
                    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                    if abs(dx) > 2 * mr or abs(dy) > 2 * mr:
                        continue
                    d = math.hypot(dx, dy) or 1e-6
                    if d < 2 * mr:
                        nx, ny = dx / d, dy / d
                        rel = (a["vx"] - b["vx"]) * nx + (a["vy"] - b["vy"]) * ny
                        if rel > 0:
                            a["vx"] -= 0.9 * rel * nx
                            a["vy"] -= 0.9 * rel * ny
                            b["vx"] += 0.9 * rel * nx
                            b["vy"] += 0.9 * rel * ny
                        push = (2 * mr - d) / 2
                        a["x"] -= nx * push
                        a["y"] -= ny * push
                        b["x"] += nx * push
                        b["y"] += ny * push
            for m in marbles:
                if m["rank"] is None and m["y"] > length:
                    finished.append(m)
                    m["rank"] = len(finished)
                    parts.burst(rng, (m["x"], length), m["col"], n=30, speed=520, life=0.9, size=8)
                    if m["rank"] == 1:
                        first_at = v.t
                        for k, note in enumerate((60, 64, 67, 72, 76)):
                            v.audio.note(v.t + 0.07 * k, note, 0.8, "piano")
                    else:
                        v.audio.note(v.t, 72 - m["rank"], 0.4, "pop")
            parts.step(v.dt)

        ranking = sorted(marbles, key=lambda m: (m["rank"] or 99, -m["y"]))
        lead = ranking[0]
        target = min(max(0.0, lead["y"] - 1220), length - 1300)
        cam += (target - cam) * min(1.0, 5.0 / v.fps)

        if not v.dry:
            v.begin(bg=(18, 20, 28))
            pygame.draw.rect(v.surf, (34, 38, 52), (0, 0, left, H))
            pygame.draw.rect(v.surf, (34, 38, 52), (right, 0, W - right, H))
            fy = int(length - cam)
            if -60 < fy < H + 60:                                   # ゴールのチェッカー
                for i in range(0, 24):
                    for j in range(2):
                        if (i + j) % 2 == 0:
                            pygame.draw.rect(v.surf, (240, 240, 240), (left + i * 40, fy + j * 26, 40, 26))
            for px, py, pr in pegs:
                sy = py - cam
                if -80 < sy < H + 80:
                    v.circle((120, 130, 160) if pr < 20 else (90, 100, 140), (px, sy), pr, outline=(210, 215, 235))
            for x1, y1, x2, y2 in segs:
                if max(y1, y2) - cam > -40 and min(y1, y2) - cam < H + 40:
                    v.line((210, 215, 235), (x1, y1 - cam), (x2, y2 - cam), 16)
            for m in marbles:
                v.circle(mix(m["col"], (0, 0, 0), 0.5), (m["x"], m["y"] - cam), mr + 3)
                v.circle(m["col"], (m["x"], m["y"] - cam), mr)
                v.circle(mix(m["col"], (255, 255, 255), 0.7), (m["x"] - 7, m["y"] - cam - 7), 6)
            parts.draw(v, offset=(0, cam))
            band = pygame.Surface((W, 430), pygame.SRCALPHA)       # 上部の字幕帯
            band.fill((0, 0, 0, 190))
            v.surf.blit(band, (0, 0))
            v.text("Pick a color!" if v.t < 3.5 else "Which marble wins?", 96, (CX, 235))
            for i, m in enumerate(ranking):
                px = CX - 3.5 * 112 + i * 112
                v.circle(m["col"], (px, 350), 30, outline=(255, 255, 255))
                v.text(str(i + 1), 40, (px, 350), outline=3)
            if v.t < release:
                v.text(str(max(1, math.ceil(release - v.t))) if release - v.t > 0.35 else "GO!", 220, (CX, 900), outline=7)
            if first_at is not None:
                v.text(f"{finished[0]['name']} WINS", 150, (CX, 820), color=finished[0]["col"], outline=7)
        v.end(glow=0.3)
        if first_at is not None and v.t - first_at > 2.6:
            break
        if v.t > 95:
            break
    return {"result": f"{finished[0]['name']} wins" if finished else "no finisher"}


# ============================================================ 7. 曲に合わせて跳ねるボール
MUSIC_G = 4200.0          # 弧を描いて跳ねる型（3D の chime）の重力。大きいほど、同じ間隔でも高く跳ねる


def _arc_path(rng, notes, vx0, br):
    """経路を先に全部決める。ボールは重力で弧を描いて跳ね、音が鳴る瞬間にちょうど板へ着地する。
    次の音までが長いほど高く跳ねる。板はふつう水平で、向きを変える板だけ傾く。全体としては下へ進む。
    板がすでに通った道や後で通る道に重ならない置き方を、行き止まりなら戻ってやり直しながら探す。
    戻り値: legs [(着地時刻, x, y, 出る速度x, 出る速度y)], plats [(x, y, 板の向きの角度, 時刻, 長さ)]。"""
    gap = br + 8
    n = len(notes)
    g = MUSIC_G

    def ends(p):
        x, y, ang, _t, length = p
        hx, hy = math.cos(ang) * length / 2, math.sin(ang) * length / 2
        return x - hx, y - hy, x + hx, y + hy

    def dist_to_bar(px, py, p):
        x0, y0, x1, y1 = ends(p)
        dx, dy = x1 - x0, y1 - y0
        k = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - x0 - dx * k, py - y0 - dy * k)

    def arc(x, y, vx, vy, dt):
        """着地点から次の着地点までの弧。(細かい点の並び, それを囲む四角) を返す。"""
        steps = max(6, int(dt * 90))
        pts_ = [(x + vx * dt * k / steps, y + vy * dt * k / steps + 0.5 * g * (dt * k / steps) ** 2)
                for k in range(steps + 1)]
        xs, ys = [q[0] for q in pts_], [q[1] for q in pts_]
        return pts_, (min(xs), min(ys), max(xs), max(ys))

    def path_hits(a_, p, margin, skip_head=0, skip_tail=0):
        """弧 a_ が板 p に近づきすぎるか。先に囲みの四角どうしで大まかに外す（探索を速くするため）。"""
        points, (x0, y0, x1, y1) = a_
        r = p[4] / 2 + margin
        if p[0] + r < x0 or p[0] - r > x1 or p[1] + r < y0 or p[1] - r > y1:
            return False
        sel = points[skip_head:len(points) - skip_tail]
        return any(abs(px - p[0]) < r and abs(py - p[1]) < r and dist_to_bar(px, py, p) < margin for px, py in sel)

    def bars_touch(p, q):
        """板どうしが重なる、またはすき間が狭すぎる。"""
        if math.hypot(p[0] - q[0], p[1] - q[1]) > (p[4] + q[4]) / 2 + 22:
            return False
        x0, y0, x1, y1 = ends(p)
        u0, v0_, u1, v1_ = ends(q)
        return min(dist_to_bar(x0, y0, q), dist_to_bar(x1, y1, q), dist_to_bar(p[0], p[1], q),
                   dist_to_bar(u0, v0_, p), dist_to_bar(u1, v1_, p)) < 21

    for _attempt in range(300):
        side = rng.choice([-1, 1])
        t0 = notes[0][0]
        fall = min(t0, 0.55)                                   # 最初は少し上から落ちてくる
        first = (-side * vx0 * fall, -0.5 * g * fall * fall)
        legs = [(t0 - fall, first[0], first[1], side * vx0, 0.0)]
        plats, arcs = [], [arc(first[0], first[1], side * vx0, 0.0, fall)]
        budget = [6000]
        turn_in = [rng.randint(7, 13)]                         # 何音ごとに左右の向きを変えるか

        def rec(i, x, y, vx, vy_in, since_turn):
            """i 番目の音で (x, y) に着地する。vx・vy_in は着地の直前の速度。"""
            if i == n:
                return True
            budget[0] -= 1
            if budget[0] < 0:
                return False
            t = notes[i][0]
            dt = (notes[i + 1][0] - t) if i + 1 < n else 0.8
            hop = 0.5 * g * dt * dt                            # まっすぐ同じ高さへ戻るときに使う落差
            prev_dt = (t - notes[i - 1][0]) if i else 9.0
            length = max(34.0, min(120.0, vx0 * min(dt, prev_dt) - 24.0))    # となりの板とのあいだにすき間を残す
            cands = []
            for _k in range(6):
                drop = hop * (rng.uniform(-0.25, 0.05) if rng.random() < 0.15 else rng.uniform(0.08, 0.5))
                drop = max(-140.0, min(260.0, drop))           # 次の着地点が、いまよりどれだけ下か
                flip = since_turn >= turn_in[0] and dt > 0.3 and rng.random() < 0.7
                if flip:                                       # 折り返すときは大きく下りて、来た道の下をくぐる
                    drop = min(430.0, hop * rng.uniform(0.5, 0.82))
                cands.append((drop, -vx if flip else vx, flip))
            for drop, nvx, flip in cands:
                vy_out = (drop - hop) / dt                     # 上向き（負）に打ち出す速さ
                if vy_out > -120:
                    continue
                dvx, dvy = nvx - vx, vy_out - vy_in            # 板の向き = 速度の変化に垂直（水平に跳ねるなら水平の板）
                nl = math.hypot(dvx, dvy)
                nrm = (dvx / nl, dvy / nl)                     # 板からボールへ向かう向き
                p = (x - nrm[0] * gap, y - nrm[1] * gap, math.atan2(nrm[0], -nrm[1]), t, length)
                if any(path_hits(a_, p, br + 6) for a_ in arcs[:-1]) or path_hits(arcs[-1], p, br + 4, skip_tail=3):
                    continue                                   # 新しい板が、もう通った道に重ならない
                if any(bars_touch(p, q) for q in plats):
                    continue
                nxt = arc(x, y, nvx, vy_out, dt)
                if any(path_hits(nxt, q, br + 6, skip_head=3) for q in plats) or path_hits(nxt, p, br + 4, skip_head=4):
                    continue                                   # これから通る道が、置いてある板を突き抜けない
                plats.append(p)
                arcs.append(nxt)
                legs.append((t, x, y, nvx, vy_out))
                if rec(i + 1, nxt[0][-1][0], nxt[0][-1][1], nvx, vy_out + g * dt, 0 if flip else since_turn + 1):
                    return True
                plats.pop()
                arcs.pop()
                legs.pop()
            return False

        if rec(0, 0.0, 0.0, side * vx0, g * fall, 0):
            return legs, plats
    raise RuntimeError("chime: could not lay out the bars")


def arc_layout(rng, song, br=22.0):
    """曲 1 つぶんの「弧を描いて跳ねる」経路を作る（3D の chime が使う）。
    戻り値: (音の一覧 [(時刻, MIDI)], 曲の終わりの時刻, legs, plats, 横向きの速さ)。"""
    notes, end_t = melodies.timeline(song, start=1.2)
    shortest = min(b_ - a_ for (a_, _m), (b_, _m2) in zip(notes, notes[1:]))
    vx0 = max(300.0, min(470.0, 70.0 / shortest))            # 速い曲ほど横に速く進む（板どうしが重ならないように）
    legs, plats = _arc_path(rng, notes, vx0, br)
    return notes, end_t, legs, plats, vx0


def _wall_path(rng, notes, sx, sy, br):
    """壁反射の経路を先に全部決める。ボールは斜めにまっすぐ進み、縦か横の板で跳ね返る。
    音が鳴る瞬間に必ず板へ当たるよう、当たる位置に板を置いていく。sx・sy は横と縦の速さ。
    板がすでに通った道や後で通る道に重ならない置き方を、行き止まりなら戻ってやり直しながら探す。
    戻り値: pts [(時刻, x, y, 向きx, 向きy)], plats [(x, y, 縦板か, 当たる時刻, 長さ)]。"""
    gap = br + 8
    n = len(notes)

    def rect(p):                      # 板の四角（中心 x, y, 半分の幅, 半分の高さ）
        x, y, vertical, _t, length = p
        return (x, y, 8, length / 2) if vertical else (x, y, length / 2, 8)

    def seg_hits(x0, y0, x1, y1, p, margin):
        cx, cy, hw, hh = rect(p)
        hw, hh = hw + margin, hh + margin
        if max(x0, x1) < cx - hw or min(x0, x1) > cx + hw or max(y0, y1) < cy - hh or min(y0, y1) > cy + hh:
            return False
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) / 5))
        for k in range(steps + 1):
            px, py = x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps
            if abs(px - cx) < hw and abs(py - cy) < hh:
                return True
        return False

    def overlap(p, q):
        ax, ay, aw, ah = rect(p)
        bx, by, bw, bh = rect(q)
        return abs(ax - bx) < aw + bw + 6 and abs(ay - by) < ah + bh + 6

    for _attempt in range(300):
        dx0 = rng.choice([-1, 1])
        t0 = notes[0][0]
        pts = [(0.0, -dx0 * sx * t0, -sy * t0, dx0, 1)]
        plats, segs = [], []
        budget = [4000]

        def rec(i, x, y, dx, dy, must, t_prev):
            if i == n:
                return True
            budget[0] -= 1
            if budget[0] < 0:
                return False
            t = notes[i][0]
            nx, ny = x + dx * sx * (t - t_prev), y + dy * sy * (t - t_prev)
            for p in plats[:-1]:                              # これから通る道が、前に置いた板を突き抜けない
                if seg_hits(x, y, nx, ny, p, br - 2):
                    return False
            step = min(t - t_prev if i else 9.0, notes[i + 1][0] - t if i + 1 < n else 9.0)
            length = max(44.0, min(120.0, min(sx, sy) * step * 0.95))
            first = "y" if (must or (dy > 0 and rng.random() < 0.30)) else "x"
            for o in ([first] if must else [first, "x" if first == "y" else "y"]):
                if o == "y":
                    p = (nx, ny + dy * gap, False, t, length)
                    nxt = (dx, -dy, dy > 0)                   # 上向きになったら、次で必ず下向きへ戻す
                else:
                    p = (nx + dx * gap, ny, True, t, length)
                    nxt = (-dx, dy, False)
                if any(seg_hits(*s, p, br - 2) for s in segs):       # 新しい板が、もう通った道に重ならない
                    continue
                if any(overlap(p, q) for q in plats):
                    continue
                plats.append(p)
                segs.append((x, y, nx, ny))
                pts.append((t, nx, ny, nxt[0], nxt[1]))
                if rec(i + 1, nx, ny, nxt[0], nxt[1], nxt[2], t):
                    return True
                plats.pop()
                segs.pop()
                pts.pop()
            return False

        if rec(0, pts[0][1], pts[0][2], dx0, 1, False, 0.0):
            return pts, plats
    raise RuntimeError("music: could not lay out the bars")


def run_music(v, rng):
    import sys
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))
    song = rng.choice(melodies.ALL)
    notes, end_t = melodies.timeline(song, start=1.2)
    lift = 12 if min(m for _t, m in notes) < 57 else 0       # 低すぎる曲は、曲全体を 1 オクターブ上げる
    speed = 900.0
    br = 22.0
    hue0 = rng.random()
    slope = math.radians(rng.choice([38, 45, 45, 52]))        # 進む角度。動画ごとに少し変える
    sx, sy = speed * math.cos(slope), speed * math.sin(slope)
    pts, raw = _wall_path(rng, notes, sx, sy, br)
    plats = [(x, y, vertical, t, hsv(hue0 + i * 0.017, 0.8, 1.0), length)       # (x, y, 縦板か, 当たる時刻, 色, 長さ)
             for i, (x, y, vertical, t, length) in enumerate(raw)]
    total = end_t + 1.6
    hit_x = {p[0]: p[1] for p in pts}          # 当たった時刻 → そのときのボールの位置（板が引っ込む向きを決める）
    hit_y = {p[0]: p[2] for p in pts}

    def pos(t):
        k = 0
        for j in range(len(pts)):
            if pts[j][0] <= t:
                k = j
            else:
                break
        pt = pts[k]
        return pt[1] + pt[3] * sx * (t - pt[0]), pt[2] + pt[4] * sy * (t - pt[0])

    camx, camy = pos(0.0)
    next_note = 0
    parts = Particles()
    while v.t < total:
        t = v.t
        while next_note < len(notes) and notes[next_note][0] <= t + 0.5 / v.fps:
            nt, midi = notes[next_note]
            gap_t = (notes[next_note + 1][0] - nt) if next_note + 1 < len(notes) else 1.5
            v.audio.note(nt, midi + lift, 0.7, "piano", dur=gap_t + 0.03)
            px, py, _, _, pc, _len = plats[next_note]
            parts.burst(rng, (px, py), pc, n=12, speed=380, life=0.5, gravity=False)
            next_note += 1
        bx, by = pos(t)
        camx += (bx - camx) * min(1.0, 6.0 / v.fps)
        camy += (by - camy) * min(1.0, 6.0 / v.fps)
        parts.step(1 / v.fps)
        if not v.dry:
            ox, oy = camx - CX, camy - 900
            v.begin(bg=(12, 12, 18))
            gx0, gy0 = int(ox // 135), int(oy // 135)            # 背景の点（動きが分かるように）
            for gx in range(gx0, gx0 + 10):
                for gy in range(gy0, gy0 + 16):
                    v.circle((38, 40, 54), (gx * 135 - ox, gy * 135 - oy), 4)
            done = [p for p in pts if p[0] <= t]                    # 通った道
            path = [(p[1] - ox, p[2] - oy) for p in done[-40:]] + [(bx - ox, by - oy)]
            if len(path) > 1:
                pygame.draw.lines(v.surf, (70, 74, 100), False, path, 4)
            for px, py, vertical, pt, pc, length in plats:
                sx_, sy_ = px - ox, py - oy
                if not (-150 < sx_ < W + 150 and -150 < sy_ < H + 150):
                    continue
                if pt <= t:
                    age = t - pt
                    c = mix((255, 255, 255), pc, min(1.0, age / 0.25))
                    push = 9.0 * max(0.0, 1 - age / 0.18)       # 当たった板は、押されて少し引っ込んでから戻る
                    if vertical:
                        sx_ += push * (1 if px > hit_x[pt] else -1)
                    else:
                        sy_ += push * (1 if py > hit_y[pt] else -1)
                    if age < 0.35:                               # 当たった瞬間の光の輪
                        v.circle(mix(pc, (12, 12, 18), age / 0.35), (sx_, sy_), 30 + 150 * age, width=3)
                else:
                    c = (86, 90, 112)
                w_, h_ = (16, int(length)) if vertical else (int(length), 16)
                pygame.draw.rect(v.surf, c, (int(sx_ - w_ / 2), int(sy_ - h_ / 2), w_, h_), border_radius=7)
            for k in range(10, 0, -1):                              # ボールの尾
                tx, ty = pos(max(0.0, t - k * 0.011))
                v.circle(mix((12, 12, 18), (255, 255, 255), 0.5 - k * 0.045), (tx - ox, ty - oy), br - k * 1.4)
            parts.draw(v, offset=(ox, oy))
            v.circle((255, 255, 255), (bx - ox, by - oy), br)
            band = pygame.Surface((W, 380), pygame.SRCALPHA)
            band.fill((0, 0, 0, 170))
            v.surf.blit(band, (0, 0))
            v.text(song["title"], 100 if len(song["title"]) < 16 else 64, (CX, 220))
            v.text("every bounce = 1 note", 62, (CX, 312), color=(200, 200, 210), outline=3)
        v.end(glow=0.45)
    return {"song": song, "result": f"{len(notes)} notes"}
